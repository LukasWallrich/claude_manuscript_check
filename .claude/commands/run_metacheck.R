#!/usr/bin/env Rscript

# run_metacheck.R — Run metacheck modules on a manuscript PDF
#
# Usage: Rscript run_metacheck.R <pdf_path> [grobid_xml_path]
#
# Outputs structured JSON to stdout. Diagnostic messages go to stderr.
# Exit code 1 = metacheck not installed (JSON error on stdout).
# Exit code 0 = ran successfully (even if individual modules failed).

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 1) {
  cat('{"error": "No PDF path provided"}\n')
  quit(status = 1)
}

pdf_path <- args[1]
grobid_xml_path <- if (length(args) >= 2) args[2] else NULL

# Check metacheck is installed
if (!requireNamespace("metacheck", quietly = TRUE)) {
  cat('{"error": "metacheck not installed"}\n')
  quit(status = 1)
}

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  cat('{"error": "jsonlite not installed"}\n')
  quit(status = 1)
}

library(metacheck)
library(jsonlite)

metacheck_version <- tryCatch(
  as.character(packageVersion("metacheck")),
  error = function(e) "unknown"
)

message("metacheck version: ", metacheck_version)

# Convert PDF to GROBID XML or use provided XML
xml_file <- NULL

if (!is.null(grobid_xml_path) && file.exists(grobid_xml_path)) {
  message("Using provided GROBID XML: ", grobid_xml_path)
  xml_file <- grobid_xml_path
} else {
  message("Converting PDF to GROBID XML via metacheck...")
  xml_file <- tryCatch({
    pdf2grobid(pdf_path)
  }, error = function(e) {
    message("pdf2grobid failed: ", conditionMessage(e))
    NULL
  })
}

if (is.null(xml_file) || !file.exists(xml_file)) {
  cat(toJSON(list(
    error = "Failed to obtain GROBID XML",
    metacheck_version = metacheck_version
  ), auto_unbox = TRUE))
  cat("\n")
  quit(status = 0)
}

# Parse the XML into a paper object
paper <- tryCatch({
  read(xml_file)
}, error = function(e) {
  message("Failed to parse XML: ", conditionMessage(e))
  NULL
})

if (is.null(paper)) {
  cat(toJSON(list(
    error = "Failed to parse GROBID XML into paper object",
    metacheck_version = metacheck_version
  ), auto_unbox = TRUE))
  cat("\n")
  quit(status = 0)
}

# Define modules to run, grouped by category
modules <- list(
  # Statistical reporting
  stat_check = "stat_check",
  all_p_values = "all_p_values",
  marginal = "marginal",
  # Reference integrity
  ref_retraction = "ref_retraction",
  ref_pubpeer = "ref_pubpeer",
  ref_doi_check = "ref_doi_check",
  ref_consistency = "ref_consistency",
  # Open science & compliance
  open_practices = "open_practices",
  prereg_check = "prereg_check",
  coi_check = "coi_check",
  funding_check = "funding_check",
  # Informational
  all_urls = "all_urls",
  causal_claims = "causal_claims"
)

results <- list()
modules_run <- character(0)
modules_failed <- list()

for (name in names(modules)) {
  module_name <- modules[[name]]
  message("Running module: ", module_name)

  result <- tryCatch({
    res <- module_run(paper, module_name)
    modules_run <<- c(modules_run, name)

    # Extract the key outputs from the module result
    output <- list()
    if (!is.null(res$table)) {
      output$table <- res$table
    }
    if (!is.null(res$summary_table)) {
      output$summary_table <- res$summary_table
    }
    if (!is.null(res$traffic_light)) {
      output$traffic_light <- res$traffic_light
    }
    if (!is.null(res$summary_text)) {
      output$summary_text <- res$summary_text
    }
    if (!is.null(res$report)) {
      output$report <- res$report
    }
    output
  }, error = function(e) {
    message("Module ", module_name, " failed: ", conditionMessage(e))
    modules_failed[[length(modules_failed) + 1]] <<- list(
      module = name,
      error = conditionMessage(e)
    )
    NULL
  })

  if (!is.null(result)) {
    results[[name]] <- result
  }
}

# Sanitize objects that jsonlite can't serialize (e.g., bibentry, person)
sanitize_for_json <- function(x) {
  if (is.null(x)) return(NULL)
  if (inherits(x, "bibentry") || inherits(x, "person")) {
    return(format(x, style = "text"))
  }
  if (is.data.frame(x)) {
    for (col in names(x)) {
      x[[col]] <- sanitize_for_json(x[[col]])
    }
    return(x)
  }
  if (is.list(x)) {
    return(lapply(x, sanitize_for_json))
  }
  x
}

# Build output
output <- list(
  metacheck_version = metacheck_version,
  modules_run = modules_run,
  modules_failed = modules_failed,
  results = sanitize_for_json(results)
)

cat(toJSON(output, auto_unbox = TRUE, pretty = TRUE, null = "null"))
cat("\n")
