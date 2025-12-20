# Load required libraries
library(dplyr)
library(ggplot2)
library(tidyr)
library(corrplot)


find_scale_variables <- function(data, min_items = 3, max_unique = 10, verbose = TRUE) {
  scale_vars <- c()

  # Find numeric columns with limited unique values (typical of Likert scales)
  for (col in names(data)) {
    if (is.numeric(data[[col]])) {
      # Count unique non-missing values
      non_missing <- data[[col]][!is.na(data[[col]])]
      unique_vals <- length(unique(non_missing))
      n_valid <- length(non_missing)

      # Check if it looks like a scale (2-10 unique values, and enough responses)
      if (unique_vals >= 2 && unique_vals <= max_unique && n_valid >= 10) {
        # Exclude certain variable types that aren't scales
        if (!grepl("^(id|time[0-9]|age|zip|finished|screen|q_|md_|gr$)", col)) {
          scale_vars <- c(scale_vars, col)
        }
      }
    }
  }

  # Extract prefixes (everything before the last _number pattern)
  prefixes <- unique(gsub("_[0-9]+[a-z]*$", "", scale_vars))

  # Filter to groups with minimum number of items
  valid_prefixes <- c()
  scale_batteries <- list()

  for (prefix in prefixes) {
    # items <- scale_vars[grepl(paste0("^", prefix, "_[0-9]"), scale_vars)]
    items <- scale_vars[grepl(paste0("^", prefix, "_[0-9]+"), scale_vars)]
    if (length(items) >= min_items) {
      valid_prefixes <- c(valid_prefixes, prefix)
      scale_batteries[[prefix]] <- items
    }
  }

  # Return all variables from valid scale batteries
  final_vars <- c()
  for (prefix in valid_prefixes) {
    final_vars <- c(final_vars, scale_batteries[[prefix]])
  }

  if (verbose && length(final_vars) > 0) {
    cat(sprintf("Found %d scale variables from %d scale batteries:\n",
                length(final_vars), length(valid_prefixes)))
    for (prefix in valid_prefixes) {
      cat(sprintf("  - %s: %d items\n", prefix, length(scale_batteries[[prefix]])))
    }
    cat("\n")
  } else if (verbose) {
    cat("No scale variables detected\n\n")
  }

  return(final_vars)
}

# Threshold should be always 1.0 as mentioned in  (Leiner, 2019).
detect_straightlining <- function(data, scale_vars, threshold = 1.0, verbose = TRUE) {
  straightline_flags <- data.frame(id = data$id, straightline = FALSE)

  if(length(scale_vars) > 0) {
    # Track coverage metrics
    n_respondents_total <- nrow(data)
    n_got_questions <- 0  # People who got >2 questions where response != -2
    n_straightliners <- 0
    n_straightliners_got_questions <- 0  # ADD THIS: Straightliners who also got >2 questions

    # Per-question coverage
    question_coverage <- data.frame(
      question = scale_vars,
      n_got_question = 0,
      pct_got_question = 0,
      n_answered = 0,
      pct_answered = 0
    )

    # Calculate per-person straightlining
    for(i in 1:nrow(data)) {
      responses <- as.numeric(data[i, scale_vars])

      # Count how many questions they got (not -2)
      n_got_question <- sum(!is.na(responses) & responses != -2)

      # Track if this person got enough questions to assess
      got_enough_questions <- n_got_question > 2
      if(got_enough_questions) {
        n_got_questions <- n_got_questions + 1
      }

      # Count valid answers (not -2, -1, 0, NA)
      responses_valid <- responses[!is.na(responses) &
                                   responses != 0 &
                                   responses != -1 &
                                   responses != -2]

      # Only check straightlining if they answered >2 questions validly
      if(length(responses_valid) > 2) {
        # Most common response frequency
        max_freq <- max(table(responses_valid))
        prop_same <- max_freq / length(responses_valid)

        if(prop_same >= threshold) {
          straightline_flags$straightline[i] <- TRUE
          n_straightliners <- n_straightliners + 1

          # ADD THIS: Track if this straightliner also got >2 questions
          if(got_enough_questions) {
            n_straightliners_got_questions <- n_straightliners_got_questions + 1
          }
        }
      }
    }

    # Calculate per-question coverage
    for(j in 1:length(scale_vars)) {
      var <- scale_vars[j]
      if(var %in% names(data)) {
        n_got <- sum(!is.na(data[[var]]) & data[[var]] != -2)
        question_coverage$n_got_question[j] <- n_got
        question_coverage$pct_got_question[j] <- 100 * n_got / n_respondents_total

        n_answered <- sum(!is.na(data[[var]]) &
                         data[[var]] != 0 &
                         data[[var]] != -1 &
                         data[[var]] != -2)
        question_coverage$n_answered[j] <- n_answered
        question_coverage$pct_answered[j] <- 100 * n_answered / n_respondents_total
      }
    }

    # Print detailed statistics if verbose
    if(verbose) {
      cat("\n--- Straightlining Detection Results ---\n")
      cat(sprintf("Total respondents: %d\n", n_respondents_total))
      cat(sprintf("Respondents who got >2 questions: %d (%.1f%%)\n",
                  n_got_questions, 100 * n_got_questions / n_respondents_total))

      cat(sprintf("\nStraightliners detected: %d\n", n_straightliners))
      cat(sprintf("  • Of these, %d (%.1f%%) got >2 questions\n",
                  n_straightliners_got_questions,
                  100 * n_straightliners_got_questions / n_straightliners))
      cat(sprintf("  • %.1f%% of total respondents\n",
                  100 * n_straightliners / n_respondents_total))
      cat(sprintf("  • %.1f%% of those who got >2 questions\n",
                  100 * n_straightliners / n_got_questions))

      cat(sprintf("\nQuestion coverage:\n"))
      cat(sprintf("  • Average %.1f%% got each question (not -2)\n",
                  mean(question_coverage$pct_got_question, na.rm = TRUE)))
      cat(sprintf("  • Average %.1f%% answered each question validly\n",
                  mean(question_coverage$pct_answered, na.rm = TRUE)))

      # Show questions with lowest coverage
      low_cov <- question_coverage %>%
        arrange(pct_got_question) %>%
        head(3)
      cat("\nQuestions with lowest coverage (who got them):\n")
      for(i in 1:nrow(low_cov)) {
        cat(sprintf("  %s: %.1f%% got it, %.1f%% answered\n",
                    low_cov$question[i],
                    low_cov$pct_got_question[i],
                    low_cov$pct_answered[i]))
      }
      cat("\n")
    }

    # Store coverage data as attribute for later analysis
    attr(straightline_flags, "coverage_stats") <- question_coverage
    attr(straightline_flags, "summary_stats") <- list(
      n_total = n_respondents_total,
      n_got_questions = n_got_questions,
      n_straightliners = n_straightliners,
      n_straightliners_got_questions = n_straightliners_got_questions,
      pct_of_total = 100 * n_straightliners / n_respondents_total,
      pct_of_applicable = 100 * n_straightliners / n_got_questions
    )
  } else {
    straightline_flags$straightline <- FALSE
  }

  # In detect_straightlining function, add this before return:
  attr(straightline_flags, "straightline_summary_stats") <- list(
    n_total = n_respondents_total,
    n_got_questions = n_got_questions,
    n_straightliners = n_straightliners,
    n_straightliners_got_questions = n_straightliners_got_questions,
    pct_of_total = 100 * n_straightliners / n_respondents_total,
    pct_of_applicable = 100 * n_straightliners / n_got_questions
  )

  return(straightline_flags)
}



detect_inconsistencies <- function(data) {
  consistency_flags <- data.frame(
    id = data$id,
    inconsistent = FALSE,
    inconsistency_types = ""
  )

  # Helper function to append inconsistency type
  flag_inconsistency <- function(condition, type) {
    idx <- which(condition & !is.na(condition))
    consistency_flags$inconsistent[idx] <<- TRUE
    consistency_flags$inconsistency_types[idx] <<- ifelse(
      consistency_flags$inconsistency_types[idx] == "",
      type,
      paste(consistency_flags$inconsistency_types[idx], type, sep = "; ")
    )
  }

  # Age vs age group consistency
  # agegr: 1=18-34, 2=35-54, 3=55+
  if("age" %in% names(data) && "agegr" %in% names(data)) {
    age_inconsistent <- (data$age < 18 & data$agegr %in% c(1,2,3)) |  # Under 18 in adult category
                       (data$age >= 18 & data$age <= 34 & data$agegr != 1) |
                       (data$age >= 35 & data$age <= 54 & data$agegr != 2) |
                       (data$age >= 55 & data$agegr != 3)

    flag_inconsistency(age_inconsistent, "age_mismatch")
  }

  # Car ownership vs usage
  # mob2_1: number of cars, mob11a=1: uses private car for work
  if("mob2_1" %in% names(data) && "mob11a" %in% names(data)) {
    car_inconsistent <- (data$mob2_1 == 0 & data$mob11a == 1)
    flag_inconsistency(car_inconsistent, "no_car_but_uses_car")
  }

  # Motorbike ownership vs usage
  # mob2_2: number of motorbikes, mob11a=7: uses motorbike for work
  if("mob2_2" %in% names(data) && "mob11a" %in% names(data)) {
    motorbike_inconsistent <- (data$mob2_2 == 0 & data$mob11a == 7)
    flag_inconsistency(motorbike_inconsistent, "no_motorbike_but_uses_motorbike")
  }

  # Airplane travel vs spending
  # mob13_1, mob13_2: number of trips, mob14: spending on air travel
  if(all(c("mob13_1", "mob13_2", "mob14") %in% names(data))) {
    flight_inconsistent <- (data$mob13_1 == 0 & data$mob13_2 == 0 &
                           data$mob14 > 0 & !is.na(data$mob14))
    flag_inconsistency(flight_inconsistent, "no_flights_but_spending")
  }

  # Work status vs workplace ZIP code
  # mob11a=6: doesn't work
  # seco4_1: workplace ZIP should be empty/NA
  if("mob11a" %in% names(data) && "seco4_1" %in% names(data)) {
    work_inconsistent <- (data$mob11a == 6 &
                         !is.na(data$seco4_1) & data$seco4_1 != -2)
    flag_inconsistency(work_inconsistent, "no_work_but_workplace_zip")
  }

  # Household size consistency
  # Check if gender totals match age totals in seco1b
  if(all(c("seco1b_5", "seco1b_6", "seco1b_7",  # males, females, non-binary
           "seco1b_1", "seco1b_2", "seco1b_3", "seco1b_4") %in% names(data))) {

    gender_total <- rowSums(data[, c("seco1b_5", "seco1b_6", "seco1b_7")], na.rm = TRUE)
    age_total <- rowSums(data[, c("seco1b_1", "seco1b_2", "seco1b_3", "seco1b_4")], na.rm = TRUE)

    household_size_inconsistent <- (gender_total != age_total)
    flag_inconsistency(household_size_inconsistent, "household_size_mismatch")
  }

  # Working persons vs household adults
  # seco2: number of working persons should not exceed adults (18+)
  if(all(c("seco2_1", "seco2_2", "seco2_3",  # full-time, part-time high, part-time low
           "seco1b_3", "seco1b_4") %in% names(data))) {  # adults 18-65, adults 65+

    working_persons <- rowSums(data[, c("seco2_1", "seco2_2", "seco2_3")], na.rm = TRUE)
    adults <- rowSums(data[, c("seco1b_3", "seco1b_4")], na.rm = TRUE)

    working_inconsistent <- (working_persons > adults)
    flag_inconsistency(working_inconsistent, "more_workers_than_adults")
  }
  return(consistency_flags)
}



run_outlier_detection <- function(data) {
  scale_vars <- c()

  # Add behavioral intention scales
  #int_vars <- paste0("psy8_", 1:5)  # Behavioral intentions
  #int_vars <- int_vars[int_vars %in% names(data)]
  #scale_vars <- c(scale_vars, int_vars)

  # Add behavioral intention scales
  # int_vars <- paste0("psy1_", 1:5)  # Behavioral intentions
  # int_vars <- int_vars[int_vars %in% names(data)]
  #scale_vars <- c(scale_vars, int_vars)

  # Add behavioral intention scales
  # int_vars <- paste0("psy2_", 1:5)  # Behavioral intentions
  # int_vars <- int_vars[int_vars %in% names(data)]
  #scale_vars <- c(scale_vars, int_vars)

  # int_vars <- paste0("psy3_", 1:5)  # Behavioral intentions
  # int_vars <- int_vars[int_vars %in% names(data)]
  # scale_vars <- c(scale_vars, int_vars)

  int_vars <- paste0("psy4_", 1:16)  # Behavioral intentions
  int_vars <- int_vars[int_vars %in% names(data)]
  scale_vars <- c(scale_vars, int_vars)

   # Add attitude scales
  #att_vars <- paste0("psy5a_", 1:5)  # Environmental attitudes
  #att_vars <- att_vars[att_vars %in% names(data)]
  #scale_vars <- c(scale_vars, att_vars)

  # Add attitude scales
  # att_vars <- paste0("psy6_", 1:5)  # Environmental attitudes
  # att_vars <- att_vars[att_vars %in% names(data)]
  # scale_vars <- c(scale_vars, att_vars)


  # int_vars <- paste0("soc4_", 1:5)  # Behavioral intentions
  # int_vars <- int_vars[int_vars %in% names(data)]
  # scale_vars <- c(scale_vars, int_vars)

  # int_vars <- paste0("soc4a_", 1:5)  # Behavioral intentions
  # int_vars <- int_vars[int_vars %in% names(data)]
  # scale_vars <- c(scale_vars, int_vars)

  # int_vars <- paste0("soc5_", 1:5)  # Behavioral intentions
  # int_vars <- int_vars[int_vars %in% names(data)]
  # scale_vars <- c(scale_vars, int_vars)

  #int_vars <- paste0("soc6_", 1:5)  # Behavioral intentions
  #int_vars <- int_vars[int_vars %in% names(data)]
  #scale_vars <- c(scale_vars, int_vars)



  cat("Used", length(scale_vars), "scale variables for analysis\n\n")
  cat("Used scale_vars: \n", scale_vars, "\n\n")

  results <- data.frame(id = data$id)

  # Timing-based
  if("q_totalduration" %in% names(data)) {
    cat("Timing based: total duration")
    # Get some realistic threshold? More than 10 less than 60 ( Filter out people who finished under 2 min
    # and people who finished in more than 60 min for threshold
    #threshold <- data  %>%
    #  filter(q_totalduration > 10, q_totalduration < 60)
    #fast_threshold <- quantile(threshold$q_totalduration, 0.05, na.rm = TRUE)
    fast_threshold <- quantile(data$q_totalduration, 0.05, na.rm = TRUE)
    results$timing_speeder <- data$q_totalduration <= fast_threshold & !is.na(data$q_totalduration)
    cat("Timing speeders (bottom 5%):", sum(results$timing_speeder, na.rm = TRUE), "Fast treshold: ",fast_threshold, "\n")
  }

  # Consistency checks
  consistency_result <- detect_inconsistencies(data)
  results <- merge(results, consistency_result, by = "id", all.x = TRUE)
  cat("Inconsistent responses:", sum(results$inconsistent, na.rm = TRUE), "\n")


   if(length(scale_vars) > 0) {
     cat("Straightliners:", sum(results$straightline, na.rm = TRUE), "\n")
     straightline_result <- detect_straightlining(data, scale_vars)
     results <- merge(results, straightline_result, by = "id", all.x = TRUE)
     # Copy the attributes to results
     attr(results, "straightline_summary_stats") <- attr(straightline_result, "straightline_summary_stats")
   }


  # Create composite risk score
  flag_vars <- c("timing_speeder", "straightline","inconsistent")
  flag_vars <- flag_vars[flag_vars %in% names(results)]

  if(length(flag_vars) == 0) {
    results$risk_score <- 0
  } else if(length(flag_vars) == 1) {
    results$risk_score <- as.numeric(results[[flag_vars]])
  } else {
    results$risk_score <- rowSums(results[, flag_vars], na.rm = TRUE)
  }

 return(results)
}

plot_completion_distribution <- function(threshold_data, wave_name = "SHEDS", show_plot = TRUE) {

  #if (!"q_totalduration" %in% names(data)) {
  #  warning("q_totalduration not found in data")
  #  return(NULL)
  #}

  library(ggplot2)

  # Calculate thresholds and create threshold data
  # threshold_data <- data %>%
  #  filter(q_totalduration > 10, q_totalduration < 60)

  fast_threshold <- quantile(threshold_data$q_totalduration, 0.05, na.rm = TRUE)

  # Get statistics
  duration <- threshold_data$q_totalduration[!is.na(threshold_data$q_totalduration)]
  mean_time <- mean(duration, na.rm = TRUE)
  median_time <- median(duration, na.rm = TRUE)

  # Count speeders
  n_speeders <- sum(threshold_data$q_totalduration <= fast_threshold & !is.na(threshold_data$q_totalduration))
  pct_speeders <- (n_speeders / nrow(threshold_data)) * 100

  # Create the plot
  p <- ggplot(threshold_data, aes(x = q_totalduration)) +
    # Histogram
    geom_histogram(bins = 50, fill = "steelblue", alpha = 0.7, color = "white") +

    # Threshold lines
    geom_vline(xintercept = 10, color = "gray50", linetype = "dotted", size = 1) +
    geom_vline(xintercept = 60, color = "gray50", linetype = "dotted", size = 1) +
    # geom_vline(xintercept = fast_threshold, color = "red", linetype = "dashed", size = 0.6) +
    geom_vline(xintercept = mean_time, color = "darkblue", linetype = "solid", size = 1) +

    # Annotations
    #annotate("text", x = 10, y = Inf, label = "10 min\n(filter)",
    #         hjust = -0.1, vjust = 1.5, size = 3, color = "gray40") +
    #annotate("text", x = 60, y = Inf, label = "60 min\n(filter)",
    #         hjust = 1.1, vjust = 1.5, size = 3, color = "gray40") +
    #annotate("text", x = fast_threshold, y = Inf,
    #         label = sprintf("5%% threshold\n%.1f min", fast_threshold),
    #         hjust = -0.1, vjust = 3, size = 1.2, color = "red", fontface = "bold") +
    annotate("text", x = mean_time, y = Inf,
             label = sprintf("Mean\n%.1f min", mean_time),
             hjust = -0.1, vjust = 5, size = 3, color = "darkblue") +

    # Shaded region for speeders
    annotate("rect", xmin = -Inf, xmax = fast_threshold, ymin = -Inf, ymax = Inf,
             alpha = 0.2, fill = "red") +

    # Labels
    labs(
      title = sprintf("Completion Time Distribution - %s", wave_name),
      subtitle = sprintf(
        "Mean: %.1f min | Median: %.1f min | 5%% threshold: %.1f min )",
        mean_time, median_time, fast_threshold
      ),
      x = "Completion Time (minutes)",
      y = "Number of Respondents",
     #  caption = sprintf("n = %d respondents | Gray lines = filtering bounds (10-60 min)",
      #                 length(duration))
    ) +

    # Limit x-axis for better visibility
    # xlim(0, min(max(duration, na.rm = TRUE), 100)) +
    # START X-AXIS AT 10 MIN
    coord_cartesian(xlim = c(10, 100)) +
    scale_x_continuous(breaks = seq(10, 100, by = 10)) +

    # Theme
    theme_minimal(base_size = 12) +
    theme(
      plot.title = element_text(face = "bold", size = 14),
      plot.subtitle = element_text(size = 10, color = "gray40"),
      plot.caption = element_text(size = 9, color = "gray50", hjust = 0)
    )

  if (show_plot) {
    print(p)
  }

  # Print summary statistics
  cat("\n=== COMPLETION TIME SUMMARY ===\n")
  cat(sprintf("Wave: %s\n", wave_name))
  cat(sprintf("Total respondents: %d\n", length(duration)))
  cat(sprintf("Mean: %.2f minutes\n", mean_time))
  cat(sprintf("Median: %.2f minutes\n", median_time))
  cat(sprintf("SD: %.2f minutes\n", sd(duration, na.rm = TRUE)))
  cat(sprintf("Range: %.1f - %.1f minutes\n",
              min(duration, na.rm = TRUE),
              max(duration, na.rm = TRUE)))
  cat("\nPercentiles:\n")
  print(quantile(duration, probs = c(0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95), na.rm = TRUE))
  cat(sprintf("\n5%% threshold (after 10-60 filter): %.2f minutes\n", fast_threshold))
  cat(sprintf("Speeders flagged: %d (%.2f%%)\n", n_speeders, pct_speeders))
  cat(sprintf("Speeders complete in %.1f%% of mean time\n",
              100 * fast_threshold / mean_time))

  return(invisible(p))
}

#' Plot completion time distributions as ridge plot
#' @param waves_data Either a combined dataframe with Wave column, or list of already-filtered wave dataframes
#' @export
plot_waves_ridges <- function(waves_data) {

  library(ggplot2)
  library(ggridges)
  library(dplyr)

  # Check if input is already combined or a list
  if (is.data.frame(waves_data)) {
    # Already combined dataframe
    combined_data <- waves_data %>%
      select(Wave, Duration = q_totalduration)

    # Calculate thresholds per wave
    thresholds <- waves_data %>%
      group_by(Wave) %>%
      summarise(Threshold = quantile(q_totalduration, 0.05, na.rm = TRUE), .groups = "drop")

  } else {
    # List of waves
    # Calculate thresholds
    thresholds <- bind_rows(
      map(names(waves_data), function(wave_name) {
        data <- waves_data[[wave_name]]
        data.frame(
          Wave = wave_name,
          Threshold = quantile(data$q_totalduration, 0.05, na.rm = TRUE)
        )
      })
    )

    # Combine data
    combined_data <- bind_rows(
      map(names(waves_data), function(wave_name) {
        data <- waves_data[[wave_name]]
        data.frame(Wave = wave_name, Duration = data$q_totalduration)
      })
    )
  }

  # Reverse order for ridge plot (most recent on top)
  wave_order <- rev(unique(combined_data$Wave))
  combined_data$Wave <- factor(combined_data$Wave, levels = wave_order)
  thresholds$Wave <- factor(thresholds$Wave, levels = wave_order)

  # Create ridge plot
  ggplot(combined_data, aes(x = Duration, y = Wave, fill = Wave)) +
    geom_density_ridges(alpha = 0.7, scale = 1.5, rel_min_height = 0.01) +
    geom_point(data = thresholds, aes(x = Threshold, y = Wave),
               color = "red", size = 3, shape = 18, inherit.aes = FALSE) +
    geom_vline(xintercept = c(10, 60), linetype = "dotted", color = "gray50", alpha = 0.5) +
    labs(
      subtitle = "Red diamonds mark the 5th percentile timing threshold",
      x = "Completion Time (minutes)",
      y = "SHEDS Wave"
    ) +
    scale_fill_brewer(palette = "Set2") +
    coord_cartesian(xlim = c(0, 100)) +
    theme_ridges() +
    theme(
      plot.title = element_text(face = "bold", size = 14),
      plot.subtitle = element_text(size = 10, color = "gray40"),
      plot.caption = element_text(size = 8, color = "gray50", hjust = 0),
      legend.position = "none"
    )
}

# Function to create straightliner detail table
get_straightliner_details <- function(data, wave_name, scale_vars = paste0("psy4_", 1:16)) {
  # Run detection to get flags
  straightline_result <- detect_straightlining(data, scale_vars, verbose = FALSE)

  # Get straightliners
  straightliners <- data %>%
    inner_join(straightline_result, by = "id") %>%
    filter(straightline == TRUE)

  if(nrow(straightliners) == 0) {
    cat("No straightliners found in", wave_name, "\n")
    return(NULL)
  }

  # Create detail table
  details <- data.frame(
    wave = wave_name,
    id = straightliners$id,
    stringsAsFactors = FALSE
  )

  # Add each psy4 response
  for(var in scale_vars) {
    if(var %in% names(straightliners)) {
      details[[var]] <- straightliners[[var]]
    }
  }

  # Calculate straightlining statistics for each person
  details$most_common_value <- NA
  details$frequency <- NA
  details$proportion <- NA
  details$n_valid_responses <- NA

  for(i in 1:nrow(details)) {
    responses <- as.numeric(details[i, scale_vars])

    # Get valid responses
    valid <- responses[!is.na(responses) &
                       responses != 0 &
                       responses != -1 &
                       responses != -2]

    if(length(valid) > 0) {
      freq_table <- table(valid)
      most_common <- as.numeric(names(freq_table)[which.max(freq_table)])
      max_freq <- max(freq_table)

      details$most_common_value[i] <- most_common
      details$frequency[i] <- max_freq
      details$proportion[i] <- max_freq / length(valid)
      details$n_valid_responses[i] <- length(valid)
    }
  }

  return(details)
}

# Function to create summary of straightliners across all waves
analyze_all_straightliners <- function(waves_filtered) {
  all_straightliners <- list()

  for(wave_name in names(waves_filtered)) {
    cat("\n=== WAVE", wave_name, "===\n")
    details <- get_straightliner_details(waves_filtered[[wave_name]], wave_name)

    if(!is.null(details)) {
      all_straightliners[[wave_name]] <- details

      # Print summary
      cat(sprintf("Found %d straightliners\n", nrow(details)))
      cat("\nDistribution of most common value:\n")
      print(table(details$most_common_value))
      cat("\nProportion statistics:\n")
      print(summary(details$proportion))

      # Show first few examples
      cat("\nFirst 5 straightliners:\n")
      summary_cols <- c("id", "most_common_value", "frequency", "proportion", "n_valid_responses")
      print(head(details[, summary_cols], 5))
    }
  }

  return(all_straightliners)
}