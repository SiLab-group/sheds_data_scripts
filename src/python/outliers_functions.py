"""
Outlier detection functions for SHEDS data analysis.
Converted from R to Python.
"""

import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import Optional


def find_scale_variables(data: pd.DataFrame, min_items: int = 3, max_unique: int = 10, verbose: bool = True) -> list:
    """
    Find Likert-scale variables in a dataframe by looking for numeric columns
    with a limited number of unique values arranged in batteries (shared prefix).

    Parameters
    ----------
    data : pd.DataFrame
    min_items : int
        Minimum number of items required per battery
    max_unique : int
        Maximum number of unique values for a column to be considered a scale
    verbose : bool

    Returns
    -------
    list of column names belonging to valid scale batteries
    """
    scale_vars = []
    exclude_pattern = re.compile(r'^(id|time\d|age|zip|finished|screen|q_|md_|gr$)')

    for col in data.columns:
        if pd.api.types.is_numeric_dtype(data[col]):
            non_missing = data[col].dropna()
            unique_vals = non_missing.nunique()
            n_valid = len(non_missing)
            if unique_vals >= 2 and unique_vals <= max_unique and n_valid >= 10:
                if not exclude_pattern.match(col):
                    scale_vars.append(col)

    # Extract prefixes (everything before the last _number pattern)
    prefixes = list(dict.fromkeys(
        re.sub(r'_[0-9]+[a-z]*$', '', v) for v in scale_vars
    ))

    valid_prefixes = []
    scale_batteries = {}

    for prefix in prefixes:
        pattern = re.compile(r'^' + re.escape(prefix) + r'_[0-9]+')
        items = [v for v in scale_vars if pattern.match(v)]
        if len(items) >= min_items:
            valid_prefixes.append(prefix)
            scale_batteries[prefix] = items

    final_vars = []
    for prefix in valid_prefixes:
        final_vars.extend(scale_batteries[prefix])

    if verbose and len(final_vars) > 0:
        print(f"Found {len(final_vars)} scale variables from {len(valid_prefixes)} scale batteries:")
        for prefix in valid_prefixes:
            print(f"  - {prefix}: {len(scale_batteries[prefix])} items")
        print()
    elif verbose:
        print("No scale variables detected\n")

    return final_vars


def detect_straightlining(data: pd.DataFrame, scale_vars: list, threshold: float = 1.0, verbose: bool = True) -> pd.DataFrame:
    """
    Detect respondents who gave the same answer to all scale questions (straightliners).

    Parameters
    ----------
    data : pd.DataFrame
        Must contain an 'id' column
    scale_vars : list
        List of scale variable column names
    threshold : float
        Proportion of same responses required (1.0 = all same)
    verbose : bool

    Returns
    -------
    pd.DataFrame with columns ['id', 'straightline']
    Attributes stored: 'coverage_stats', 'summary_stats', 'straightline_summary_stats'
    """
    straightline_flags = pd.DataFrame({'id': data['id'], 'straightline': False})

    if len(scale_vars) == 0:
        return straightline_flags

    n_respondents_total = len(data)
    n_got_questions = 0
    n_straightliners = 0
    n_straightliners_got_questions = 0

    question_coverage = pd.DataFrame({
        'question': scale_vars,
        'n_got_question': 0,
        'pct_got_question': 0.0,
        'n_answered': 0,
        'pct_answered': 0.0
    })

    # Per-person straightlining
    existing_scale_vars = [v for v in scale_vars if v in data.columns]

    for i in range(len(data)):
        responses = pd.to_numeric(data.iloc[i][existing_scale_vars], errors='coerce').values

        n_got_question = int(np.sum(~np.isnan(responses) & (responses != -2)))
        got_enough_questions = n_got_question > 2
        if got_enough_questions:
            n_got_questions += 1

        responses_valid = responses[
            ~np.isnan(responses) &
            (responses != 0) &
            (responses != -1) &
            (responses != -2)
        ]

        if len(responses_valid) > 2:
            values, counts = np.unique(responses_valid, return_counts=True)
            max_freq = counts.max()
            prop_same = max_freq / len(responses_valid)

            if prop_same >= threshold:
                straightline_flags.loc[straightline_flags.index[i], 'straightline'] = True
                n_straightliners += 1
                if got_enough_questions:
                    n_straightliners_got_questions += 1

    # Per-question coverage
    for j, var in enumerate(scale_vars):
        if var in data.columns:
            col = pd.to_numeric(data[var], errors='coerce')
            n_got = int(((~col.isna()) & (col != -2)).sum())
            question_coverage.loc[j, 'n_got_question'] = n_got
            question_coverage.loc[j, 'pct_got_question'] = 100 * n_got / n_respondents_total

            n_answered = int(((~col.isna()) & (col != 0) & (col != -1) & (col != -2)).sum())
            question_coverage.loc[j, 'n_answered'] = n_answered
            question_coverage.loc[j, 'pct_answered'] = 100 * n_answered / n_respondents_total

    if verbose:
        print("\n--- Straightlining Detection Results ---")
        print(f"Total respondents: {n_respondents_total}")
        pct_got = 100 * n_got_questions / n_respondents_total if n_respondents_total > 0 else 0
        print(f"Respondents who got >2 questions: {n_got_questions} ({pct_got:.1f}%)")

        print(f"\nStraightliners detected: {n_straightliners}")
        if n_straightliners > 0:
            pct_sl_got = 100 * n_straightliners_got_questions / n_straightliners
            print(f"  • Of these, {n_straightliners_got_questions} ({pct_sl_got:.1f}%) got >2 questions")
        pct_of_total = 100 * n_straightliners / n_respondents_total if n_respondents_total > 0 else 0
        pct_of_applicable = 100 * n_straightliners / n_got_questions if n_got_questions > 0 else 0
        print(f"  • {pct_of_total:.1f}% of total respondents")
        print(f"  • {pct_of_applicable:.1f}% of those who got >2 questions")

        avg_got = question_coverage['pct_got_question'].mean()
        avg_ans = question_coverage['pct_answered'].mean()
        print(f"\nQuestion coverage:")
        print(f"  • Average {avg_got:.1f}% got each question (not -2)")
        print(f"  • Average {avg_ans:.1f}% answered each question validly")

        low_cov = question_coverage.nsmallest(3, 'pct_got_question')
        print("\nQuestions with lowest coverage (who got them):")
        for _, row in low_cov.iterrows():
            print(f"  {row['question']}: {row['pct_got_question']:.1f}% got it, {row['pct_answered']:.1f}% answered")
        print()

    summary_stats = {
        'n_total': n_respondents_total,
        'n_got_questions': n_got_questions,
        'n_straightliners': n_straightliners,
        'n_straightliners_got_questions': n_straightliners_got_questions,
        'pct_of_total': 100 * n_straightliners / n_respondents_total if n_respondents_total > 0 else 0,
        'pct_of_applicable': 100 * n_straightliners / n_got_questions if n_got_questions > 0 else 0,
    }
    straightline_flags.attrs['coverage_stats'] = question_coverage
    straightline_flags.attrs['summary_stats'] = summary_stats
    straightline_flags.attrs['straightline_summary_stats'] = summary_stats

    return straightline_flags


def detect_inconsistencies(data: pd.DataFrame) -> pd.DataFrame:
    """
    Detect logically inconsistent responses across several survey variables.

    Parameters
    ----------
    data : pd.DataFrame
        Must contain an 'id' column

    Returns
    -------
    pd.DataFrame with columns ['id', 'inconsistent', 'inconsistency_types']
    """
    consistency_flags = pd.DataFrame({
        'id': data['id'],
        'inconsistent': False,
        'inconsistency_types': ''
    })

    def flag_inconsistency(condition: pd.Series, itype: str):
        condition = condition.fillna(False).astype(bool)
        idx = condition[condition].index
        consistency_flags.loc[idx, 'inconsistent'] = True
        existing = consistency_flags.loc[idx, 'inconsistency_types']
        consistency_flags.loc[idx, 'inconsistency_types'] = existing.apply(
            lambda x: itype if x == '' else f"{x}; {itype}"
        )

    # Age vs age group (agegr: 1=18-34, 2=35-54, 3=55+)
    if 'age' in data.columns and 'agegr' in data.columns:
        age = pd.to_numeric(data['age'], errors='coerce')
        agegr = pd.to_numeric(data['agegr'], errors='coerce')
        age_inconsistent = (
            ((age < 18) & agegr.isin([1, 2, 3])) |
            ((age >= 18) & (age <= 34) & (agegr != 1)) |
            ((age >= 35) & (age <= 54) & (agegr != 2)) |
            ((age >= 55) & (agegr != 3))
        )
        flag_inconsistency(age_inconsistent, 'age_mismatch')

    # Car ownership vs usage
    if 'mob2_1' in data.columns and 'mob11a' in data.columns:
        mob2_1 = pd.to_numeric(data['mob2_1'], errors='coerce')
        mob11a = pd.to_numeric(data['mob11a'], errors='coerce')
        flag_inconsistency((mob2_1 == 0) & (mob11a == 1), 'no_car_but_uses_car')

    # Motorbike ownership vs usage
    if 'mob2_2' in data.columns and 'mob11a' in data.columns:
        mob2_2 = pd.to_numeric(data['mob2_2'], errors='coerce')
        mob11a = pd.to_numeric(data['mob11a'], errors='coerce')
        flag_inconsistency((mob2_2 == 0) & (mob11a == 7), 'no_motorbike_but_uses_motorbike')

    # Airplane travel vs spending
    if all(c in data.columns for c in ['mob13_1', 'mob13_2', 'mob14']):
        mob13_1 = pd.to_numeric(data['mob13_1'], errors='coerce')
        mob13_2 = pd.to_numeric(data['mob13_2'], errors='coerce')
        mob14 = pd.to_numeric(data['mob14'], errors='coerce')
        flag_inconsistency(
            (mob13_1 == 0) & (mob13_2 == 0) & (mob14 > 0) & mob14.notna(),
            'no_flights_but_spending'
        )

    # Work status vs workplace ZIP
    if 'mob11a' in data.columns and 'seco4_1' in data.columns:
        mob11a = pd.to_numeric(data['mob11a'], errors='coerce')
        seco4_1 = pd.to_numeric(data['seco4_1'], errors='coerce')
        flag_inconsistency(
            (mob11a == 6) & seco4_1.notna() & (seco4_1 != -2),
            'no_work_but_workplace_zip'
        )

    # Household size consistency (gender totals vs age totals)
    gender_cols = ['seco1b_5', 'seco1b_6', 'seco1b_7']
    age_cols = ['seco1b_1', 'seco1b_2', 'seco1b_3', 'seco1b_4']
    if all(c in data.columns for c in gender_cols + age_cols):
        gender_total = data[gender_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
        age_total = data[age_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
        flag_inconsistency(gender_total != age_total, 'household_size_mismatch')

    # Working persons vs household adults
    work_cols = ['seco2_1', 'seco2_2', 'seco2_3']
    adult_cols = ['seco1b_3', 'seco1b_4']
    if all(c in data.columns for c in work_cols + adult_cols):
        working_persons = data[work_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
        adults = data[adult_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
        flag_inconsistency(working_persons > adults, 'more_workers_than_adults')

    return consistency_flags


def run_outlier_detection(data: pd.DataFrame) -> pd.DataFrame:
    """
    Run the full outlier detection pipeline on a single wave.

    Checks:
      - Timing speeders (bottom 5% of q_totalduration)
      - Logical inconsistencies
      - Straightlining on psy4_1..psy4_16

    Parameters
    ----------
    data : pd.DataFrame

    Returns
    -------
    pd.DataFrame with columns: id, timing_speeder, inconsistent,
        inconsistency_types, straightline, risk_score
    """
    scale_vars = [f'psy4_{i}' for i in range(1, 17)]
    scale_vars = [v for v in scale_vars if v in data.columns]

    print(f"Used {len(scale_vars)} scale variables for analysis\n")
    print(f"Used scale_vars: \n{scale_vars}\n")

    results = pd.DataFrame({'id': data['id']})

    # Timing speeders (bottom 5%)
    if 'q_totalduration' in data.columns:
        print("Timing based: total duration")
        fast_threshold = data['q_totalduration'].quantile(0.05)
        results['timing_speeder'] = (
            data['q_totalduration'].le(fast_threshold) & data['q_totalduration'].notna()
        )
        n_speeders = results['timing_speeder'].sum()
        print(f"Timing speeders (bottom 5%): {n_speeders}  Fast threshold: {fast_threshold}")

    # Consistency checks
    consistency_result = detect_inconsistencies(data)
    results = results.merge(consistency_result, on='id', how='left')
    print(f"Inconsistent responses: {results['inconsistent'].sum()}")

    # Straightlining
    if len(scale_vars) > 0:
        print(f"Straightliners: {results.get('straightline', pd.Series(dtype=bool)).sum()}")
        straightline_result = detect_straightlining(data, scale_vars)
        results = results.merge(straightline_result, on='id', how='left')
        results.attrs['straightline_summary_stats'] = straightline_result.attrs.get('straightline_summary_stats', {})

    # Composite risk score
    flag_vars = [v for v in ['timing_speeder', 'straightline', 'inconsistent'] if v in results.columns]
    if len(flag_vars) == 0:
        results['risk_score'] = 0
    else:
        results['risk_score'] = results[flag_vars].fillna(False).astype(int).sum(axis=1)

    return results


def plot_completion_distribution(threshold_data: pd.DataFrame, wave_name: str = "SHEDS", show_plot: bool = True):
    """
    Plot the completion time distribution for a single wave with threshold annotations.

    Parameters
    ----------
    threshold_data : pd.DataFrame
        Must contain 'q_totalduration' column
    wave_name : str
    show_plot : bool
        If True, call plt.show()

    Returns
    -------
    matplotlib.figure.Figure
    """
    fast_threshold = threshold_data['q_totalduration'].quantile(0.05)
    duration = threshold_data['q_totalduration'].dropna()
    mean_time = duration.mean()
    median_time = duration.median()
    n_speeders = int((threshold_data['q_totalduration'].le(fast_threshold) & threshold_data['q_totalduration'].notna()).sum())
    pct_speeders = (n_speeders / len(threshold_data)) * 100

    fig, ax = plt.subplots(figsize=(10, 6))

    # Histogram
    ax.hist(duration, bins=50, color='steelblue', alpha=0.7, edgecolor='white')

    # Shaded speeder region
    ax.axvspan(duration.min(), fast_threshold, alpha=0.2, color='red', zorder=0)

    # Reference lines
    ax.axvline(10, color='gray', linestyle='dotted', linewidth=1)
    ax.axvline(60, color='gray', linestyle='dotted', linewidth=1)
    ax.axvline(mean_time, color='darkblue', linestyle='solid', linewidth=1)

    # Mean annotation
    ax.annotate(
        f'Mean\n{mean_time:.1f} min',
        xy=(mean_time, ax.get_ylim()[1]),
        xytext=(mean_time + 1, ax.get_ylim()[1] * 0.85),
        color='darkblue', fontsize=9
    )

    ax.set_xlim(10, 100)
    ax.set_xticks(range(10, 101, 10))
    ax.set_title(f'Completion Time Distribution - {wave_name}', fontweight='bold', fontsize=14)
    ax.set_subtitle = None
    ax.set_xlabel('Completion Time (minutes)')
    ax.set_ylabel('Number of Respondents')
    fig.suptitle(
        f'Mean: {mean_time:.1f} min | Median: {median_time:.1f} min | 5% threshold: {fast_threshold:.1f} min',
        fontsize=10, color='gray', y=0.94
    )

    ax.grid(True, alpha=0.3)

    if show_plot:
        plt.tight_layout()
        plt.show()
        plt.close(fig)

    # Print summary statistics
    print("\n=== COMPLETION TIME SUMMARY ===")
    print(f"Wave: {wave_name}")
    print(f"Total respondents: {len(duration)}")
    print(f"Mean: {mean_time:.2f} minutes")
    print(f"Median: {median_time:.2f} minutes")
    print(f"SD: {duration.std():.2f} minutes")
    print(f"Range: {duration.min():.1f} - {duration.max():.1f} minutes")
    print("\nPercentiles:")
    print(duration.quantile([0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]))
    print(f"\n5% threshold (after 10-60 filter): {fast_threshold:.2f} minutes")
    print(f"Speeders flagged: {n_speeders} ({pct_speeders:.2f}%)")
    print(f"Speeders complete in {100 * fast_threshold / mean_time:.1f}% of mean time")

    return fig


def plot_waves_ridges(waves_data):
    """
    Plot completion time distributions as a ridge/KDE plot across waves.

    Parameters
    ----------
    waves_data : dict or pd.DataFrame
        Either a dict mapping wave name -> DataFrame (each with q_totalduration),
        or a combined DataFrame with columns Wave and q_totalduration.

    Returns
    -------
    matplotlib.figure.Figure
    """
    import matplotlib.cm as cm

    if isinstance(waves_data, pd.DataFrame):
        combined_data = waves_data[['Wave', 'q_totalduration']].copy()
        combined_data = combined_data.rename(columns={'q_totalduration': 'Duration'})
        thresholds = (
            waves_data.groupby('Wave')['q_totalduration']
            .quantile(0.05)
            .reset_index()
            .rename(columns={'q_totalduration': 'Threshold'})
        )
    else:
        rows = []
        thresh_rows = []
        for wave_name, df in waves_data.items():
            rows.append(pd.DataFrame({'Wave': wave_name, 'Duration': df['q_totalduration']}))
            thresh_rows.append({'Wave': wave_name, 'Threshold': df['q_totalduration'].quantile(0.05)})
        combined_data = pd.concat(rows, ignore_index=True)
        thresholds = pd.DataFrame(thresh_rows)

    # Reverse order for ridge plot (most recent on top)
    wave_order = list(dict.fromkeys(combined_data['Wave']))[::-1]
    combined_data['Wave'] = pd.Categorical(combined_data['Wave'], categories=wave_order, ordered=True)
    thresholds['Wave'] = pd.Categorical(thresholds['Wave'], categories=wave_order, ordered=True)

    n_waves = len(wave_order)
    colors = plt.cm.Set2(np.linspace(0, 1, n_waves))

    fig, ax = plt.subplots(figsize=(10, n_waves * 1.2 + 2))

    for idx, wave in enumerate(wave_order):
        wave_dur = combined_data.loc[combined_data['Wave'] == wave, 'Duration'].dropna()
        wave_dur = wave_dur[(wave_dur >= 0) & (wave_dur <= 100)]

        if len(wave_dur) < 2:
            continue

        from scipy.stats import gaussian_kde
        kde = gaussian_kde(wave_dur)
        x = np.linspace(0, 100, 300)
        y = kde(x)
        scale = 1.5 / y.max() if y.max() > 0 else 1
        y_scaled = y * scale

        base = idx
        ax.fill_between(x, base, base + y_scaled, alpha=0.7, color=colors[idx])
        ax.plot(x, base + y_scaled, color=colors[idx], linewidth=0.8)

        # 5th percentile threshold marker
        thr_row = thresholds[thresholds['Wave'] == wave]
        if not thr_row.empty:
            thr = thr_row['Threshold'].values[0]
            thr_y = kde(np.array([thr]))[0] * scale
            ax.plot(thr, base + thr_y, 'D', color='red', markersize=6, zorder=5)

    # Reference lines
    ax.axvline(10, linestyle='dotted', color='gray', alpha=0.5)
    ax.axvline(60, linestyle='dotted', color='gray', alpha=0.5)

    ax.set_yticks(range(n_waves))
    ax.set_yticklabels(wave_order)
    ax.set_xlim(0, 100)
    ax.set_xlabel('Completion Time (minutes)')
    ax.set_ylabel('SHEDS Wave')
    ax.set_title('Completion Time Distributions by Wave', fontweight='bold', fontsize=14)
    ax.set_subtitle = None
    fig.text(0.5, 0.96,
             'Red diamonds mark the 5th percentile timing threshold',
             ha='center', fontsize=10, color='gray')

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    return fig


def get_straightliner_details(data: pd.DataFrame, wave_name: str,
                               scale_vars: Optional[list] = None) -> Optional[pd.DataFrame]:
    """
    Get detailed information about straightlining respondents for a single wave.

    Parameters
    ----------
    data : pd.DataFrame
    wave_name : str
    scale_vars : list, optional
        Defaults to psy4_1..psy4_16

    Returns
    -------
    pd.DataFrame or None
    """
    if scale_vars is None:
        scale_vars = [f'psy4_{i}' for i in range(1, 17)]

    straightline_result = detect_straightlining(data, scale_vars, verbose=False)

    merged = data.merge(straightline_result[['id', 'straightline']], on='id', how='inner')
    straightliners = merged[merged['straightline'] == True].copy()

    if len(straightliners) == 0:
        print(f"No straightliners found in {wave_name}")
        return None

    details = pd.DataFrame({'wave': wave_name, 'id': straightliners['id'].values})

    for var in scale_vars:
        if var in straightliners.columns:
            details[var] = straightliners[var].values

    # Compute per-person statistics
    details['most_common_value'] = np.nan
    details['frequency'] = np.nan
    details['proportion'] = np.nan
    details['n_valid_responses'] = np.nan

    existing_vars = [v for v in scale_vars if v in details.columns]

    for i in range(len(details)):
        responses = pd.to_numeric(details.iloc[i][existing_vars], errors='coerce').values
        valid = responses[
            ~np.isnan(responses) &
            (responses != 0) &
            (responses != -1) &
            (responses != -2)
        ]
        if len(valid) > 0:
            values, counts = np.unique(valid, return_counts=True)
            max_idx = np.argmax(counts)
            details.loc[details.index[i], 'most_common_value'] = values[max_idx]
            details.loc[details.index[i], 'frequency'] = counts[max_idx]
            details.loc[details.index[i], 'proportion'] = counts[max_idx] / len(valid)
            details.loc[details.index[i], 'n_valid_responses'] = len(valid)

    return details


def analyze_all_straightliners(waves_filtered: dict) -> dict:
    """
    Analyze straightliners across all waves.

    Parameters
    ----------
    waves_filtered : dict
        Mapping of wave name -> pd.DataFrame

    Returns
    -------
    dict mapping wave name -> details DataFrame
    """
    all_straightliners = {}

    for wave_name, df in waves_filtered.items():
        print(f"\n=== WAVE {wave_name} ===")
        details = get_straightliner_details(df, wave_name)

        if details is not None:
            all_straightliners[wave_name] = details

            print(f"Found {len(details)} straightliners")
            print("\nDistribution of most common value:")
            print(details['most_common_value'].value_counts().sort_index())
            print("\nProportion statistics:")
            print(details['proportion'].describe())

            print("\nFirst 5 straightliners:")
            summary_cols = ['id', 'most_common_value', 'frequency', 'proportion', 'n_valid_responses']
            print(details[summary_cols].head(5).to_string(index=False))

    return all_straightliners
