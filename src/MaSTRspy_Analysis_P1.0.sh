#!/bin/bash

# --- Script Configuration ---
# Exit immediately if a command exits with a non-zero status.
set -e
# Treat failures in a pipeline as a failure for the entire pipeline.
set -o pipefail

SECONDS=0

# --- Functions ---

# Function to print usage information
print_USAGE() {
    printf "USAGE: bash ./MaSTRspy_Analysis_P1.0.sh <path/to/InputConfig.txt> <path/to/ToolsConfig.txt>\n\n"
    printf "EXAMPLE:\n"
    printf "bash ./MaSTRspy_Analysis_P1.0.sh \"/home/user/config/InputConfig.txt\" \"/home/user/config/ToolsConfig.txt\"\n\n"
    printf "NOTE: Always enclose paths with spaces in double quotes.\n"
}

# Function to calculate mapping coverage and statistics
get_cov() {
    local bam_input_dir="$1"
    local stats_output_dir="$2"
    local regions_to_check_bed="$3"

    for bamfile in "$bam_input_dir"/*.bam; do
        local bamfile_name
        bamfile_name="$(basename "$bamfile")"

        printf "Calculating mapping stats for %s...\n" "$bamfile_name"

        # Get total, mapped, and unmapped reads from bam and their percentage
        $SAMTOOLS flagstat "$bamfile" |
            sed -n '1p;5p' |
            awk -F' ' '{print $1}' |
            xargs |
            awk '{print $1"\t"$2,"("$2/$1*100"%)""\t"$1-$2,"("($1-$2)/$1*100"%)"}' > "$stats_output_dir/${bamfile_name}_MappingStats.txt"

        # Add header (using a portable method instead of sed -i)
        { echo -e "TotalReads\tIntersectMappedReads(Ratio)\tUnmapedReads(Ration)"; cat "$stats_output_dir/${bamfile_name}_MappingStats.txt"; } > "$stats_output_dir/${bamfile_name}_MappingStats.txt.tmp" && \
        mv "$stats_output_dir/${bamfile_name}_MappingStats.txt.tmp" "$stats_output_dir/${bamfile_name}_MappingStats.txt"

        # Get overlap regions from mapped reads
        local region_cov
        local bam_cov
        region_cov=$($SAMTOOLS view -c -F 2308 -L "$regions_to_check_bed" "$bamfile")
        bam_cov=$($SAMTOOLS view -c -F 2308 "$bamfile")

        paste <(echo "$bam_cov") <(echo "$region_cov") |
            awk '{print $1"\t"$2"\t"$2/$1*100"(%)"}' > "$stats_output_dir/${bamfile_name}.regions.OverlapStats.txt"
        
        # Add header (using a portable method instead of sed -i)
        { echo -e "GenomicMapping\tRegionsOverllaped\tRatio"; cat "$stats_output_dir/${bamfile_name}.regions.OverlapStats.txt"; } > "$stats_output_dir/${bamfile_name}.regions.OverlapStats.txt.tmp" && \
        mv "$stats_output_dir/${bamfile_name}.regions.OverlapStats.txt.tmp" "$stats_output_dir/${bamfile_name}.regions.OverlapStats.txt"
    done
}

# Function to process one STR locus for a given sample bam
process_locus_for_sample() {
    local sample_bam_file="$1"
    local str_bed_file="$2"
    # Each parallel job gets its own temporary directory to avoid race conditions
    local temp_dir="$3"

    local bam_name
    local bed_name
    local bed_fname
    bam_name="$(basename "$sample_bam_file")"
    bed_name="$(basename "$str_bed_file")"
    bed_fname=$(basename "$bed_name" .bed)

    printf "\n# Working on Sample: [%s] for STR Locus: [%s]\n" "$bam_name" "$bed_name"

    # Define intermediate filenames for clarity, ensuring they are unique to this job
    local intersected_bam="$temp_dir/intersected.bam"
    local intersected_fq="$temp_dir/intersected.fq"
    local motif_mapped_sam="$temp_dir/motif_alignment.sam"
    local motif_mapped_bam="$temp_dir/motif_alignment.bam"
    local motif_mapped_sorted_bam="$OUTPUT_DIR/IntersectMappedReads/${bed_fname}_${bam_name}_alignment.sorted.bam"

    # Step 1: Intersect regions and create FASTQ
    printf "## Step 1/5: Intersecting reads from STR region...\n"
    $BEDTOOLS intersect -a "$sample_bam_file" -b "$str_bed_file" > "$intersected_bam"
    $BEDTOOLS bamtofastq -i "$intersected_bam" -fq "$intersected_fq"

    # Step 2: Map extracted reads to the STR motif reference
    printf "## Step 2/5: Mapping extracted reads to STR motif reference...\n"
    local motif_fa_file="$STR_FASTA/${bed_fname}.fa"
    if [[ "$READ_TYPE" == "ont" ]]; then
        $MINIMAP --MD -L -t "$NUM_THREADS" -ax map-ont "$motif_fa_file" "$intersected_fq" -o "$motif_mapped_sam"
    elif [[ "$READ_TYPE" == "pb" ]]; then
        $MINIMAP --MD -L -t "$NUM_THREADS" -ax map-pb "$motif_fa_file" "$intersected_fq" -o "$motif_mapped_sam"
    fi

    # Step 3: Convert SAM to sorted, indexed BAM
    printf "## Step 3/5: Sorting and indexing motif alignments...\n"
    $SAMTOOLS view -S -b "$motif_mapped_sam" -o "$motif_mapped_bam"
    $SAMTOOLS sort -o "$motif_mapped_sorted_bam" "$motif_mapped_bam"
    $SAMTOOLS index "$motif_mapped_sorted_bam"

    # Step 4: Call SNVs with xatlas
    printf "## Step 4/5: Calling SNVs with xatlas...\n"
    $XATLAS \
        -r "$motif_fa_file" \
        -i "$motif_mapped_sorted_bam" \
        -s "$OUTPUT_DIR/SNVcalls/${bed_fname}_${bam_name}" \
        -p "$OUTPUT_DIR/SNVcalls/${bed_fname}_${bam_name}"

    # Step 5: Count and normalize STR alleles
    printf "## Step 5/5: Counting and normalizing STR alleles...\n"
    local allele_freq_file="$OUTPUT_DIR/Countings/${bed_fname}_${bam_name}_Allele_freqs.txt"
    $SAMTOOLS view -q 1 -F 2308 "$motif_mapped_sorted_bam" |
        cut -f 3 |
        sort |
        uniq -c |
        sed -e 's/^ *//;s/ /\t/' |
        grep -v '*' |
        sort -nr -k1,1 > "$allele_freq_file"

    # Normalize with maximum value of Allele counts
    awk 'FNR==NR{max=($1+0>max)?$1:max;next} {print $2"\t"$1"\t"$1/max}' \
        "$allele_freq_file" "$allele_freq_file" > "${allele_freq_file}.tmp" && mv "${allele_freq_file}.tmp" "$allele_freq_file"
    
    # Add header (portable method)
    { echo -e "STR\tRawCounts\tNormalizedCounts"; cat "$allele_freq_file"; } > "${allele_freq_file}.tmp" && mv "${allele_freq_file}.tmp" "$allele_freq_file"

	# --- Determine effective (per-locus) normalization cutoff ---
	# Default to the global cutoff from InputConfig.
	# If a TSV overrides file is provided via NORM_CUTOFF_OVERRIDES, and it contains
	# an entry for this locus (bed_fname), that value will be used instead.
	local effective_norm_cutoff="$NORM_CUTOFF"
	if [[ -n "${NORM_CUTOFF_OVERRIDES:-}" && -f "$NORM_CUTOFF_OVERRIDES" ]]; then
	    # Expect 2 columns: <LOCUS> <CUTOFF>. Ignore comments/blank lines.
	    # awk returns empty string if locus not found; keep global in that case.
	    local override_val
	    override_val=$(awk -v locus="$bed_fname" 'NF && $1 !~ /^#/ && $1==locus {print $2; exit}' "$NORM_CUTOFF_OVERRIDES")
	    if [[ -n "$override_val" ]]; then
	        effective_norm_cutoff="$override_val"
	    fi
	fi

	# Get top two alleles by filtering
	printf "### Filtering for top two alleles (Normalized count >= %s)...\n" "$effective_norm_cutoff"
    local toptwo_file="$OUTPUT_DIR/Countings/${bed_fname}_${bam_name}_Toptwo.txt"
    sed '1d' "$allele_freq_file" |
	    awk -v f="$effective_norm_cutoff" '$3>=f' |
        tr '_' ' ' |
        sed 's/\]/] /g' |
        awk '{print $1"\t"$(NF-2)"\t"$NF}' |
        sort -r -k3,3 |
        head -n 2 > "$toptwo_file"

    # Add header (portable method)
    { echo -e "Locus\tAllele\tNormalizedCounts"; cat "$toptwo_file"; } > "${toptwo_file}.tmp" && mv "${toptwo_file}.tmp" "$toptwo_file"

    printf "## Done processing locus %s for sample %s.\n" "$bed_fname" "$bam_name"
}


# --- Main Script Logic ---

# Initial check for arguments before starting the log
if [[ $# -ne 2 ]]; then
    printf "#ERROR: Please provide the path to the Input and Tool config files.\n\n"
    print_USAGE
    exit 1
fi

input_config="$1"
tools_config="$2"

# Validate that config files exist before sourcing them
if [[ ! -f "$input_config" ]]; then
    printf "\n#ERROR: Input config file not found at: '%s'\n" "$input_config"; print_USAGE; exit 1;
fi
if [[ ! -f "$tools_config" ]]; then
    printf "\n#ERROR: Tools config file not found at: '%s'\n" "$tools_config"; print_USAGE; exit 1;
fi

# Source the config files to load variables
# Use grep to remove commented lines and filter for lines with '=' to avoid sourcing issues
source <(grep -v '^#' "$input_config" | grep '=')
source <(grep -v '^#' "$tools_config" | grep '=')

# Optional: per-locus Norm_cutoff overrides (TSV)
# If provided, this must be a readable file with 2 columns: <LOCUS> <CUTOFF>
# (comments/blank lines allowed). If empty/unset, the global NORM_CUTOFF applies.
if [[ -n "${NORM_CUTOFF_OVERRIDES:-}" ]]; then
    if [[ ! -f "$NORM_CUTOFF_OVERRIDES" ]]; then
        printf "\n#ERROR: 'NORM_CUTOFF_OVERRIDES' is set but is not a readable file: %s\n" "$NORM_CUTOFF_OVERRIDES"
        printf "       Expected a TSV file with columns: <LOCUS><TAB><CUTOFF>\n"
        exit 1
    fi
fi

# Validate OUTPUT_DIR before setting up logging
if [[ -z "$OUTPUT_DIR" ]]; then
    printf "\n#ERROR: 'OUTPUT_DIR' variable not set in your InputConfig file.\n"; exit 1;
fi
# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# --- LOGGING SETUP ---
# Now that OUTPUT_DIR is confirmed, redirect all subsequent output (stdout and stderr) to a log file.
exec &> >(tee -a "$OUTPUT_DIR/MaSTRspyLogParallel.log")

# The rest of the script will now log to the console and the file automatically.
{
    printf "Configurations loaded successfully.\n"

    # --- USER CONFIGURABLE PARAMETERS (can be set in script or InputConfig) ---
    NUM_PARALLEL_JOBS=${NUM_PARALLEL_JOBS:-8}
    NUM_THREADS=${NUM_THREADS:-16}

    # Validate crucial variables from config files
    if [[ ! -d "$INPUT_DIR" ]]; then
        printf "\n#ERROR: Input directory from config ('%s') does not exist!\n" "$INPUT_DIR"; exit 1;
    fi
    if ! command -v "$PARALLEL" &> /dev/null; then
        printf "\n#ERROR: GNU Parallel command ('%s') not found or not executable. Please install it or check your tools config.\n" "$PARALLEL"; exit 1;
    fi

    printf "========================================================\n"
    printf "Arguments are valid. Starting MaSTRspy P1.0 analysis.\n"
    printf "Analysis date and time: %s\n" "$(date)"
    printf "========================================================\n"
    printf "Input read dir: %s\n" "$INPUT_DIR"
    printf "Input type: %s\n" "$( [[ "$INPUT_BAM" == "yes" ]] && echo "bam" || echo "fastq" )"
    printf "Read Technology: %s\n" "$READ_TYPE"
    printf "Parallel Jobs: %d\n" "$NUM_PARALLEL_JOBS"
    printf "Threads per Job: %d\n" "$NUM_THREADS"
    printf "Output dir: %s\n" "$OUTPUT_DIR"
	if [[ -n "${NORM_CUTOFF_OVERRIDES:-}" ]]; then
	    printf "Norm_cutoff overrides TSV: %s\n" "$NORM_CUTOFF_OVERRIDES"
	else
	    printf "Norm_cutoff overrides TSV: (none)\n"
	fi
    printf "Log File: %s/MaSTRspyLogParallel.log\n" "$OUTPUT_DIR"
    printf "========================================================\n"

    # Check for existence of read files
    input_file_type=""
    if [[ "$INPUT_BAM" == "yes" ]]; then
        if ! ls "$INPUT_DIR"/*.bam &> /dev/null; then
            printf "\n#ERROR: No .bam files found in '%s'.\n" "$INPUT_DIR"; exit 1;
        fi
        input_file_type="bam"
    else # is_input_bam == "no"
        if ! ls "$INPUT_DIR"/*.fastq &> /dev/null && ! ls "$INPUT_DIR"/*.fastq.gz &> /dev/null ; then
            printf "\n#ERROR: No .fastq or .fastq.gz files found in '%s'.\n" "$INPUT_DIR"; exit 1;
        fi
        input_file_type="fastq"
    fi
    
    # Create output sub-directories
    mkdir -p "$OUTPUT_DIR"/{IntersectMappedReads,Countings,SNVcalls,GenomeMapping,GenomicMappingStats}
    
    # --- STEP 1: GENOMIC MAPPING (for FASTQ input) ---
    if [[ "$input_file_type" == "fastq" ]]; then
        printf "\n# STEP 1: Mapping FASTQ reads to reference genome (using %d parallel jobs)...\n" "$NUM_PARALLEL_JOBS"
        map_preset=""
        [[ "$READ_TYPE" == "ont" ]] && map_preset="map-ont" || map_preset="map-pb"

        find "$INPUT_DIR" -name "*.fastq" -o -name "*.fastq.gz" | \
            $PARALLEL -j"$NUM_PARALLEL_JOBS" --bar \
            "$MINIMAP --MD -L -t $NUM_THREADS -ax $map_preset \"$GENOME_FASTA\" {} | $SAMTOOLS sort -@$NUM_THREADS -o \"$OUTPUT_DIR/GenomeMapping/{/.}.sorted.bam\" && $SAMTOOLS index \"$OUTPUT_DIR/GenomeMapping/{/.}.sorted.bam\""
        
        printf "# Genome mapping complete.\n"
    fi

    # --- MAPPING STATS ---
    printf "\n# Calculating mapping statistics...\n"
    bam_dir_for_stats=""
    if [[ "$INPUT_BAM" == "yes" ]]; then
        printf "Input is BAM. Ensuring all are sorted and indexed...\n"
        find "$INPUT_DIR" -name "*.bam" | $PARALLEL -j"$NUM_PARALLEL_JOBS" "if [ ! -f {}.bai ]; then $SAMTOOLS index {}; fi"
        bam_dir_for_stats=$INPUT_DIR
    else
        bam_dir_for_stats="$OUTPUT_DIR/GenomeMapping"
    fi
    get_cov "$bam_dir_for_stats" "$OUTPUT_DIR/GenomicMappingStats" "$REGION_BED"
    printf "# Mapping statistics complete.\n"

    # --- STEP 2: SPYING ON STRS (Massively Parallel) ---
    printf "\n^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"
    printf "# STEP 2: Spying on STRs for each sample (using %d parallel jobs)...\n" "$NUM_PARALLEL_JOBS"
    printf "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"

    # Define the path to BAM files to process
    bam_files_to_process_path="$bam_dir_for_stats"

    # Set up a single parent temporary directory for all parallel jobs
    PARENT_TEMP_DIR=$(mktemp -d -p "$OUTPUT_DIR" "Mastrspy_parallel_temp.XXXXXX")
    trap 'printf "\nCleaning up temporary files from %s...\n" "$PARENT_TEMP_DIR"; rm -rf "${PARENT_TEMP_DIR}"' EXIT
    printf "Parent temporary directory for all jobs: %s\n" "$PARENT_TEMP_DIR"

    # Export variables and functions to make them available to parallel jobs
    export -f process_locus_for_sample get_cov
	export OUTPUT_DIR READ_TYPE STR_FASTA NUM_THREADS NORM_CUTOFF NORM_CUTOFF_OVERRIDES BEDTOOLS SAMTOOLS MINIMAP XATLAS

    # Create file lists for parallel processing
    readarray -t bam_files < <(find "$bam_files_to_process_path" -name "*.sorted.bam" -o -name "*.bam")
    readarray -t bed_files < <(find "$STR_BED" -name "*.bed")

    # Main processing loop using GNU Parallel for massive speedup
    $PARALLEL --bar --joblog "$OUTPUT_DIR/parallel_joblog.txt" -j "$NUM_PARALLEL_JOBS" \
        "process_locus_for_sample {1} {2} \$(mktemp -d -p '$PARENT_TEMP_DIR')" \
        ::: "${bam_files[@]}" ::: "${bed_files[@]}"
        
        
# This script organizes files into barcode-specific subdirectories.
# Ensure the OUTPUT_DIR variable is set before this runs.

# Exit immediately if a command exits with a non-zero status.
# set -e  <-- This line is already at the top of your main script, no need to repeat.

# Define the target directory
COUNTING_DIR="$OUTPUT_DIR/Countings"

echo "--- Starting File Organization in '$COUNTING_DIR' ---"

# Navigate to the correct directory, or exit if it doesn't exist.
cd "$COUNTING_DIR" || { echo "Error: Directory '$COUNTING_DIR' not found." >&2; exit 1; }

## 1. Remove Files
echo "Removing files ending with 'Toptwo.txt'..."
# Use find to safely delete only files matching the pattern in the current directory.
find . -maxdepth 1 -type f -name "*Toptwo.txt" -delete
echo "Cleanup complete."

# ---

## 2. Create Directories
echo "Creating directories from barcode01 to barcode24..."
# Create all directories at once. The '-p' flag prevents errors if they already exist.
for i in $(seq -w 1 24); do
    mkdir -p "barcode$i"
done
# Create the directory for unclassified files
mkdir -p "unclassified"
echo "Directories are ready."

# ---

## 3. Sort & Move Files
echo "Sorting files into corresponding barcode directories..."
# Loop through all items in the directory.
for file in *; do
    # FIX: This line tells the loop to skip any item that is a directory.
    [ -d "$file" ] && continue

    # Use a regular expression to find the 'barcodeXX' pattern in the filename.
    if [[ "$file" =~ (barcode[0-9]{2}) ]]; then
        # The matched pattern (e.g., "barcode09") becomes the directory name.
        DEST_DIR="${BASH_REMATCH[1]}"

        # Check if the destination is a valid directory before moving.
        if [ -d "$DEST_DIR" ]; then
            echo "Moving '$file' -> '$DEST_DIR/'"
            mv "$file" "$DEST_DIR/"
        fi
    fi
done
# ---

## 4. Move Unclassified Files
echo "Moving unclassified text files..."
# Loop through all .txt files containing the word "unclassified"
for file in *unclassified*.txt; do
    # This check prevents errors if no files are found and ensures we only move actual files
    [ -f "$file" ] || continue
    echo "Moving '$file' -> 'unclassified/'"
    mv "$file" "unclassified/"
done
echo "Unclassified files sorted."

echo "--- All files have been sorted. ---"

# --- STEP 4: GENERATE SUMMARIES ---
echo "--- Starting Summary Generation ---"

# Navigate back to the Countings directory to run the summary logic
cd "$OUTPUT_DIR/Countings" || { echo "Error: Could not navigate to '$OUTPUT_DIR/Countings' to generate summaries." >&2; exit 1; }

# 1. Create the Summaries directory
mkdir -p Summaries

# 2. Loop through each barcode directory and process its files
for barcode_dir in barcode*/; do
    # Ensure it is a directory
    if [ -d "$barcode_dir" ]; then
        barcode_name=$(basename "$barcode_dir")
        output_summary="Summaries/${barcode_name}_summary.tsv"
        
        # Add a header to each individual summary file
        echo -e "Barcode\tLocus\tCE_Number\tMotif\tRawCounts\tNormalizedCounts" > "$output_summary"

        # Process each allele frequency file within the barcode directory
        for locus_file in "$barcode_dir"/*_Allele_freqs.txt; do
            if [ -f "$locus_file" ]; then
                locus_name=$(basename "$locus_file" | cut -d'_' -f1)

                # Use awk to extract and reformat the data, appending to the summary
                awk -v barcode="$barcode_name" -v locus="$locus_name" '
                BEGIN { OFS="\t" }
                NR > 1 {
                    # Extract CE Number
                    match($1, /CE[0-9]+(\.[0-9]+)?/)
                   ce_num = substr($1, RSTART, RLENGTH)
                    sub(/CE/, "", ce_num)

                    # Extract Motif
                    match($1, /\[.*/)
                    motif = substr($1, RSTART)

                    # Print the formatted output
                    print barcode, locus, ce_num, motif, $2, $3
                }
                ' "$locus_file" >> "$output_summary"
            fi
        done
    fi
done



echo "--- Summaries created in the 'Summaries' directory. ---"

# --- STEP 4.5: GENERATE BARCODE PROFILES (TOP 2 ALLELES WITH FLAGGING) ---
echo "--- Starting Barcode Profile Generation ---"

# Loop through each barcode directory and generate profile
for barcode_dir in barcode*/; do
    if [ -d "$barcode_dir" ]; then
        barcode_name=$(basename "$barcode_dir")
        profile_file="Summaries/${barcode_name}_Profile.tsv"
        
        # Add header
        echo -e "Barcode\tLocus\tAllele_Rank\tCE_Number\tMotif\tRawCounts\tNormalizedCounts\tStatus" > "$profile_file"
        
        # Process each allele frequency file
        for locus_file in "$barcode_dir"/*_Allele_freqs.txt; do
            if [ -f "$locus_file" ]; then
                locus_name=$(basename "$locus_file" | cut -d'_' -f1)
                
                # Determine effective normalization cutoff for this locus
                effective_norm_cutoff="$NORM_CUTOFF"
                if [[ -n "${NORM_CUTOFF_OVERRIDES:-}" && -f "$NORM_CUTOFF_OVERRIDES" ]]; then
                    override_val=$(awk -v locus="$locus_name" 'NF && $1 !~ /^#/ && $1==locus {print $2; exit}' "$NORM_CUTOFF_OVERRIDES")
                    if [[ -n "$override_val" ]]; then
                        effective_norm_cutoff="$override_val"
                    fi
                fi
                
                # Extract top 2 alleles and flag if below threshold
                awk -v barcode="$barcode_name" -v locus="$locus_name" -v cutoff="$effective_norm_cutoff" '
                BEGIN { OFS="\t"; rank=0 }
                NR > 1 {
                    rank++
                    if (rank > 2) exit  # Only process top 2
                    
                    # Extract CE Number
                    match($1, /CE[0-9]+(\.[0-9]+)?/)
                    ce_num = substr($1, RSTART, RLENGTH)
                    sub(/CE/, "", ce_num)
                    
                    # Extract Motif
                    match($1, /\[.*/)
                    motif = substr($1, RSTART)
                    
                    # Determine status
                    norm_count = $3 + 0  # Convert to number
                    cutoff_num = cutoff + 0
                    
                    if (norm_count >= cutoff_num) {
                        status = "PASS"
                    } else {
                        status = "FLAGGED (Below " cutoff ")"
                    }
                    
                    # Print profile entry
                    print barcode, locus, rank, ce_num, motif, $2, $3, status
                }
                ' "$locus_file" >> "$profile_file"
            fi
        done
        
        echo "  Generated profile for $barcode_name"
    fi
done

echo "--- Barcode Profiles created in the 'Summaries' directory. ---"

    printf "\n========================================================\n"
    printf "All analyses are complete.\n"
    
    # --- STEP 5: RUN R SCRIPT FOR EACH BARCODE ---
echo "--- Starting R script for each barcode summary ---"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R_SCRIPT_PATH="$SCRIPT_DIR/STR_Profile_Plots_P1.0.R"
LOGO_PATH="$SCRIPT_DIR/logo.jpg"
SUMMARIES_DIR="$OUTPUT_DIR/Countings/Summaries"
PLOTS_DIR="$SUMMARIES_DIR/Plots"

# Create a directory to store the output plots
mkdir -p "$PLOTS_DIR"

# Check if the R script exists before starting the loop
if [ ! -f "$R_SCRIPT_PATH" ]; then
    echo "Warning: R script '$R_SCRIPT_PATH' not found. Skipping."
else
    # Loop through each individual barcode summary file
    for summary_file in "$SUMMARIES_DIR"/barcode*_summary.tsv; do
        # Check if the file exists and has content
        [ -s "$summary_file" ] || continue

        echo "Running R analysis on: $(basename "$summary_file")"
        
        # Define a unique output name for the plot based on the input file
        output_name=$(basename "$summary_file" _summary.tsv)
        output_plot_path="$PLOTS_DIR/${output_name}_plot.png"

        # Run Rscript, passing the input summary, output path, and logo path
        if [ -f "$LOGO_PATH" ]; then
            Rscript "$R_SCRIPT_PATH" "$summary_file" "$output_plot_path" "$LOGO_PATH"
        else
            # Run without logo if not found
            Rscript "$R_SCRIPT_PATH" "$summary_file" "$output_plot_path"
        fi
    done
    echo "--- R analysis complete for all barcodes. ---"
fi
    
    
    duration=$SECONDS
    printf "Total time elapsed: %d minutes and %d seconds.\n" "$(($duration / 60))" "$(($duration % 60))"
    printf "Log file saved to: %s/MaSTRspyLogParallel.log\n" "$OUTPUT_DIR"
    printf "Parallel job log saved to: %s/parallel_joblog.txt\n" "$OUTPUT_DIR"
    printf "SUMMARY REPORT: %s/Countings/Summaries/\n" "$OUTPUT_DIR"
    printf "  - barcode##_summary.tsv: All alleles per barcode\n"
    printf "  - barcode##_Profile.tsv: Top 2 alleles per locus (flagged if below threshold)\n"
    printf "  - Plots/: Visualization plots for each barcode\n"
    printf "========================================================\n"
}
