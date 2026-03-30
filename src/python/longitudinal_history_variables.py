"""
SHEDS Identifier History - Wide Format
One row per ID + year with variable answers as columns
"""

import yaml
import pandas as pd
import pyreadstat
from pathlib import Path
from typing import Dict

_root = Path(__file__).parents[2]
with open(_root / "config.yaml") as f:
    _config = yaml.safe_load(f)

data_dir = Path(_config["paths"]["data_dir"])
sheds_files = _config["sheds_files"]

# Target variables to find and make columns of
target_vars = ["accom3", "accom5", "heat5a1_2", "accom4a3", "accom9a1_1","accom9a1_2","accom9a1_3","accom9a1_4"]


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


def extract_year(filepath: Path, year: int, target_vars: list,
                 df: pd.DataFrame | None = None) -> pd.DataFrame | None:
    """Extract target variables from a single year's SHEDS file.

    If df is provided (pre-read), filepath is not re-read.
    """
    print(f"Processing {year}...")

    if df is None:
        if not filepath.exists():
            print(f"  File not found: {filepath}")
            return None
        df, _ = read_clean_sheds(filepath)

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


def build_car_history(all_waves_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Build car history across all waves with carry-forward logic.
    Equivalent to R version using zoo::na.locf for forward fill.

    Parameters
    ----------
    all_waves_dict : dict
        Dictionary mapping year strings to DataFrames (e.g., {"2016": df2016, ...})

    Returns
    -------
    pd.DataFrame
        Combined car history with mob3_3_filled and mob2_e_filled columns
    """
    fuel_type_to_code = {
        'Gasoline': 1, 'gasoline': 1, 'Benzin': 1, 'Essence': 1,
        'Diesel': 2, 'diesel': 2,
        'Natural Gas': 3, 'natural gas': 3, 'Erdgas': 3, 'Gaz naturel': 3,
        'LPG': 4, 'lpg': 4,
        'Hybrid gasoline': 5, 'hybrid gasoline': 5, 'Hybride essence': 5,
        'Plug In Hybrid': 6, 'Plug-in Hybrid': 6, 'plug in hybrid': 6,
        'Hybrid diesel': 7, 'hybrid diesel': 7, 'Hybride diesel': 7,
        'Electric': 8, 'electric': 8, 'Électrique': 8, 'Elektrisch': 8,
        'Other': 9, 'other': 9, 'Autre': 9, 'Andere': 9,
    }

    dfs = []

    for year, df in all_waves_dict.items():
        cols_to_select = ['id', 'mob2_1', 'mob3_3']
        optional_cols = ['old', 'mob2_e', 'mob3_change']

        for col in optional_cols:
            if col in df.columns:
                cols_to_select.append(col)

        available_cols = [c for c in cols_to_select if c in df.columns]
        subset = df[available_cols].copy()
        subset['year_wave'] = int(year)

        if 'mob3_3' in subset.columns and subset['mob3_3'].dtype == object:
            subset['mob3_3'] = subset['mob3_3'].map(fuel_type_to_code)

        dfs.append(subset)

    car_history = pd.concat(dfs, ignore_index=True)
    car_history = car_history.sort_values(['id', 'year_wave'])

    numeric_cols = ['mob2_1', 'mob3_3', 'mob2_e', 'mob3_change', 'old']
    for col in numeric_cols:
        if col in car_history.columns:
            car_history[col] = pd.to_numeric(car_history[col], errors='coerce')

    # Carry forward last known mob3_3 (only positive values)
    car_history['mob3_3_filled'] = car_history['mob3_3'].where(
        car_history['mob3_3'].notna() & (car_history['mob3_3'] > 0)
    )
    car_history['mob3_3_filled'] = car_history.groupby('id')['mob3_3_filled'].ffill()

    # Carry forward last known mob2_e (only non-negative values)
    if 'mob2_e' in car_history.columns:
        car_history['mob2_e_filled'] = car_history['mob2_e'].where(
            car_history['mob2_e'].notna() & (car_history['mob2_e'] >= 0)
        )
        car_history['mob2_e_filled'] = car_history.groupby('id')['mob2_e_filled'].ffill()

    return car_history


def build_accom_history(all_waves_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Build accommodation (owner/tenant) history across all waves with carry-forward logic.

    accom1 codes: 1=Owner, 2=Tenant, 3=Living in cooperative
    accom_change: 1=moved/changed, 0=no change (returning respondents only)
    When accom_change=0, accom1 may be skipped (-2=dna), so we carry forward
    the last known value.

    Parameters
    ----------
    all_waves_dict : dict
        Dictionary mapping year strings to DataFrames (e.g., {"2016": df2016, ...})

    Returns
    -------
    pd.DataFrame
        Combined accommodation history with accom1_filled column
    """
    dfs = []

    for year, df in all_waves_dict.items():
        cols_to_select = ['id', 'accom1']
        optional_cols = ['old', 'accom_change']

        for col in optional_cols:
            if col in df.columns:
                cols_to_select.append(col)

        available_cols = [c for c in cols_to_select if c in df.columns]
        subset = df[available_cols].copy()
        subset['year_wave'] = int(year)

        dfs.append(subset)

    accom_history = pd.concat(dfs, ignore_index=True)
    accom_history = accom_history.sort_values(['id', 'year_wave'])

    numeric_cols = ['accom1', 'accom_change', 'old']
    for col in numeric_cols:
        if col in accom_history.columns:
            accom_history[col] = pd.to_numeric(accom_history[col], errors='coerce')

    # Carry forward last known accom1 (valid values: 1=Owner, 2=Tenant, 3=Cooperative)
    # Excludes -1 (dnk) and -2 (dna, i.e. question skipped because accom_change=0)
    accom_history['accom1_filled'] = accom_history['accom1'].where(
        accom_history['accom1'].notna() & (accom_history['accom1'] > 0)
    )
    accom_history['accom1_filled'] = accom_history.groupby('id')['accom1_filled'].ffill()

    return accom_history


def main():
    print("SHEDS Identifier History Extraction")
    print("=" * 60)
    print(f"Target variables: {', '.join(target_vars)}")
    print()

    # Read all waves once so we can pass to all functions
    all_waves_dict = {}
    for year, filename in sheds_files.items():
        filepath = data_dir / filename
        if not filepath.exists():
            print(f"  File not found: {filepath}")
            continue
        print(f"Reading {year}...")
        df, _ = read_clean_sheds(filepath)
        all_waves_dict[str(year)] = df

    if not all_waves_dict:
        print("\nNo data read - check file paths in config.yaml")
        return

    # Target vars history
    all_years = []
    for year, df in all_waves_dict.items():
        result = extract_year(Path(), int(year), target_vars, df=df)
        if result is not None:
            all_years.append(result)

    if all_years:
        history_df = pd.concat(all_years, ignore_index=True)
        cols_order = ['id', 'year'] + [v for v in target_vars if v in history_df.columns]
        history_df = history_df[cols_order].sort_values(['id', 'year']).reset_index(drop=True)

        print(f"\nTarget vars — records: {len(history_df)}, unique IDs: {history_df['id'].nunique()}")
        print(history_df.head(10).to_string())

        history_df.to_csv(data_dir / "sheds_identifier_history.csv", index=False)
        history_df.to_pickle(data_dir / "sheds_identifier_history.pkl")
        print(f"  Saved: sheds_identifier_history.csv / .pkl")

    # Car (fuel type) history ---
    car_history = build_car_history(all_waves_dict)
    print(f"\nCar history — records: {len(car_history)}, unique IDs: {car_history['id'].nunique()}")
    car_history.to_csv(data_dir / "sheds_car_history.csv", index=False)
    car_history.to_pickle(data_dir / "sheds_car_history.pkl")
    print(f"  Saved: sheds_car_history.csv / .pkl")

    # Accommodation (owner/tenant) history
    accom_history = build_accom_history(all_waves_dict)
    print(f"\nAccom history — records: {len(accom_history)}, unique IDs: {accom_history['id'].nunique()}")
    accom_history.to_csv(data_dir / "sheds_accom_history.csv", index=False)
    accom_history.to_pickle(data_dir / "sheds_accom_history.pkl")
    print(f"  Saved: sheds_accom_history.csv / .pkl")

    # Owner / tenant counts per year (using accom1_filled)
    label_map = {1: 'Owner', 2: 'Tenant', 3: 'Cooperative'}
    counts = (
        accom_history
        .groupby(['year_wave', 'accom1_filled'])
        .size()
        .unstack(fill_value=0)
        .rename(columns=label_map)
    )
    print("\nOwner / Tenant counts per year (accom1_filled):")
    print(counts.to_string())

    return history_df, car_history, accom_history


if __name__ == "__main__":
    df = main()