library(ggplot2)
library(viridis)
library(grid)
library(png)

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 2) {
  stop("Usage: Rscript STR_Profile_Plots_P1.0.R <input_tsv_path> <output_plot_path> [logo_path]", call. = FALSE)
}

input_file <- args[1]
output_file <- args[2]
logo_path <- if (length(args) >= 3) args[3] else NULL

cat("----------------------------------------\n")
cat("Processing R analysis for:", basename(input_file), "\n")

plot_data <- read.delim(input_file, header = TRUE, sep = "\t")

autosomal_loci <- sort(unique(plot_data$Locus[!grepl("^DYS", plot_data$Locus)]))
y_loci <- sort(unique(plot_data$Locus[grepl("^DYS", plot_data$Locus)]))

locus_order <- c(autosomal_loci, y_loci)

plot_data$Locus <- factor(plot_data$Locus, levels = locus_order) 

if (nrow(plot_data) > 0) {
  
  current_barcode <- plot_data$Barcode[1]
  
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  
  stutter_plot <- ggplot(plot_data, aes(x = as.factor(CE_Number), y = RawCounts, fill = Locus)) +
    geom_col(show.legend = FALSE) +
    scale_fill_viridis_d() +
    facet_wrap(~ Locus, scales = "free", ncol = 9) +
    theme_bw() +
    labs(
      title = paste(current_barcode, "Profile"),
      x = "CE Number (Allele)",
      y = "Raw Counts"
    ) +
    theme(
      plot.title = element_text(hjust = 0.5, face = "bold", size = 16),
      plot.subtitle = element_text(hjust = 0.5),
      axis.text.x = element_text(angle = 90, vjust = 0.5, size = 6),
      plot.margin = margin(10, 10, 50, 10)
    )
  
  png(
    filename = output_file,
    width = 16,
    height = 10,
    units = "in",
    res = 300
  )
  
  print(stutter_plot)
  
  grid.text(
    label = paste("Generated:", timestamp),
    x = 0.98,
    y = 0.02,
    just = c("right", "bottom"),
    gp = gpar(fontsize = 10, col = "gray30", fontface = "italic")
  )
  
  if (!is.null(logo_path) && file.exists(logo_path)) {
    tryCatch({
      logo <- readPNG(logo_path)
      
      grid.raster(
        logo,
        x = 0.96,
        y = 0.06,
        width = 0.08,
        height = 0.08,
        just = c("right", "bottom")
      )
    }, error = function(e) {
      cat("Warning: Could not load logo:", e$message, "\n")
    })
  }
  
  dev.off()
  
  cat("Successfully saved plot to:", output_file, "\n")
  
} else {
  cat("Skipping plot for", basename(input_file), "because it contains no data.\n")
}

cat("----------------------------------------\n")
