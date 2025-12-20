"""
SHEDS Identifier History - Wide Format
One row per ID + year with variable answers as columns
"""

import pandas as pd
import pyreadstat
from pathlib import Path


data_dir = Path("/home/amy/tmp/sheds_data/files")  # Adjust for the path to the files

# Target variables to find and make columns of
target_vars = ["accom3", "accom5", "heat5a1_2", "accom4a3", "accom9a1_1","accom9a1_2","accom9a1_3","accom9a1_4"]

# SHEDS data files by year
sheds_files = {
    2016: "SHEDS2016.sav",
    2017: "SHEDS2017.sav",
    2018: "SHEDS2018.sav",
    2019: "SHEDS2019.sav",
    2020: "SHEDS2020.sav",
    2021: "SHEDS2021.sav",
    2022: "SHEDS2022.sav",
    2023: "SHEDS2023.sav",
    2024: "SHEDS2024.sav",
    2025: "SHEDS2025.sav",
}


def read_clean_sheds(filepath: str) -> tuple[pd.DataFrame, pyreadstat.metadata_container]:
    """
    Read SPSS file and filter out screened respondents (screen == 3).
    Equivalent to R's read_sav() with haven - keeps numeric codes.

    Parameters
    ----------
    filepath : str
        Path to the .sav SPSS file

    Returns
    -------
    pd.DataFrame
        Cleaned dataframe with numeric codes preserved
    """
    df, meta = pyreadstat.read_sav(filepath,
                                   encoding='UTF-8', apply_value_formats=False)
    df = df[df['screen'] != 3].copy()
    return df, meta


def extract_year(filepath: Path, year: int, target_vars: list) -> pd.DataFrame | None:
    """Extract target variables from a single year's SHEDS file."""
    print(f"Processing {year}...")

    if not filepath.exists():
        print(f"  File not found: {filepath}")
        return None

    # Read SPSS file
    df, meta = read_clean_sheds(filepath)

    # Find ID column
    id_col = None
    possible_ids = ["id"]
    for col in possible_ids:
        if col in df.columns:
            id_col = col
            break

    if id_col is None:
        # Try to find any column with 'id' in name
        id_candidates = [c for c in df.columns if 'id' in c.lower()]
        if id_candidates:
            id_col = id_candidates[0]
        else:
            print("  No ID column found, using index")
            df['id'] = df.index
            id_col = 'id'

    print(f"  ID column: {id_col}")

    # Find available target variables (case-insensitive search)
    df_cols_lower = {c.lower(): c for c in df.columns}
    available_vars = []
    col_mapping = {}
    print(df.columns)

    for var in target_vars:
        if var in df.columns:
            available_vars.append(var)
            col_mapping[var] = var
        elif var.lower() in df_cols_lower:
            actual_col = df_cols_lower[var.lower()]
            available_vars.append(actual_col)
            col_mapping[var] = actual_col

    print(f"  Found: {', '.join(available_vars) if available_vars else 'None'}")

    if not available_vars:
        return None

    # Select columns
    cols_to_select = [id_col] + available_vars
    result = df[cols_to_select].copy()

    # Rename ID column to 'id'
    result = result.rename(columns={id_col: 'id'})

    # Rename columns back to standard names
    for standard_name, actual_name in col_mapping.items():
        if actual_name != standard_name and actual_name in result.columns:
            result = result.rename(columns={actual_name: standard_name})

    # Add year
    result['year'] = year

    return result


def main():
    print("SHEDS Identifier History Extraction")
    print("=" * 60)
    print(f"Target variables: {', '.join(target_vars)}")
    print()

    all_years = []

    for year, filename in sheds_files.items():
        filepath = data_dir / filename
        result = extract_year(filepath, year, target_vars)
        if result is not None:
            all_years.append(result)

    if not all_years:
        print("\nNo data extracted - check file paths and variable names")
        return

    # Combine all years
    history_df = pd.concat(all_years, ignore_index=True)

    # Reorder columns: id, year, then target vars
    cols_order = ['id', 'year'] + [v for v in target_vars if v in history_df.columns]
    history_df = history_df[cols_order].sort_values(['id', 'year']).reset_index(drop=True)

    # Summary
    print(f"Total records: {len(history_df)}")
    print(f"Unique IDs: {history_df['id'].nunique()}")
    print(f"Years: {sorted(history_df['year'].unique())}")

    print("\nPreview:")
    print(history_df.head(20).to_string())

    # Save
    output_csv = data_dir / "sheds_identifier_history.csv"
    output_pkl = data_dir / "sheds_identifier_history.pkl"

    history_df.to_csv(output_csv, index=False)
    history_df.to_pickle(output_pkl)

    print(f"\nSaved to:")
    print(f"  {output_csv}")
    print(f"  {output_pkl}")

    return history_df


if __name__ == "__main__":
    df = main()