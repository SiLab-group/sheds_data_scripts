# SHEDS scripts
This repository contains the scripts to read sheds data files. For the complete data with metadata the sav files should be used in R and python.

## Loading

1. Loading with metadata R:
```R
sheds <- read_sav("/Users/olaf/NAMEFILE.sav", encoding="UTF-8")
```


2. Loading with metadata python:
```python
import pyreadstat
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
