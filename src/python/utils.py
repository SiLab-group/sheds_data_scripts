"""
Utility functions for SHEDS data analysis.
Converted from R to Python.
"""

import pandas as pd
import numpy as np
import pyreadstat
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional, Dict, Any



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
    df, meta = pyreadstat.read_sav(filepath, encoding='UTF-8', apply_value_formats=False)
    df = df[df['screen'] != 3].copy()
    return df, meta



def get_data_summary(data: pd.DataFrame) -> Dict[str, Any]:
    """
    Get summary statistics for SHEDS data.
    Filters to respondents with duration between 1 and 60 minutes.
    """
    clean_data = data[(data['q_totalduration'] >= 1) & (data['q_totalduration'] <= 60)].copy()
    
    completion_rate = None
    if 'finished' in clean_data.columns:
        completion_rate = (clean_data['finished'] == 1).mean() * 100
    
    avg_duration = None
    if 'q_totalduration' in clean_data.columns:
        avg_duration = clean_data['q_totalduration'].mean()
    
    return {
        'n_respondents': len(clean_data),
        'n_variables': len(clean_data.columns),
        'completion_rate': completion_rate,
        'avg_duration': avg_duration
    }



def save_plot(plot, path: str = "plots", filename: str = "plot", 
              width: float = 12, height: float = 8) -> None:
    """
    Save plot in PDF and EPS formats.
    
    Parameters
    ----------
    plot : matplotlib Figure
        Matplotlib figure object
    path : str
        Output directory path
    filename : str
        Base filename (without extension)
    width : float
        Width in inches
    height : float
        Height in inches
    """
    output_path = Path(path)
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
    
    plot.set_size_inches(width, height)
    
    # Save as PDF
    plot.savefig(output_path / f"{filename}.pdf", format='pdf', bbox_inches='tight', facecolor='white')

    # Save as EPS
    plot.savefig(output_path / f"{filename}.eps", format='eps', bbox_inches='tight', facecolor='white')

    plt.close(plot)
    print(f"Saved: {filename}.pdf and .eps")



def conditional_ffill(group: pd.DataFrame, value_col: str, change_col: str,
                       fill_when: pd.Series | None = None) -> pd.Series:
    """
    Forward-fill value_col only when change_col != 1.

    Fill conditions:
      - change_col == 0   : no change reported          → fill
      - change_col is NaN : new respondent / not shown  → fill
      - change_col == 1   : change happened             → keep NaN
                            (new value should be explicitly provided)

    Parameters
    ----------
    group : pd.DataFrame
        Single-person group (already sorted by year_wave)
    value_col : str
        Column to fill (e.g. 'mob3_3_filled', 'accom1_filled')
    change_col : str
        Column indicating whether a change occurred (e.g. 'mob3_change', 'accom_change')
    fill_when : pd.Series or None
        Boolean mask (aligned to group index) restricting which rows are eligible
        for filling. If None, any NaN row is eligible (original behaviour).
    """
    result = group[value_col].copy()
    change = group[change_col] if change_col in group.columns else pd.Series(np.nan, index=group.index)
    last_known = np.nan
    for idx in result.index:
        if pd.notna(result.loc[idx]):
            last_known = result.loc[idx]    # update last known valid value
        elif (fill_when is None or fill_when.loc[idx]) and change.loc[idx] != 1:
            result.loc[idx] = last_known
        # change_col == 1, or fill_when is False → leave as NaN
    return result


def build_car_history(all_waves_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Build car history across all waves with conditional carry-forward logic.

    Matches R build_car_history_stata: mob3_3 is only carried forward when
    mob3_change != 1 (i.e. no car change reported, or question not shown to
    new respondents). When mob3_change == 1 the person changed cars and their
    new fuel type must be explicitly provided — we do NOT fill those rows.

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

    # Mask invalid codes (-1 dnk, -2 dna) before filling
    car_history['mob3_3_filled'] = car_history['mob3_3'].where(
        car_history['mob3_3'].notna() & (car_history['mob3_3'] > 0)
    )
    # Conditionally carry forward: only when mob3_change != 1
    car_history['mob3_3_filled'] = (
        car_history.groupby('id', group_keys=False)
        .apply(lambda g: conditional_ffill(g, 'mob3_3_filled', 'mob3_change'))
    )

    if 'mob2_e' in car_history.columns:
        car_history['mob2_e_filled'] = car_history['mob2_e'].where(
            car_history['mob2_e'].notna() & (car_history['mob2_e'] >= 0)
        )
        car_history['mob2_e_filled'] = (
            car_history.groupby('id', group_keys=False)
            .apply(lambda g: conditional_ffill(g, 'mob2_e_filled', 'mob3_change'))
        )

    return car_history


def check_finished(data: pd.DataFrame, year: int) -> Optional[pd.DataFrame]:
    """
    Check finished respondents for a given year.
    """
    print(f"\n=== Year {year} ===")
    
    if 'finished' in data.columns:
        total_respondents = len(data)
        finished_count = (data['finished'] == 1).sum()
        
        print(f"Total respondents: {total_respondents}")
        print(f"Finished respondents: {finished_count}")
        print(f"Completion rate: {finished_count / total_respondents:.1%}")
        
        print("\nFinished column distribution:")
        print(data['finished'].value_counts(dropna=False))
        
        return pd.DataFrame({
            'year': [year],
            'total': [total_respondents],
            'finished': [finished_count]
        })
    else:
        print("No 'finished' column found!")
        print(f"Available columns: {', '.join(data.columns[:10])}...")
        return None


def analyze_ev_ownership_data(data_history: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Analyze EV ownership for a specific year using car history data.
    
    Parameters
    ----------
    data_history : pd.DataFrame
        Car history dataframe from build_car_history
    year : int
        Year to analyze
        
    Returns
    -------
    pd.DataFrame
        Summary statistics for EV ownership
    """
    print(f"\n For Year {year}")
    
    data_finished = data_history[data_history['year_wave'] == year].copy()
    
    # Car ownership: mob2_1 > 0 & mob2_1 < 90
    car_owners = np.nan
    if 'mob2_1' in data_finished.columns:
        mask = (data_finished['mob2_1'] > 0) & (data_finished['mob2_1'] < 90)
        car_owners = mask.sum()
    
    # How many changed the car
    changed_car = np.nan
    if 'mob3_change' in data_finished.columns:
        mask = (
            (data_finished['mob3_change'] == 1) & 
            (data_finished['mob2_1'] > 0) & 
            (data_finished['mob2_1'] < 90)
        )
        changed_car = mask.sum()
    
    # New car owners (old == 0)
    new_car_owners = np.nan
    if 'mob2_1' in data_finished.columns and 'old' in data_finished.columns:
        mask = (
            (data_finished['mob2_1'] > 0) & 
            (data_finished['mob2_1'] < 90) & 
            (data_finished['old'] == 0)
        )
        new_car_owners = mask.sum()
    
    # EV main car (mob3_3_filled == 8)
    ev_main = np.nan
    if 'mob3_3_filled' in data_finished.columns:
        ev_main = (data_finished['mob3_3_filled'] == 8).sum()
    
    # EV secondary (mob2_e == 1)
    ev_secondary = np.nan
    if 'mob2_e' in data_finished.columns:
        ev_secondary = (data_finished['mob2_e'] == 1).sum()
    
    # Hybrids (mob3_3_filled == 5 or 6 for gas, 7 for diesel)
    hybrid_gas = np.nan
    if 'mob3_3_filled' in data_finished.columns:
        hybrid_gas = ((data_finished['mob3_3_filled'] == 5) | 
                      (data_finished['mob3_3_filled'] == 6)).sum()
    
    hybrid_diesel = np.nan
    if 'mob3_3_filled' in data_finished.columns:
        hybrid_diesel = (data_finished['mob3_3_filled'] == 7).sum()
    
    # Total EVs
    total_ev = np.nansum([ev_main, ev_secondary])
    
    n_total = len(data_finished)
    
    print(f"Total respondents: {n_total}")
    print(f"Car owners: {car_owners}")
    print(f"EVs (main): {ev_main if not np.isnan(ev_main) else 'N/A'}")
    print(f"EVs (secondary): {ev_secondary if not np.isnan(ev_secondary) else 'N/A'}")
    print(f"Total EVs: {total_ev}")
    print(f"Hybrids: {np.nansum([hybrid_gas, hybrid_diesel])}")
    print(f"Changed the car: {changed_car}")
    print(f"New respondents: {new_car_owners}\n")
    
    # Calculate rates
    ev_rate_all = total_ev / n_total if n_total > 0 else np.nan
    ev_rate_car_owners = total_ev / car_owners if not np.isnan(car_owners) and car_owners > 0 else np.nan
    
    return pd.DataFrame({
        'year': [year],
        'n_total': [n_total],
        'n_car_owners': [car_owners],
        'n_ev_main': [ev_main if not np.isnan(ev_main) else 0],
        'n_ev_secondary': [ev_secondary if not np.isnan(ev_secondary) else 0],
        'n_ev_total': [total_ev],
        'n_hybrid_gas': [hybrid_gas if not np.isnan(hybrid_gas) else 0],
        'n_hybrid_diesel': [hybrid_diesel if not np.isnan(hybrid_diesel) else 0],
        'ev_rate_all': [ev_rate_all],
        'ev_rate_car_owners': [ev_rate_car_owners],
        'n_changed_car': [changed_car],
        'new_respondents': [new_car_owners]
    })
