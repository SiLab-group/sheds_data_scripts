"""
SHEDS Identifier History - Wide Format
One row per ID + year with variable answers as columns
"""

import yaml
import pandas as pd
import pyreadstat
from pathlib import Path
from typing import Dict
from utils import read_clean_sheds, build_car_history, conditional_ffill

_root = Path(__file__).parents[2]
with open(_root / "config.yaml") as f:
    _config = yaml.safe_load(f)

data_dir = Path(_config["paths"]["data_dir"])
sheds_files = _config["sheds_files"]

# Target variables to find and make columns of
target_vars = ["accom3", "accom5", "heat5a1_2", "accom4a3", "accom9a1_1","accom9a1_2","accom9a1_3","accom9a1_4"]


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

    print("\naccom1 value counts (before filling):")
    for yr in [2016, 2017, 2018, 2019, 2020, 2021, 2023, 2025]:
        subset = accom_history[accom_history['year_wave'] == yr]['accom1']
        print(f"  {yr}: {subset.value_counts(dropna=False).sort_index().to_dict()}")

    # Mask invalid codes (-1 dnk, -2 dna) before filling
    accom_history['accom1_filled'] = accom_history['accom1'].where(
        accom_history['accom1'].notna() & (accom_history['accom1'] > 0)
    )
    # Carry forward only into rows where original accom1 was -2 (DNA),
    # and only when accom_change != 1 (no move/change reported)
    filled_parts = []
    for _, group in accom_history.groupby('id', sort=False):
        filled_parts.append(conditional_ffill(
            group, 'accom1_filled', 'accom_change',
            fill_when=(
                ((group['accom1'] == -2) & (group['year_wave'].isin([2018, 2019]))) |
                (group['accom1'].isna() & (group['year_wave'] == 2020))
            )
        ))
    accom_history['accom1_filled'] = pd.concat(filled_parts)

    return accom_history


def main():
    print("SHEDS Identifier History Extraction")
    print(f"Target variables: {', '.join(target_vars)}")

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

    # Accommodation (owner/tenant) history
    accom_history = build_accom_history(all_waves_dict)

    # Merge target vars into accom history
    if all_years:
        accom_history = accom_history.merge(
            history_df.rename(columns={'year': 'year_wave'}),
            on=['id', 'year_wave'],
            how='left'
        )

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

    # Car history
    car_history = build_car_history(all_waves_dict)
    print(f"\nCar history — records: {len(car_history)}, unique IDs: {car_history['id'].nunique()}")

    # Total vehicles per wave: sum of mob2_1 values where mob2_1 > 0 and < 90
    total_vehicles = {}
    for year, df in all_waves_dict.items():
        if 'mob2_1' in df.columns:
            mob2 = pd.to_numeric(df['mob2_1'], errors='coerce')
            total_vehicles[int(year)] = mob2[(mob2 > 0) & (mob2 < 90)].sum()
        else:
            total_vehicles[int(year)] = None

    # Fuel type / EV counts per year
    fuel_label_map = {
        1: 'Gasoline', 2: 'Diesel', 3: 'Natural Gas', 4: 'LPG',
        5: 'Hybrid Gas', 6: 'Plug-in Hybrid', 7: 'Hybrid Diesel',
        8: 'Electric', 9: 'Other'
    }
    fuel_counts = (
        car_history
        .groupby(['year_wave', 'mob3_3_filled'])
        .size()
        .unstack(fill_value=0)
        .rename(columns=fuel_label_map)
    )
    fuel_counts['Total Vehicles'] = pd.Series(total_vehicles)
    fuel_counts['EV %'] = (fuel_counts.get('Electric', 0) / fuel_counts['Total Vehicles'] * 100).round(2)
    hybrid_cols = [c for c in ['Hybrid Gas', 'Plug-in Hybrid', 'Hybrid Diesel'] if c in fuel_counts.columns]
    fuel_counts['Hybrid %'] = (fuel_counts[hybrid_cols].sum(axis=1) / fuel_counts['Total Vehicles'] * 100).round(2)
    print("\nFuel type counts per year (mob3_3_filled):")
    print(fuel_counts.to_string())

    return history_df, accom_history, car_history


if __name__ == "__main__":
    df = main()