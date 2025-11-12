# SHEDS scripts
This repository contains the scripts to read sheds data files. For the complete data with metadata the sav files should be used in R and python.

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


2. For the reading the file library pyreadstat has to be first installed. Then the the file can be loaded with metadata:
```python
import pyreadstat # Read SPSS files
import numpy as np

# Example  how to load the file with name
data_path = "/Users/olaf"
f = "NAMEFILE.sav"
df, metadata = pyreadstat.read_sav(f"{data_path}/{f}", encoding="UTF-8")

# Print column names
print("\nColumn names:", metadata.column_names)

# Take column name such as accom11_1
column_name = "accom11_1"
metadata.variable_value_labels[column_name]

# Print column labels
print("\nColumn labels:", metadata.column_labels)

# Print variable value labels id_of_question = { metadata}
print("\nValue labels:", metadata.variable_value_labels)

```

## Loading Stata file


