library(haven)        # Read SPSS files
library(dplyr)
library(zoo)

# Useful functions
read_clean_sheds <- function(filepath) {
  data <- read_sav(filepath, encoding = "UTF-8") %>%
    filter(screen != 3) %>%
    # filter(q_totalduration > 2) %>% # Filter the responders who replied to the whole survey in less than 2 minutes
    as_tibble()  # Keep labels!

  return(data)
}

get_data_summary <- function(data) {
  clean_data <- data %>%
  filter(q_totalduration >= 1 & q_totalduration <= 60)
  list(
    n_respondents = nrow(clean_data),
    n_variables = ncol(clean_data),
    completion_rate = if ("finished" %in% names(clean_data)) {
      mean(clean_data$finished == 1, na.rm = TRUE) * 100
    } else {
      NA
    },
    avg_duration = if ("q_totalduration" %in% names(clean_data)) {
      mean(clean_data$q_totalduration, na.rm = TRUE)
    } else {
      NA
    }
  )
}

# Save plots in pdf and eps
save_plot <- function(plot, filename, width = 12, height = 8,path = "plots") {
  if (!dir.exists(path)) {
    dir.create(path, recursive = TRUE)
  }
  ggsave(
    filename = file.path(path, paste0(filename, ".pdf")),
    plot = plot,
    width = width,
    height = height,
    device = cairo_pdf
  )

  # Save as EPS
  ggsave(
    filename = file.path(path, paste0(filename, ".eps")),
    plot = plot,
    width = width,
    height = height,
    device = cairo_ps
  )

  cat(paste0("Saved: ", filename, ".pdf and .eps\n"))
}



build_car_history_stata <- function(all_waves_list) {
  # Combine all waves with car data
  car_history <- bind_rows(
    lapply(names(all_waves_list), function(year) {
      all_waves_list[[year]] %>%
        #select(id, mob2_1, mob3_3, any_of("old"), any_of("mob2_e"), any_of("mob3_change")) %>%
        select(id, mob2_1, mob3_3, any_of("md_220"), any_of("old"), any_of("mob2_e"), any_of("mob3_change"), any_of("md_hhgr")) %>%
        mutate(across(everything(), ~ as.vector(.))) %>%
        mutate(year_wave = as.numeric(year),
               # recode SPSS missing codes to NA before fill
               mob3_3 = ifelse(mob3_3 %in% c(-2, -1), NA_real_, as.numeric(mob3_3)))
    })
  ) %>%
    arrange(id, year_wave)

  # Stata logic: Copy info from previous waves
  # forv i = 1/8 {
  #   replace mob3_3 = l`i`.mob3_3 if mi(mob3_3) & !mob3_change
  # }
  # Carry forward mob3_3 ONLY if missing AND no car change
  car_history <- car_history %>%
    group_by(id) %>%
    mutate(
      mob3_3_filled = {
        val <- mob3_3
        for (i in seq_along(val)) {
          if (is.na(val[i]) && (is.na(mob3_change[i]) || mob3_change[i] == 0)) {
            # Look back for last non-NA value
            if (i > 1) {
              prev_vals <- val[1:(i-1)]
              last_known <- tail(prev_vals[!is.na(prev_vals)], 1)
              if (length(last_known) > 0) val[i] <- last_known
            }
          }
        }
        val
      },
      # Same for mob2_e (secondary car)
      mob2_e_filled = if ("mob2_e" %in% names(.)) {
        val <- mob2_e
        for (i in seq_along(val)) {
          if (is.na(val[i]) && (is.na(mob3_change[i]) || mob3_change[i] == 0)) {
            if (i > 1) {
              prev_vals <- val[1:(i-1)]
              last_known <- tail(prev_vals[!is.na(prev_vals)], 1)
              if (length(last_known) > 0) val[i] <- last_known
            }
          }
        }
        val
      } else NA
    ) %>%
    ungroup()

  # Drop E85 (3), natural gas (4), other (9)
  #car_history <- car_history %>%
  #  filter(!mob3_3_filled %in% c(3, 4, 9) | is.na(mob3_3_filled))

  # Recode: 1=Gasoline, 2=Diesel, 5-8=Hybrid or electric
  car_history <- car_history %>%
    mutate(
      car_type = case_when(
        mob3_3_filled == 1 ~ "Gasoline",
        mob3_3_filled == 2 ~ "Diesel",
        mob3_3_filled %in% c(6, 7) ~ "Hybrid",
        mob3_3_filled == 8  ~ "Pure Electric",
        TRUE ~ NA_character_
      )
    )

  return(car_history)
}

analyze_ev_ownership_data <- function(data_history, year, raw_waves ) {

  cat("\n For Year", year, "\n")
  data_finished <- data_history %>%
    filter(year_wave == year)

  raw_wave <- raw_waves[[as.character(year)]] %>%
  mutate(across(everything(), as.vector))

  n_total_raw <- nrow(raw_waves[[as.character(year)]])

  # --- Total population meaning sum of household members ---
  total_population <- if("md_hhgr" %in% names(data_finished)) {
    sum(data_finished$md_hhgr, na.rm = TRUE)
  } else {
    nrow(data_finished)
  }

  # --- Car owner population (only car owners) ---
  car_owner_population <- if("md_hhgr" %in% names(data_finished)) {
    sum(data_finished$md_hhgr[data_finished$mob2_1 >= 1 & data_finished$mob2_1 < 90], na.rm = TRUE)
  } else {
    sum(data_finished$mob2_1 >= 1 & data_finished$mob2_1 < 90, na.rm = TRUE)
  }

   car_owners <- if("mob2_1" %in% names(data_finished)) {
    data_finished %>% filter(mob2_1 > 0 & mob2_1 < 90) %>% nrow()
  } else {
    NA
  }


  car_owners_inter <- if("md_220" %in% names(raw_waves)) {
  data_finished %>%
    filter(as.numeric(md_220) > 0 & as.numeric(md_220) < 90) %>% nrow()
  } else {
    NA
  }

  changed_car <- if("mob3_change" %in% names(data_finished)) {
    data_finished %>%
      filter(mob3_change == 1, mob2_1 > 0 & mob2_1 < 90) %>%
      nrow()
  } else {
    NA
  }

  new_car_owners <- if("mob2_1" %in% names(data_finished) & "old" %in% names(data_finished)) {
    data_finished %>% filter(mob2_1 > 0 & mob2_1 < 90 & old == 0) %>% nrow()
  } else {
    NA
  }

  ev_main <- if("mob3_3_filled" %in% names(data_finished)) {
    data_finished %>% filter(mob2_1 > 0 & mob2_1 < 90) %>% filter(mob3_3_filled == 8) %>% nrow()
  } else {
    NA
  }


  # Fixed: use mob2_e_filled instead of mob2_e, and == 8 (engine type) instead of == 1
  ev_secondary <- if("mob2_e_filled" %in% names(data_finished)) {
    data_finished %>% filter(mob2_1 > 0 & mob2_1 < 90) %>% filter(mob2_e_filled == 1) %>% nrow()
  } else {
    NA
  }

  hybrid_gas <- if("mob3_3_filled" %in% names(data_finished)) {
    data_finished %>% filter(mob2_1 > 0 & mob2_1 < 90) %>% filter(mob3_3_filled %in% c(5, 6)) %>% nrow()
  } else {
    NA
  }

  hybrid_diesel <- if("mob3_3_filled" %in% names(data_finished)) {
    data_finished %>% filter(mob2_1 > 0 & mob2_1 < 90) %>% filter(mob3_3_filled == 7) %>% nrow()
  } else {
    NA
  }

  total_vehicles_mob2 <- if ("mob2_1" %in% names(raw_wave)) {
    sum(as.numeric(raw_wave$mob2_1[raw_wave$mob2_1 > 0 & raw_wave$mob2_1 < 90]),
        na.rm = TRUE)
  } else NA

  total_vehicles_md220 <- if ("md_220" %in% names(raw_wave)) {
    sum(as.numeric(raw_wave$md_220[as.numeric(raw_wave$md_220) > 0 &
                                    as.numeric(raw_wave$md_220) < 90]),
        na.rm = TRUE)
  } else NA

  # Stata logic:
  car_owners_df <- data_finished %>% filter(mob2_1 > 0 & mob2_1 < 90)

  elec_count <- car_owners_df %>%
    filter(mob3_3_filled %in% 8 | mob2_e %in% 1) %>%
    nrow()

  ev_count <- car_owners_df %>%
    filter(mob3_3_filled %in% c(5, 6, 7, 8) | mob2_e %in% 1) %>%
    nrow()

  hybrid_count <- car_owners_df %>%
    filter(mob3_3_filled %in% c(5, 6, 7)) %>%
    nrow()

  total_ev <- sum(c(ev_main, ev_secondary), na.rm = TRUE)

  cat("Total respondents:", nrow(data_finished), "\n")
  cat("Total population (all households):", total_population, "\n")
  cat("Car owners:", car_owners, "\n")
  cat("Car owner population (car owner households):", car_owner_population, "\n")
  cat("EVs (main):", if(!is.na(ev_main)) ev_main else "N/A", "\n")
  cat("EVs (secondary):", if(!is.na(ev_secondary)) ev_secondary else "N/A", "\n")
  cat("Total EVs:", total_ev, "\n")
  cat("Hybrids:", sum(c(hybrid_gas, hybrid_diesel), na.rm = TRUE), "\n\n")
  cat("Changed the car:", changed_car, na.rm = TRUE, "\n\n")
  cat("New respondents:", new_car_owners, na.rm = TRUE, "\n\n")

  tibble(
    year                       = year,
    n_total                    = n_total_raw,
    n_population               = total_population,
    n_car_owner_population     = car_owner_population,
    ev_rate_population         = total_ev / total_population,
    ev_rate_car_owner_pop      = total_ev / car_owner_population,
    n_car_owners               = car_owners,
    n_car_owners_inter         = car_owners_inter,
    n_ev_main                  = if(!is.na(ev_main)) ev_main else 0,
    n_ev_secondary             = if(!is.na(ev_secondary)) ev_secondary else 0,
    n_ev_total                 = ev_count,
    n_hybrid_total             = hybrid_count,
    n_elec_total               = elec_count,
    n_hybrid_gas               = if(!is.na(hybrid_gas)) hybrid_gas else 0,
    n_hybrid_diesel            = if(!is.na(hybrid_diesel)) hybrid_diesel else 0,
    ev_rate_all                = total_ev / n_total_raw,
    ev_rate_car_owners         = if(!is.na(car_owners) & car_owners > 0) total_ev / car_owners else NA,
    n_changed_car              = changed_car,
    new_respondents            = new_car_owners,
    n_total_vehicles_mob2      = total_vehicles_mob2,   # sum of cars from history
    n_total_vehicles_md220     = total_vehicles_md220,  # sum of cars from md_220
    ev_rate_vehicles           = total_ev / n_total_vehicles_mob2
  )
}

theme_publication <- function(base_size = 16, base_family = "") {
  theme_minimal(base_size = base_size, base_family = base_family) +
    theme(
      # Text elements
      plot.title = element_text(face = "bold", size = rel(1.3), hjust = 0.5,
                                margin = margin(b = 15)),
      plot.subtitle = element_text(size = rel(1.0), hjust = 0.5,
                                   margin = margin(b = 15)),
      plot.caption = element_text(size = rel(0.8), hjust = 1,
                                  margin = margin(t = 15)),

      # Axis text and titles
      axis.title = element_text(size = rel(1.1), face = "bold"),
      axis.text = element_text(size = rel(0.95), color = "black"),
      axis.text.x = element_text(margin = margin(t = 8)),
      axis.text.y = element_text(margin = margin(r = 8)),

      # Legend
      legend.title = element_text(size = rel(1.0), face = "bold"),
      legend.text = element_text(size = rel(0.95)),
      legend.key.size = unit(1.5, "lines"),
      legend.position = "bottom",
      legend.box.margin = margin(t = 15),

      # Panel and grid
      panel.grid.major = element_line(color = "grey90", linewidth = 0.5),
      panel.grid.minor = element_blank(),
      panel.border = element_blank(),

      # Plot margins
      plot.margin = margin(20, 20, 20, 20)
    )
}

validate_car_history <- function(car_history, label, all_waves,
                                         analysis_years = c(2019, 2020, 2021, 2023, 2025)) {
  library(scales)
  library(knitr)

  assert <- function(condition, message) {
    if (!condition) cat("FAIL:", message, "\n")
    else            cat("PASS:", message, "\n")
  }



  per_wave_raw <- bind_rows(lapply(names(all_waves), function(yr) {
    w <- all_waves[[yr]]
    tibble(
      year_wave    = as.numeric(yr),
      n_car_owners = sum(w$mob2_1 >= 1 & w$mob2_1 < 90, na.rm = TRUE),
      n_engine_raw = sum(w$mob3_3 > 0, na.rm = TRUE)
    )
  }))

  per_wave_filled <- car_history %>%
    filter(mob2_1 >= 1 & mob2_1 < 90) %>%   # car owners only
    group_by(year_wave) %>%
    summarise(
      n_in_history = n(),
      n_filled     = sum(!is.na(mob3_3_filled)),
      n_missing    = sum(is.na(mob3_3_filled)),   # now only among car owners
      n_electric   = sum(mob3_3_filled == 8, na.rm = TRUE),
      n_minus2     = sum(mob3_3_filled == -2, na.rm = TRUE),
      .groups      = "drop"
    )

  cmp <- per_wave_raw %>%
    left_join(per_wave_filled, by = "year_wave") %>%
    mutate(
      pct_raw    = round(n_engine_raw / n_car_owners * 100, 1),
      pct_filled = round(n_filled     / n_car_owners * 100, 1),
      recovered  = n_filled - n_engine_raw
    )

  cat("\n--- Per-wave coverage ---\n")
  cmp %>%
    select(year_wave, n_car_owners,
           n_engine_raw, pct_raw,
           n_filled, pct_filled, recovered, n_missing, n_minus2) %>%
    kable(col.names = c("Year", "Car Owners",
                        "Raw Known", "Raw %",
                        "Filled", "Filled %", "Recovered",
                        "Still Missing", "-2 Remaining"),
          align = "r", format.args = list(big.mark = ",")) %>%
    print()

  # ── md_708 cross-check (Intervista "Elektroauto im HH") ──────────────────
  # md_708 is collected every wave by the panel provider regardless of survey
  # flow, making it an independent ground-truth for EV presence in the household.
  # We compare it wave-by-wave against our mob3_3_filled == 8 derived count.
  # Expect: md_708 >= n_electric (Intervista covers all cars incl. secondary;
  # mob3_3_filled only tracks the main car unless mob2_e supplements it).
  md708_per_wave <- bind_rows(lapply(names(all_waves), function(yr) {
    w <- all_waves[[yr]] %>% mutate(across(everything(), as.vector))
    if (!"md_708" %in% names(w)) return(tibble(year_wave = as.numeric(yr),
                                               n_md708 = NA_integer_))
    tibble(
      year_wave = as.numeric(yr),
      n_md708   = sum(w$md_708 == 1, na.rm = TRUE)
    )
  }))

  md708_cmp <- cmp %>%
    left_join(md708_per_wave, by = "year_wave") %>%
    mutate(
      diff_vs_md708 = n_electric - n_md708,   # negative = under-count vs Intervista
      pct_md708     = round(n_md708   / n_car_owners * 100, 1),
      pct_electric  = round(n_electric / n_car_owners * 100, 1)
    )

  cat("\n--- md_708 (Intervista EV flag) vs mob3_3_filled == 8 ---\n")
  md708_cmp %>%
    select(year_wave, n_car_owners,
           n_md708, pct_md708,
           n_electric, pct_electric,
           diff_vs_md708) %>%
    kable(
      col.names = c("Year", "Car Owners",
                    "md_708 (Intervista)", "md_708 %",
                    "mob3_3==8 (derived)", "derived %",
                    "Diff (derived - Intervista)"),
      align = "r",
      format.args = list(big.mark = ","),
      caption = paste(
        "Negative diff = derived under-counts Intervista",
        "(expected: Intervista covers secondary cars too).",
        "Positive diff = derived EXCEEDS Intervista (investigate)."
      )
    ) %>%
    print()

  # ── Assertions ────────────────────────────────────────────────────────────
  cat("\n--- Assertions ---\n")

  assert(nrow(car_history %>% count(id, year_wave) %>% filter(n > 1)) == 0,
         "No duplicate id+year combinations")
  assert(any(cmp %>% filter(year_wave > min(year_wave)) %>% pull(recovered) > 0),
         "Forward-fill recovers at least some engine types after first wave")
  assert(sum(car_history$mob3_3_filled == -2, na.rm = TRUE) == 0,
         "No -2 codes remaining in mob3_3_filled")
  assert(all(diff(cmp %>% arrange(year_wave) %>% pull(n_electric)) >= 0, na.rm = TRUE),
         "EV count non-decreasing over time")
  assert(cmp %>% filter(year_wave == max(year_wave)) %>% pull(recovered) > 0,
         paste("Recovers engine types in", max(cmp$year_wave)))

  # md_708-specific assertions
  waves_with_md708 <- md708_cmp %>% filter(!is.na(n_md708))
  if (nrow(waves_with_md708) > 0) {
    assert(all(waves_with_md708$diff_vs_md708 <= 0, na.rm = TRUE),
           "Derived EV count never exceeds Intervista md_708 (no overcounting)")
    assert(all(diff(waves_with_md708 %>% arrange(year_wave) %>% pull(n_md708)) >= 0,
               na.rm = TRUE),
           "md_708 EV count non-decreasing over time")
    # Flag large unexplained gaps (>20% relative divergence) as a warning
    large_gaps <- waves_with_md708 %>%
      filter(!is.na(n_md708), n_md708 > 0) %>%
      mutate(rel_diff = abs(diff_vs_md708) / n_md708) %>%
      filter(rel_diff > 0.20)
    if (nrow(large_gaps) > 0) {
      cat("WARN: Large divergence (>20%) between derived and md_708 in waves:",
          paste(large_gaps$year_wave, collapse = ", "), "\n")
    } else {
      cat("PASS: No large divergences (>20%) between derived and md_708\n")
    }
  } else {
    cat("SKIP: md_708 not present in any wave\n")
  }

  invisible(car_history)
}

filter_by_included_vars <- function(data) {
  # Start with base filtering
  filtered <- data %>% filter(!is.na(car_owner))

  # Add filters for each included variable
  for (var in INCLUDED_DEMOGRAPHICS) {
    filtered <- filtered %>% filter(!is.na(!!sym(var)))

    # Special handling for gender - exclude "Other"
    if (var == "gender") {
      filtered <- filtered %>% filter(gender != "Other")
    }
  }

  return(filtered)
}

generate_latex_row <- function(wave_summary, column_name, row_label, add_percentage = FALSE, pct_column = NULL, format_decimal = FALSE) {
  cat(row_label)

  for(i in 1:nrow(wave_summary)) {
    value <- wave_summary[[column_name]][i]

    if(add_percentage && !is.null(pct_column)) {
      pct <- wave_summary[[pct_column]][i]
      if(pct >= 1.0) {
        cat(" & ", value, " (", sprintf("%.1f", pct), "\\%)", sep = "")
      } else {
        cat(" & ", value, sep = "")
      }
    } else if(format_decimal) {
      cat(" & ", sprintf("%.1f", value), sep = "")
    } else {
      cat(" & ", format(value, big.mark = ","), sep = "")
    }
  }

  cat(" \\\\\n")
}