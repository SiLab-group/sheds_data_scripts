"""
SHEDS Survey Timeline Visualization with Variable Counts
=========================================================
Creates a Gantt-style timeline showing which variable categories 
are available in each survey year, with counts displayed on each bar.

Input: sheds_questions_up2025.csv
"""

import yaml
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re
from pathlib import Path
from matplotlib.patches import Patch

_root = Path(__file__).parents[2]
with open(_root / "config.yaml") as f:
    _config = yaml.safe_load(f)

INPUT_FILE = _root / _config["paths"]["questions_csv"]

# First we define the category names
# Category labels (prefix -> readable name)
CATEGORY_LABELS = {
    'accom': 'Housing',
    'mob': 'Mobility',
    'elec': 'Electricity',
    'renov': 'Renovation',
    'heat': 'Heating',
    'seco': 'Socio-Economic',
    'soc': 'Social',
    'psy': 'Psychology',
    'envpsy': 'Env. Psychology',
    'enlit': 'Energy Literacy',
    'covid': 'COVID-19',
    'votations': 'Voting',
    'gr': 'Region',
    'minyearforrenov': 'Renov. Year'
}

# Prefix remapping (merge related categories)
PREFIX_REMAP = {
    'mistee': 'renov',  # MISTEE questions are renovation-related
    'minyearforrenov': 'renov',
    'gr': 'seco',
}

# Domain groupings
DOMAIN_GROUPS = {
    'Buildings': ['accom', 'elec', 'heat', 'renov', 'minyearforrenov'],
    'Mobility': ['mob'],
    'Attitudes, values and knowledge': ['psy', 'envpsy', 'enlit'],
    'Demographics & Social': ['soc', 'seco', 'gr'],
    'Special Topics': ['covid', 'votations']
}

# Domain colors
DOMAIN_COLORS = {
    'Buildings': '#2E86AB',
    'Mobility': '#A23B72',
    'Attitudes, values and knowledge': '#F18F01',
    'Demographics & Social': '#44AF69',
    'Special Topics': '#C73E1D'
}

# Font sizes — adjust here to rescale all text uniformly
FONT = {
    'bar_count':    16,   # count numbers inside bars
    'tick_labels':  16,   # y-axis category names & x-axis years
    'axis_label':   16,   # "Survey Year" x-axis title
    'domain_label': 16,   # domain group labels on the right
    'legend':       16,   # legend entries at the bottom
}

# Build category -> domain mapping
CAT_TO_DOMAIN = {}
for domain, cats in DOMAIN_GROUPS.items():
    for cat in cats:
        CAT_TO_DOMAIN[cat] = domain

# Survey years
YEARS = ['2016', '2017', '2018', '2019', '2020', '2021', '2023', '2025']


def get_prefix(question_id):
    """Extract category prefix from question ID."""
    match = re.match(r'^([a-z]+)', str(question_id).lower())
    prefix = match.group(1) if match else 'other'
    # Apply remapping (e.g., mistee -> renov)
    return PREFIX_REMAP.get(prefix, prefix)
    # return match.group(1) if match else 'other'


def load_and_process_data(filepath):
    """Load CSV and add category column."""
    df = pd.read_csv(filepath)
    df['category'] = df['question_id'].apply(get_prefix)
    return df


def create_timeline_with_counts(df, output_base='sheds_timeline_counts',
                                formats=['pdf', 'eps', 'png']):
    """
    Create Gantt-style timeline with variable counts on each bar.

    Parameters:
    -----------
    df : DataFrame
        Processed dataframe with 'category' column
    output_base : str
        Base filename for output (without extension)
    formats : list
        List of output formats ('pdf', 'eps', 'png')
    """

    year_cols = [c for c in df.columns if c in YEARS]

    # Get counts per category per year
    category_counts = df.groupby('category')[year_cols].sum()
    cat_presence = category_counts > 0

    # Order categories by domain, then by total coverage (descending)
    ordered_cats = []
    for domain in DOMAIN_GROUPS.keys():
        cats = [c for c in DOMAIN_GROUPS[domain] if c in cat_presence.index]
        cats_sorted = sorted(cats, key=lambda x: -cat_presence.loc[x].sum())
        ordered_cats.extend(cats_sorted)

    cat_presence_ordered = cat_presence.loc[ordered_cats]
    category_counts_ordered = category_counts.loc[ordered_cats]
    year_positions = {y: i for i, y in enumerate(year_cols)}

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 8))
    bar_height = 0.6

    # Draw bars with counts
    for i, cat in enumerate(ordered_cats):
        domain = CAT_TO_DOMAIN.get(cat, 'Special Topics')
        color = DOMAIN_COLORS.get(domain, '#888888')

        for y in year_cols:
            if cat_presence_ordered.loc[cat, y]:
                x = year_positions[y]
                count = int(category_counts_ordered.loc[cat, y])

                # Draw bar
                ax.barh(i, 0.8, left=x - 0.4, height=bar_height,
                        color=color, edgecolor='white', linewidth=0.5)

                # Add count text on the bar
                ax.text(x, i, str(count), ha='center', va='center',
                        fontsize=FONT['bar_count'], color='white', fontweight='bold')

    # Add domain separators
    current_domain = None
    domain_starts = []
    for i, cat in enumerate(ordered_cats):
        cat_domain = CAT_TO_DOMAIN.get(cat, 'Special Topics')
        if cat_domain != current_domain:
            if current_domain is not None:
                ax.axhline(y=i - 0.5, color='gray', linewidth=1,
                           linestyle='-', alpha=0.3)
            domain_starts.append((i, cat_domain))
            current_domain = cat_domain

    ax.set_yticks(range(len(ordered_cats)))
    ax.set_yticklabels([CATEGORY_LABELS.get(c, c) for c in ordered_cats], fontsize=FONT['tick_labels'])

    ax.set_xticks(range(len(year_cols)))
    ax.set_xticklabels(year_cols, fontsize=FONT['tick_labels'])
    ax.set_xlim(-0.6, len(year_cols) - 0.4)
    ax.set_ylim(-0.5, len(ordered_cats) - 0.5)

    # Domain labels on right side
    for i, (start, domain) in enumerate(domain_starts):
        if i < len(domain_starts) - 1:
            end = domain_starts[i + 1][0] - 1
        else:
            end = len(ordered_cats) - 1
        mid = (start + end) / 2
        ax.annotate(domain.replace(' & ', '\n& '),
                    xy=(1.02, mid), xycoords=('axes fraction', 'data'),
                    fontsize=FONT['domain_label'], fontweight='bold', va='center', ha='left',
                    color=DOMAIN_COLORS.get(domain, '#333333'))

    # Legend at bottom
    legend_elements = [Patch(facecolor=DOMAIN_COLORS[d], label=d, edgecolor='white')
                       for d in DOMAIN_GROUPS.keys()]
    ax.legend(handles=legend_elements, loc='upper center',
              bbox_to_anchor=(0.5, -0.08), ncol=5, fontsize=FONT['legend'], frameon=False)

    # Final formatting
    ax.invert_yaxis()
    ax.set_xlabel('Survey Year', fontsize=FONT['axis_label'], fontweight='bold')

    # Do not display the name of the figure
    # ax.set_title('SHEDS Survey: Variable Categories Available by Year',
    #            fontsize=14, fontweight='bold', pad=15)
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.subplots_adjust(right=0.82, bottom=0.12)

    # Save in different formats
    for fmt in formats:
        output_path = f'{output_base}.{fmt}'
        if fmt == 'png':
            plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        else:
            plt.savefig(output_path, bbox_inches='tight', facecolor='white')
        print(f"Saved: {output_path}")

    plt.close()


def main():
    """Generate timeline visualization with counts."""

    print(f"Loading data from {INPUT_FILE}...")
    df = load_and_process_data(INPUT_FILE)

    print(f"Total variables: {len(df)}")
    print(f"Categories found: {df['category'].nunique()}")
    print()

    # Generate visualization
    create_timeline_with_counts(df,
                                output_base='sheds_timeline_counts',
                                formats=['pdf', 'eps', 'png'])

    print("\nGenerated.. in the ")


if __name__ == '__main__':
    main()
