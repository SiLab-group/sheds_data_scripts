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
save_plot <- function(plot, path = "plots", filename, width = 12, height = 8) {
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


build_car_history <- function(all_waves_list) {
  # Combine all waves with car data
  car_history <- bind_rows(
    lapply(names(all_waves_list), function(year) {
      all_waves_list[[year]] %>%
       #  filter(finished == 1) %>%
        select(id,mob2_1, mob3_3, any_of("old"),any_of("mob2_e"), any_of("mob3_change")) %>%
        mutate(year_wave = as.numeric(year))
    })
  ) %>%
    arrange(id, year_wave)

  # For each person, take forward their last known car type
  car_history <- car_history %>%
    group_by(id) %>%
    mutate(
      # Carry forward last known mob3_3
      mob3_3_filled = ifelse(!is.na(mob3_3) & mob3_3 > 0, mob3_3, NA),
      mob3_3_filled = zoo::na.locf(mob3_3_filled, na.rm = FALSE),
      # Carry forward last known mob2_e
      mob2_e_filled = ifelse(!is.na(mob2_e) & mob2_e >= 0, mob2_e, NA),
      mob2_e_filled = zoo::na.locf(mob2_e_filled, na.rm = FALSE)
    ) %>%
    ungroup()

  return(car_history)
}

check_finished <- function(data, year) {
  cat("\n=== Year", year, "===\n")

  # Check if finished column exists
  if("finished" %in% names(data)) {
    total_respondents <- nrow(data)
    finished_count <- data %>%
      filter(finished == 1) %>%
      nrow()

    cat("Total respondents:", total_respondents, "\n")
    cat("Finished respondents:", finished_count, "\n")
    cat("Completion rate:", scales::percent(finished_count / total_respondents, accuracy = 0.1), "\n")

    # Show distribution of finished values
    cat("\nFinished column distribution:\n")
    print(table(data$finished, useNA = "ifany"))

    return(tibble(year = year, total = total_respondents, finished = finished_count))
  } else {
    cat("No 'finished' column found!\n")
    cat("Available columns:", paste(names(data)[1:10], collapse = ", "), "...\n")
    return(NULL)
  }
}

analyze_ev_ownership_data <- function(data_history, year) {

  cat("\n For Year", year, "\n")
  data_finished <- data_history  %>%
    filter(year_wave == year)
  #print(data_finished)


  # Car ownership
  car_owners <- if("mob2_1" %in% names(data_finished)) {
    data_finished %>% filter(mob2_1 > 0 & mob2_1 < 90) %>% nrow()
  } else {
    NA
  }

   # How many chaneged the car
  changed_car <- if("mob3_change" %in% names(data_finished)) {
     data_finished %>%
      filter(mob3_change == 1, mob2_1 > 0 & mob2_1 < 90) %>%
      nrow()
  } else {
    NA
  }

  # Car ownership
  new_car_owners <- if("mob2_1" %in% names(data_finished) & "old"  %in% names(data_finished)) {
    data_finished %>% filter(mob2_1 > 0 & mob2_1 < 90 & old == 0) %>% nrow()
  } else {
    NA
  }


  # EV main car (mob3_3 = 8)
  ev_main <- if("mob3_3_filled" %in% names(data_finished)) {
    data_finished %>% filter(mob3_3_filled == 8 ) %>% nrow()
  } else {
    NA
  }

  # EV secondary (mob2_e = 1)
  ev_secondary <- if("mob2_e" %in% names(data_finished)) {
    data_finished %>% filter(mob2_e == 1) %>% nrow()
  } else {
    NA
  }

  # Hybrids - now includes carried-forward data
  hybrid_gas <- if("mob3_3_filled" %in% names(data_finished)) {
    data_finished %>% filter(mob3_3_filled == 6 | mob3_3_filled == 5 ) %>% nrow()
  } else {
    NA
  }

  hybrid_diesel <- if("mob3_3_filled" %in% names(data_finished)) {
    data_finished %>% filter(mob3_3_filled == 7 ) %>% nrow()
  } else {
    NA
  }

  # Total EVs
  total_ev <- sum(c(ev_main, ev_secondary), na.rm = TRUE)
  #total_ev <- ev_main

  cat("Total respondents:", nrow(data_finished), "\n")
  cat("Car owners:", car_owners, "\n")
  cat("EVs (main):", if(!is.na(ev_main)) ev_main else "N/A", "\n")
  cat("EVs (secondary):", if(!is.na(ev_secondary)) ev_secondary else "N/A", "\n")
  cat("Total EVs:", total_ev, "\n")
  cat("Hybrids:", sum(c(hybrid_gas, hybrid_diesel), na.rm = TRUE), "\n\n")
  cat("Changed the car:", changed_car, na.rm = TRUE, "\n\n")
  cat("New respondents:", new_car_owners, na.rm = TRUE, "\n\n")


  tibble(
    year = year,
    n_total = nrow(data_finished),
    n_car_owners = car_owners,
    n_ev_main = if(!is.na(ev_main)) ev_main else 0,
    n_ev_secondary = if(!is.na(ev_secondary)) ev_secondary else 0,
    n_ev_total = total_ev,
    n_hybrid_gas = if(!is.na(hybrid_gas)) hybrid_gas else 0,
    n_hybrid_diesel = if(!is.na(hybrid_diesel)) hybrid_diesel else 0,
    ev_rate_all = total_ev / nrow(data_finished),
    ev_rate_car_owners = if(!is.na(car_owners) & car_owners > 0)
      total_ev / car_owners else NA,
    n_changed_car = changed_car,
    new_respondents = new_car_owners
  )
}