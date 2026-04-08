# SHEDS Data Analysis Scripts

Scripts for processing and analyzing the Swiss Household Energy Demand Survey (SHEDS) data in R and Python.
SHEDS data is stored in SPSS format (.sav) which includes value labels and variable descriptions. Descriptions and more information can be found at [SHEDS - Sweet Cross](https://sweet-cross.ch/sheds/).

**Figure 1. SHEDS variable counts over time**
<img width="2224" height="1202" alt="sheds_timeline_counts" src="https://github.com/user-attachments/assets/713a6f56-d32d-4148-b1ff-34df0b3cd7e8" />

*Note: This Figure shows the number of variables (columns) available in SHEDS datasets in each category. These do not correspond to numbers of questions because each item of a question is coded in its own column.*

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
    │   ├── utils.py # read_clean_sheds, get_data_summary, save_plot, conditional_ffill, build_car_history, check_finished, analyze_ev_ownership_data
    │   ├── sheds_explore.ipynb # Explore dataset and metadata
    |   ├── car_owners_paper.ipynb # Explore car owners
    │   ├── longitudinal_exploration.ipynb # EV ownership
    │   ├── longitudinal_history_variables.py # Build longitudinal history files (see below)
    │   └── read_sav_example.ipynb # Simple example of how to read and use metadata
    └── R/
        ├── utils.R # read_clean_sheds, get_data_summary, save_plot, build_car_history_stata, analyze_ev_ownership_data, theme_publication, validate_car_history, filter_by_included_vars, generate_latex_row
        ├── sheds_explore.Rmd # Explore dataset and metadata
        ├── outlier_detection.Rmd # Outlier detection
        ├── outliers_functions.R
        ├── car_owners_paper.R # Explore car owners
        ├── wemf_regions_distribution_map.Rmd # Create region distribution map
        └── longitudinal_exploration.rmd # EV ownership
```

### Longitudinal History Files

`longitudinal_history_variables.py` builds two panel datasets (one row per respondent × wave) saved as `.csv` and `.pkl`:

- **`sheds_accom_history`** — accommodation type (`accom1`: owner / tenant / cooperative) across all waves, plus additional housing variables. Includes a filled column `accom1_filled` to handle survey skip logic:
  - In **2018 and 2019**, returning respondents who did not move were not asked `accom1` again (coded `-2` DNA). Their previous answer is carried forward into `accom1_filled`.
  - In **2020**, a small number of respondents have a missing `accom1`; these are also filled from the previous wave.
  - If a respondent reported a move (`accom_change == 1`), no fill is applied — the new value must be explicit.
- **`sheds_identifier_history`** — selected target variables (e.g. `accom3`, `accom5`, `heat5a1_2`) across all waves in wide format.

**Car history** is built via `build_car_history` in `utils.py` (Python) and equivalently in `utils.R` / `longitudinal_exploration.rmd` (R):
- Returning car owners are only asked for their fuel type (`mob3_3`) if they changed their car (`mob3_change == 1`). Otherwise the previous answer is carried forward into `mob3_3_filled`.

#### Accommodation Variables

| Variable | Description | Codes |
|----------|-------------|-------|
| `id` | Respondent ID (consistent across waves) | — |
| `accom1` | Accommodation type | 1 = Owner, 2 = Tenant, 3 = Cooperative |
| `accom1_filled` | `accom1` with carry-forward applied | same as above |
| `accom_change` | Respondent changed accommodation since last wave | 1 = yes, 0 = no |

#### Car Variables

| Variable | Description | Codes |
|----------|-------------|-------|
| `mob2_1` | Number of cars in household | — |
| `mob3_3` | Fuel type of main car | 1 = Gasoline, 2 = Diesel, 3 = Natural Gas, 4 = LPG, 5 = Hybrid gasoline, 6 = Plug-in Hybrid, 7 = Hybrid diesel, 8 = Electric, 9 = Other |
| `mob3_3_filled` | `mob3_3` with carry-forward applied | same as above |
| `mob3_change` | Respondent changed car since last wave | 1 = yes, 0 = no |
| `mob2_e` | Has electric vehicle as secondary car | 1 = yes |




## Setup

### Python

```bash
pip install pandas numpy pyreadstat matplotlib seaborn
```

### R

```r
install.packages(c("haven", "tidyverse", "zoo", "scales", "yaml", "skimr", "corrplot", "ggthemes", "kableExtra", "extrafont", "patchwork", "forcats"))
```

Saving plots as PDF/EPS requires Cairo. Install the system library for your OS first, then `install.packages("Cairo")` in R:

- **macOS:** install [XQuartz](https://www.xquartz.org), then `brew install cairo`
- **Linux (Debian/Ubuntu):** `sudo apt install libcairo2-dev libxt-dev`
- **Windows:** Cairo is bundled with R — no extra steps needed.

## Configuration

Before running any scripts, create `config.yaml` and set the paths for your machine. Example:

```yaml
paths:
  data_dir: "/path/to/your/sheds_data/"   # folder containing the .sav files
  plots_dir: "plots"                       # output folder for saved figures
  questions_csv: "sheds_questions_up2025.csv"
  geodata_bezirke: ""                      # path to BFS Bezirke shapefile

sheds_files:
  "2016": "SHEDS2016.sav"
  "2017": "SHEDS2017.sav"
  "2018": "SHEDS2018.sav"
  "2019": "SHEDS2019.sav"
  "2020": "SHEDS2020.sav"
  "2021": "SHEDS2021.sav"
  "2023": "SHEDS2023.sav"
  "2025": "SHEDS2025.sav"
```

- **`data_dir`** — absolute path to the directory where your SHEDS `.sav` files are stored. All scripts read data from here.
- **`sheds_files`** — maps each wave year to its filename inside `data_dir`. Remove entries for waves you do not have.
- **`plots_dir`** — relative or absolute path where figures are saved by `save_plot()`. Created automatically if it does not exist.
- **`geodata_bezirke`** — only needed for the region distribution map. Leave empty to auto-download.

> **Note:** `config.yaml` contains your local paths and is listed in `.gitignore` — do not commit it.

## Loading SHEDS Data

### Python - Accessing Labels

For the reading the file library pyreadstat has to be first installed. Then the the file can be loaded with metadata:
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

## Citation

If you use this repository, please cite the following paper:

```bibtex
@TechReport{repec:irn:wpaper:26-05,
    type={IRENE Working Papers},
    institution={IRENE Institute of Economic Research},
    author={Amy Liffey and Rene Schumann and Sylvain Weber and Mehdi Farsi},
    title={The Swiss Household Energy Demand Survey: Panel updates and evidence after eight waves},
    year={2026},
    month={Mar},
    number={26-05},
    abstract={This paper serves as a comprehensive reference for users of the Swiss Household Energy Demand Survey (SHEDS). SHEDS was conducted annually from 2016 to 2021, followed by two waves in 2023 and 2025; two further waves are scheduled in 2027 and 2029. So far, it provides a panel dataset of eight waves that span a 9-year period. We present recent updates to the panel, including data processing and data quality guidelines, and provide an overview of its evolving structure. In addition, we provide two applications that illustrate the research possibilities enabled by SHEDS. We use the first application to provide a description of how the data can be used to inform an agent-based model. The second application is a descriptive study of the evolution of car ownership patterns showcasing the potential of the survey's longitudinal dimension.},
    keywords={},
    doi={None},
    url={https://ideas.repec.org/p/irn/wpaper/26-05.html},
}
```
