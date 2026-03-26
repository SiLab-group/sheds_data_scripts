# SHEDS Data Analysis Scripts

Scripts for processing and analyzing the Swiss Household Energy Demand Survey (SHEDS) data in R and Python.
SHEDS data is stored in SPSS format (.sav) which includes value labels and variable descriptions. Descriptions and more information can be found at [SHEDS - Sweet Cross](https://sweet-cross.ch/sheds/).

## Project Structure
The project provides example scripts demonstrating how to work with SHEDS data in R and Python.
It also includes a CSV file listing all question identifiers across survey years, indicating when each question was used, to improve transparency and facilitate longitudinal analysis.

```
sheds_data_scripts/
├── sheds_questions_up2025.csv # Table of question identifiers over the years
├── README.md
├── .gitignore
└── src/
    ├── python/
    │   ├── utils.py # Contains useful functions
    │   ├── sheds_explore.ipynb # Explore dataset and metadata
    │   ├── longitudinal_exploration.ipynb # EV ownership
    │   └── read_sav_example.ipynb # Simple example of how to read and use metadata
    └── R/
        ├── utils.R # Contains useful functions
        ├── sheds_explore.Rmd # Explore dataset and metadata
        ├── outlier_detection.Rmd # Outlier detection
        ├── outliers_functions.R
        ├── wemf_regions_distribution_map.Rmd # Create region distribution map
        └── longitudinal_exploration.rmd # EV ownership
```

## Setup

### Python

```bash
pip install pandas numpy pyreadstat matplotlib seaborn
```

### R

```r
install.packages(c("haven", "tidyverse", "zoo", "scales"))
```

## Loading SHEDS Data

### R

```r
source("utils.R")

## Content
- `sheds_questions_up2025.csv`: contains the question ids over the years, 1 indicating the question occured in the given year
- `sheds_explore.Rmd`: contains loading of the sav file in R with the metadata and some example graphs
- `read_sav_example.ipynb`: contains loading of sav file in python with metadata and examples how to access metadata

## Loading SPSS file
1. For the loading the library `haven` has to be first installed. After that the file can be loaded:
```R
library(haven)        # Read SPSS files
sheds <- read_sav("/Users/olaf/NAMEFILE.sav", encoding="UTF-8")
```

### Python

2. For the reading the file library pyreadstat has to be first installed. Then the the file can be loaded with metadata:
```python
import pyreadstat

# Load with metadata
df, meta = pyreadstat.read_sav("/path/to/SHEDS2025.sav", encoding="UTF-8")

# Get variable label (question text)
meta.column_names_to_labels['accom11_1']
# -> "How satisfied are you with your current heating system?"

# Get value labels (response options)
meta.variable_value_labels['accom11_1']
# -> {1: 'Very dissatisfied', 2: 'Dissatisfied', ..., 5: 'Very satisfied'}

# Apply labels to create readable values
df['accom11_1_label'] = df['accom11_1'].map(meta.variable_value_labels['accom11_1'])
```

### R - Accessing Labels

```r
library(haven)

sheds <- read_sav("/path/to/SHEDS2025.sav")

# Get variable label
attr(sheds$accom11_1, "label")

# Get value labels
attr(sheds$accom11_1, "labels")

# Apply labels
library(dplyr)
sheds %>%
  mutate(accom11_1_label = as_factor(accom11_1))
```

## Functions

| Function | Description |
|----------|-------------|
| `read_clean_sheds(filepath)` | Read SPSS file, filter out screened respondents (`screen != 3`) |
| `get_data_summary(data)` | Returns n_respondents, n_variables, completion_rate, avg_duration |
| `build_car_history(all_waves_dict)` | Combine waves, carry forward car data for longitudinal analysis |
| `analyze_ev_ownership_data(data_history, year)` | Analyze EV/hybrid ownership for a specific year |
| `save_plot(plot, path, filename)` | Save figure in PDF and EPS formats |
| `check_finished(data, year)` | Report completion statistics for a wave |

## Example longitudinal analysis of EVs
Since we do not ask all respondents about their car type in every wave—only when they report a change—it is necessary to reconstruct the full car‑ownership history for the analysis. In each wave, respondents are asked whether they have changed their car since the previous survey. If they report a change, we collect the type of car; if not, the question is skipped.
To build a complete car‑type history, we need to carry forward (i.e., “roll forward”) the car type reported in the most recent previous wave whenever no change is indicated, and update the value only in waves where a change is reported.

### Python

```python
from utils import read_clean_sheds, build_car_history, analyze_ev_ownership_data
import pandas as pd

# Load all waves
years = [2016, 2017, 2018, 2019, 2020, 2021, 2023, 2025]
waves = {}
for year in years:
    waves[str(year)] = read_clean_sheds(f"/path/to/SHEDS{year}.sav")

# Build car history with forward-fill
car_history = build_car_history(waves)

# Analyze each year
results = pd.concat([
    analyze_ev_ownership_data(car_history, year)
    for year in [2019, 2020, 2021, 2023, 2025]
])
```

### R

```r
source("utils.R")

years <- c(2016, 2017, 2018, 2019, 2020, 2021, 2023, 2025)
waves <- list()

for (year in years) {
  waves[[as.character(year)]] <- read_clean_sheds(paste0("/path/to/SHEDS", year, ".sav"))
}

car_history <- build_car_history(waves)

results <- bind_rows(
  analyze_ev_ownership_data(car_history, 2019),
  analyze_ev_ownership_data(car_history, 2020),
  analyze_ev_ownership_data(car_history, 2021),
  analyze_ev_ownership_data(car_history, 2023),
  analyze_ev_ownership_data(car_history, 2025)
)
```

## Used Variables

| Variable | Description |
|----------|-------------|
| `id` | Respondent ID (consistent across waves) |
| `finished` | Survey completion (1 = finished) |
| `screen` | Screening status (3 = screened out) |
| `mob2_1` | Number of cars in household |
| `mob3_3` | Fuel type of main car (8 = Electric) |
| `mob2_e` | Has electric vehicle as secondary car (1 = yes) |
| `q_totalduration` | Survey duration in minutes |

### mob3_3 Fuel Type Codes

| Code | Fuel Type |
|------|-----------|
| 1 | Gasoline |
| 2 | Diesel |
| 3 | Natural Gas |
| 4 | LPG |
| 5 | Hybrid gasoline |
| 6 | Plug-in Hybrid |
| 7 | Hybrid diesel |
| 8 | Electric |
| 9 | Other |

