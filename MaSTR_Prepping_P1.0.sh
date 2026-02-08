#!/bin/bash
set -e -o pipefail

# --- Default Values ---
INPUT_DIR=""
OUTPUT_DIR=""
REFERENCE_GENOME=""
EXP_NAME="experiment"
INPUT_TYPE="bam"  # Input file type: bam or fastq
MIN_DORADO_Q=0    # Minimum Dorado basecaller quality score - qs tag (0 = no filtering)
MIN_MEAN_Q=0      # Minimum mean quality score (0 = no filtering)
MIN_LEN=0         # Minimum read length (0 = no filtering)
MIN_ACC=0         # Minimum alignment accuracy (0 = no filtering)

# --- Parse Command-Line Arguments ---
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --input) INPUT_DIR="$2"; shift ;;
        --output) OUTPUT_DIR="$2"; shift ;;
        --ref) REFERENCE_GENOME="$2"; shift ;;
        --exp_name) EXP_NAME="$2"; shift ;;
        --input-type) INPUT_TYPE="$2"; shift ;;
        --min-dorado-q) MIN_DORADO_Q="$2"; shift ;;
        --min-mean-q) MIN_MEAN_Q="$2"; shift ;;
        --min-len) MIN_LEN="$2"; shift ;;
        --min-acc) MIN_ACC="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# --- Validate Inputs ---
if [[ -z "$INPUT_DIR" ]] || [[ -z "$OUTPUT_DIR" ]] || [[ -z "$REFERENCE_GENOME" ]]; then
    echo "Usage: $0 --input <dir> --output <dir> --ref <file.mmi> --exp_name <n> [options]"
    echo ""
    echo "Required arguments:"
    echo "  --input <dir>       Input directory containing BAM or FASTQ files"
    echo "  --output <dir>      Output directory for prepped files"
    echo "  --ref <file>        Reference genome index (.mmi)"
    echo "  --exp_name <n>      Experiment name prefix"
    echo ""
    echo "Input options:"
    echo "  --input-type <type>   Input file type: bam or fastq (default: bam)"
    echo ""
    echo "Filtering options:"
    echo "  --min-dorado-q <float>  Minimum Dorado basecaller qs tag score (default: 0, no filtering)"
    echo "  --min-mean-q <float>    Minimum mean quality score (default: 0, no filtering)"
    echo "  --min-len <int>         Minimum read length (default: 0, no filtering)"
    echo "  --min-acc <float>       Minimum alignment accuracy 0.0-1.0 (default: 0, no filtering)"
    exit 1
fi

# --- Validate input type ---
if [[ "$INPUT_TYPE" != "bam" ]] && [[ "$INPUT_TYPE" != "fastq" ]]; then
    echo "[ERROR] Invalid input type: $INPUT_TYPE. Must be 'bam' or 'fastq'."
    exit 1
fi

# --- Create Output Directory ---
mkdir -p "$OUTPUT_DIR"

echo "========================================"
echo "MaSTR_Prepping P1.0 Started"
echo "========================================"
echo "Input directory: $INPUT_DIR"
echo "Output directory: $OUTPUT_DIR"
echo "Reference genome: $REFERENCE_GENOME"
echo "Experiment name: $EXP_NAME"
echo "Input type: $INPUT_TYPE"
echo "----------------------------------------"
echo "Filtering parameters:"
echo "  Min Dorado qs tag: $MIN_DORADO_Q"
echo "  Min mean quality: $MIN_MEAN_Q"
echo "  Min read length: $MIN_LEN"
echo "  Min accuracy: $MIN_ACC"
echo "========================================"

# =============================================================================
# EMBEDDED PYTHON: Dorado qs Tag Filter (BAM only, runs first)
# =============================================================================
dorado_qs_filter() {
    local in_bam="$1"
    local out_bam="$2"
    local min_qs="$3"
    
    python3 - "$in_bam" "$out_bam" "$min_qs" << 'DORADO_QS_FILTER_EOF'
import sys
import pysam

in_bam = sys.argv[1]
out_bam = sys.argv[2]
min_qs = float(sys.argv[3])

passed = 0
filtered = 0
no_tag_count = 0
tag_found = False

inp = pysam.AlignmentFile(in_bam, "rb", check_sq=False)
out = pysam.AlignmentFile(out_bam, "wb", template=inp)

for r in inp.fetch(until_eof=True):
    try:
        # Try to get the qs tag (can be float or int)
        qs_value = r.get_tag("qs")
        tag_found = True
        if qs_value >= min_qs:
            out.write(r)
            passed += 1
        else:
            filtered += 1
    except KeyError:
        # qs tag not found - pass the read through
        no_tag_count += 1
        out.write(r)
        passed += 1

inp.close()
out.close()

if not tag_found and no_tag_count > 0:
    print(f"[WARNING] Dorado 'qs' tag not found in any reads. Filter not applied.", file=sys.stderr)
    print(f"[dorado_qs_filter] All {passed} reads passed (no qs tag available)", file=sys.stderr)
elif no_tag_count > 0:
    print(f"[WARNING] {no_tag_count} reads missing 'qs' tag (passed through)", file=sys.stderr)
    print(f"[dorado_qs_filter] Passed: {passed}, Filtered: {filtered}", file=sys.stderr)
else:
    print(f"[dorado_qs_filter] Passed: {passed}, Filtered: {filtered}", file=sys.stderr)
DORADO_QS_FILTER_EOF
}

# =============================================================================
# EMBEDDED PYTHON: Dorado qs Tag Filter for FASTQ (reads from stdin, writes to stdout)
# =============================================================================
dorado_qs_filter_fastq() {
    local min_qs="$1"
    
    python3 - "$min_qs" << 'DORADO_QS_FASTQ_FILTER_EOF'
import sys
import re

min_qs = float(sys.argv[1])

passed = 0
filtered = 0
no_tag_count = 0
tag_found = False

# Regex patterns to match qs tag in FASTQ header
# Matches: qs:f:12.5 or qs:i:12 or qs=12.5
qs_pattern = re.compile(r'qs[:=][fi]?:?(\d+\.?\d*)')

while True:
    header = sys.stdin.readline()
    if not header:
        break
    seq = sys.stdin.readline().rstrip("\n")
    plus = sys.stdin.readline()
    qual = sys.stdin.readline().rstrip("\n")
    
    if not qual:
        break
    
    # Try to extract qs value from header
    match = qs_pattern.search(header)
    
    if match:
        tag_found = True
        qs_value = float(match.group(1))
        if qs_value >= min_qs:
            sys.stdout.write(header)
            sys.stdout.write(seq + "\n")
            sys.stdout.write(plus)
            sys.stdout.write(qual + "\n")
            passed += 1
        else:
            filtered += 1
    else:
        # No qs tag found - pass the read through
        no_tag_count += 1
        sys.stdout.write(header)
        sys.stdout.write(seq + "\n")
        sys.stdout.write(plus)
        sys.stdout.write(qual + "\n")
        passed += 1

if not tag_found and no_tag_count > 0:
    print(f"[WARNING] Dorado 'qs' tag not found in FASTQ headers. Filter not applied.", file=sys.stderr)
    print(f"[dorado_qs_filter_fastq] All {passed} reads passed (no qs tag available)", file=sys.stderr)
elif no_tag_count > 0:
    print(f"[WARNING] {no_tag_count} reads missing 'qs' tag in header (passed through)", file=sys.stderr)
    print(f"[dorado_qs_filter_fastq] Passed: {passed}, Filtered: {filtered}", file=sys.stderr)
else:
    print(f"[dorado_qs_filter_fastq] Passed: {passed}, Filtered: {filtered}", file=sys.stderr)
DORADO_QS_FASTQ_FILTER_EOF
}

# =============================================================================
# EMBEDDED PYTHON: FASTQ Quality/Length Filter
# =============================================================================
fastq_filter() {
    python3 - --min-mean-q "$MIN_MEAN_Q" --min-len "$MIN_LEN" << 'FASTQ_FILTER_EOF'
import sys
import argparse

def mean_q(qual: str) -> float:
    if not qual:
        return 0.0
    return sum((ord(c) - 33) for c in qual) / len(qual)

ap = argparse.ArgumentParser()
ap.add_argument("--min-mean-q", type=float, default=0.0)
ap.add_argument("--min-len", type=int, default=0)
args = ap.parse_args()

passed = 0
filtered = 0

while True:
    h = sys.stdin.readline()
    if not h:
        break
    s = sys.stdin.readline().rstrip("\n")
    p = sys.stdin.readline()
    q = sys.stdin.readline().rstrip("\n")
    if not q:
        break
    if len(s) < args.min_len:
        filtered += 1
        continue
    if mean_q(q) < args.min_mean_q:
        filtered += 1
        continue
    sys.stdout.write(h)
    sys.stdout.write(s + "\n")
    sys.stdout.write(p)
    sys.stdout.write(q + "\n")
    passed += 1

print(f"[fastq_filter] Passed: {passed}, Filtered: {filtered}", file=sys.stderr)
FASTQ_FILTER_EOF
}

# =============================================================================
# EMBEDDED PYTHON: BAM Accuracy Filter
# =============================================================================
bam_accuracy_filter() {
    local in_bam="$1"
    local out_bam="$2"
    local min_acc="$3"
    
    python3 - "$in_bam" "$out_bam" "$min_acc" << 'BAM_FILTER_EOF'
import sys
import pysam

in_bam = sys.argv[1]
out_bam = sys.argv[2]
min_acc = float(sys.argv[3])

def get_ins_del_from_cigar(read):
    ins = 0
    dels = 0
    if read.cigartuples is None:
        return None
    for op, length in read.cigartuples:
        if op == 1:
            ins += length
        elif op == 2:
            dels += length
    return ins, dels

def get_matches_mismatches_from_md(read):
    try:
        md = read.get_tag("MD")
    except KeyError:
        return None
    matches = 0
    mismatches = 0
    i = 0
    num = ""
    while i < len(md):
        c = md[i]
        if c.isdigit():
            num += c
            i += 1
            continue
        if num:
            matches += int(num)
            num = ""
        if c == "^":
            i += 1
            while i < len(md) and md[i].isalpha():
                i += 1
            continue
        if c.isalpha():
            mismatches += 1
            i += 1
            continue
        i += 1
    if num:
        matches += int(num)
    return matches, mismatches

passed = 0
filtered = 0
skipped = 0

inp = pysam.AlignmentFile(in_bam, "rb")
out = pysam.AlignmentFile(out_bam, "wb", template=inp)

for r in inp.fetch(until_eof=True):
    if r.is_unmapped:
        skipped += 1
        continue
    md = get_matches_mismatches_from_md(r)
    cd = get_ins_del_from_cigar(r)
    if md is None or cd is None:
        skipped += 1
        continue
    matches, mismatches = md
    ins, dels = cd
    denom = matches + mismatches + ins + dels
    if denom == 0:
        skipped += 1
        continue
    acc = matches / denom
    if acc >= min_acc:
        out.write(r)
        passed += 1
    else:
        filtered += 1

inp.close()
out.close()

print(f"[bam_accuracy_filter] Passed: {passed}, Filtered: {filtered}, Skipped: {skipped}")
BAM_FILTER_EOF
}

# =============================================================================
# MAIN PROCESSING LOOP
# =============================================================================

# Find input files based on type
shopt -s nullglob
if [[ "$INPUT_TYPE" == "bam" ]]; then
    INPUT_FILES=("$INPUT_DIR"/*.bam)
else
    INPUT_FILES=("$INPUT_DIR"/*.fastq "$INPUT_DIR"/*.fq)
fi
shopt -u nullglob

if [[ ${#INPUT_FILES[@]} -eq 0 ]]; then
    echo "[ERROR] No $INPUT_TYPE files found in $INPUT_DIR"
    exit 1
fi

for input_file in "${INPUT_FILES[@]}"; do
    if [[ -f "$input_file" ]]; then
        # Extract sample name from filename
        file_basename=$(basename "$input_file")
        # Remove extension
        if [[ "$INPUT_TYPE" == "bam" ]]; then
            sample_name="${file_basename%.bam}"
        else
            sample_name="${file_basename%.fastq}"
            sample_name="${sample_name%.fq}"
        fi
        
        # =====================================================================
        # Smart Barcode Extraction - Handles any input naming!
        # Looks for patterns like: barcode12, BC12, bc12, barcode_12, etc.
        # =====================================================================
        barcode_name=""
        
        # Try to extract barcode number from filename
        # Pattern 1: barcodeXX or barcode_XX (most common)
        if [[ "$sample_name" =~ barcode[_]?([0-9]{1,2}) ]]; then
            barcode_num="${BASH_REMATCH[1]}"
            # Pad to 2 digits
            barcode_name=$(printf "barcode%02d" "$barcode_num")
        
        # Pattern 2: BCXX or BC_XX
        elif [[ "$sample_name" =~ [Bb][Cc][_]?([0-9]{1,2}) ]]; then
            barcode_num="${BASH_REMATCH[1]}"
            barcode_name=$(printf "barcode%02d" "$barcode_num")
        
        # Pattern 3: Just numbers at end (assume barcode if between 1-96)
        elif [[ "$sample_name" =~ _([0-9]{1,2})$ ]]; then
            barcode_num="${BASH_REMATCH[1]}"
            if [ "$barcode_num" -ge 1 ] && [ "$barcode_num" -le 96 ]; then
                barcode_name=$(printf "barcode%02d" "$barcode_num")
            fi
        
        # Pattern 4: unclassified (from Dorado demux)
        elif [[ "$sample_name" =~ unclassified ]]; then
            barcode_name="unclassified"
        fi
        
        # Fallback: if no barcode detected, use original filename
        if [[ -z "$barcode_name" ]]; then
            echo "[WARNING] Could not detect barcode number in '$file_basename'"
            echo "          Using original filename as identifier"
            barcode_name="$sample_name"
        fi
        
        echo ""
        echo "--- Processing: $file_basename → $barcode_name ---"
        
        # Construct standardized output filenames
        qs_filtered_bam="$OUTPUT_DIR/${barcode_name}_qs_filtered.bam"
        aligned_bam="$OUTPUT_DIR/${barcode_name}_aligned.bam"
        final_bam="$OUTPUT_DIR/${barcode_name}_prepped.bam"

        # Track which file to use as input for the next stage
        current_input="$input_file"

        # ---------------------------------------------------------------------
        # STAGE 0: Dorado qs Tag Filter (BAM only, runs first if enabled)
        # ---------------------------------------------------------------------
        if [[ "$INPUT_TYPE" == "bam" ]] && (( $(echo "$MIN_DORADO_Q > 0" | bc -l) )); then
            echo "[INFO] Applying Dorado qs tag filter (min-dorado-q=$MIN_DORADO_Q)"
            dorado_qs_filter "$current_input" "$qs_filtered_bam" "$MIN_DORADO_Q"
            current_input="$qs_filtered_bam"
        fi

        # Determine if pre-alignment filtering is needed
        APPLY_PRE_FILTER=false
        if (( $(echo "$MIN_MEAN_Q > 0 || $MIN_LEN > 0" | bc -l) )); then
            APPLY_PRE_FILTER=true
        fi

        # Build pipeline based on input type and filtering
        if [[ "$INPUT_TYPE" == "bam" ]]; then
            # BAM input: need samtools fastq first
            if [[ "$APPLY_PRE_FILTER" == true ]]; then
                echo "[INFO] Applying pre-alignment filters (min-mean-q=$MIN_MEAN_Q, min-len=$MIN_LEN)"
                samtools fastq -@4 "$current_input" 2>/dev/null | \
                fastq_filter | \
                minimap2 -ax map-ont --MD -t 32 "$REFERENCE_GENOME" - 2>/dev/null | \
                samtools sort -@4 -o "$aligned_bam" -
            else
                echo "[INFO] No pre-alignment filtering"
                samtools fastq -@4 "$current_input" 2>/dev/null | \
                minimap2 -ax map-ont --MD -t 32 "$REFERENCE_GENOME" - 2>/dev/null | \
                samtools sort -@4 -o "$aligned_bam" -
            fi
        else
            # FASTQ input: check if Dorado qs filter should be applied
            APPLY_DORADO_FILTER=false
            if (( $(echo "$MIN_DORADO_Q > 0" | bc -l) )); then
                APPLY_DORADO_FILTER=true
            fi
            
            # Build the pipeline based on which filters are enabled
            if [[ "$APPLY_DORADO_FILTER" == true ]] && [[ "$APPLY_PRE_FILTER" == true ]]; then
                echo "[INFO] Applying Dorado qs filter (min-dorado-q=$MIN_DORADO_Q) and pre-alignment filters (min-mean-q=$MIN_MEAN_Q, min-len=$MIN_LEN)"
                cat "$input_file" | \
                dorado_qs_filter_fastq "$MIN_DORADO_Q" | \
                fastq_filter | \
                minimap2 -ax map-ont --MD -t 32 "$REFERENCE_GENOME" - 2>/dev/null | \
                samtools sort -@4 -o "$aligned_bam" -
            elif [[ "$APPLY_DORADO_FILTER" == true ]]; then
                echo "[INFO] Applying Dorado qs filter (min-dorado-q=$MIN_DORADO_Q)"
                cat "$input_file" | \
                dorado_qs_filter_fastq "$MIN_DORADO_Q" | \
                minimap2 -ax map-ont --MD -t 32 "$REFERENCE_GENOME" - 2>/dev/null | \
                samtools sort -@4 -o "$aligned_bam" -
            elif [[ "$APPLY_PRE_FILTER" == true ]]; then
                echo "[INFO] Applying pre-alignment filters (min-mean-q=$MIN_MEAN_Q, min-len=$MIN_LEN)"
                cat "$input_file" | \
                fastq_filter | \
                minimap2 -ax map-ont --MD -t 32 "$REFERENCE_GENOME" - 2>/dev/null | \
                samtools sort -@4 -o "$aligned_bam" -
            else
                echo "[INFO] No pre-alignment filtering"
                minimap2 -ax map-ont --MD -t 32 "$REFERENCE_GENOME" "$input_file" 2>/dev/null | \
                samtools sort -@4 -o "$aligned_bam" -
            fi
        fi

        # Clean up intermediate qs-filtered BAM if created
        if [[ -f "$qs_filtered_bam" ]]; then
            rm -f "$qs_filtered_bam"
        fi

        # Determine if post-alignment filtering is needed
        if (( $(echo "$MIN_ACC > 0" | bc -l) )); then
            echo "[INFO] Applying post-alignment accuracy filter (min-acc=$MIN_ACC)"
            bam_accuracy_filter "$aligned_bam" "$final_bam" "$MIN_ACC"
            rm -f "$aligned_bam"
        else
            echo "[INFO] No post-alignment filtering"
            mv "$aligned_bam" "$final_bam"
        fi

        # Index the final BAM
        samtools index "$final_bam"
        echo "--- Completed: ${final_bam} ---"
    fi
done

echo ""
echo "========================================"
echo "MaSTR_Prepping P1.0 Finished"
echo "Prepped files are in: $OUTPUT_DIR"
echo "========================================"
