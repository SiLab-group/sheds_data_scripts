"""
Tests for build_accom_history in longitudinal_history_variables.py using synthetic data.

Fill rules:
  - 2018 & 2019: fill accom1_filled only when accom1 == -2 AND accom_change != 1
  - 2020:        fill accom1_filled only when accom1 is NaN   AND accom_change != 1
  - All others:  no fill at all
  - Valid values (> 0) are never overwritten
"""

import numpy as np
import pandas as pd
import pytest
from longitudinal_history_variables import build_accom_history


def make_waves(data_by_year: dict) -> dict:
    """Build a minimal all_waves_dict for accommodation history tests."""
    return {str(y): pd.DataFrame(d) for y, d in data_by_year.items()}


def get_row(result, respondent_id, year):
    return result[(result["id"] == respondent_id) & (result["year_wave"] == year)].iloc[0]


# ---------------------------------------------------------------------------
# 2018 / 2019 — fill when accom1 == -2
# ---------------------------------------------------------------------------

def test_2018_dna_filled():
    """-2 in 2018 with no move → filled from 2017."""
    waves = make_waves({
        2017: {"id": [1], "accom1": [1.0], "accom_change": [np.nan]},
        2018: {"id": [1], "accom1": [-2.0], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2018)
    assert row["accom1_filled"] == 1.0


def test_2019_dna_filled():
    """-2 in 2019 with no move → filled from 2018."""
    waves = make_waves({
        2018: {"id": [1], "accom1": [2.0], "accom_change": [np.nan]},
        2019: {"id": [1], "accom1": [-2.0], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2019)
    assert row["accom1_filled"] == 2.0


def test_2018_dna_no_fill_when_moved():
    """-2 in 2018 but accom_change == 1 → NOT filled (person moved, new value missing)."""
    waves = make_waves({
        2017: {"id": [1], "accom1": [1.0], "accom_change": [np.nan]},
        2018: {"id": [1], "accom1": [-2.0], "accom_change": [1.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2018)
    assert pd.isna(row["accom1_filled"])


def test_2019_dna_no_fill_when_moved():
    """-2 in 2019 but accom_change == 1 → NOT filled."""
    waves = make_waves({
        2018: {"id": [1], "accom1": [2.0], "accom_change": [np.nan]},
        2019: {"id": [1], "accom1": [-2.0], "accom_change": [1.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2019)
    assert pd.isna(row["accom1_filled"])


def test_2018_dnk_not_filled():
    """-1 (don't know) in 2018 → NOT filled (only -2 triggers fill)."""
    waves = make_waves({
        2017: {"id": [1], "accom1": [1.0], "accom_change": [np.nan]},
        2018: {"id": [1], "accom1": [-1.0], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2018)
    assert pd.isna(row["accom1_filled"])


def test_2019_dnk_not_filled():
    """-1 in 2019 → NOT filled."""
    waves = make_waves({
        2018: {"id": [1], "accom1": [2.0], "accom_change": [np.nan]},
        2019: {"id": [1], "accom1": [-1.0], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2019)
    assert pd.isna(row["accom1_filled"])


def test_2018_nan_not_filled():
    """True NaN in 2018 → NOT filled (only -2 triggers fill in 2018)."""
    waves = make_waves({
        2017: {"id": [1], "accom1": [1.0],    "accom_change": [np.nan]},
        2018: {"id": [1], "accom1": [np.nan], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2018)
    assert pd.isna(row["accom1_filled"])


def test_2019_nan_not_filled():
    """True NaN in 2019 → NOT filled."""
    waves = make_waves({
        2018: {"id": [1], "accom1": [1.0],    "accom_change": [np.nan]},
        2019: {"id": [1], "accom1": [np.nan], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2019)
    assert pd.isna(row["accom1_filled"])


def test_2018_dna_no_prior_value_stays_nan():
    """-2 in 2018 with no prior known value → stays NaN (nothing to carry forward)."""
    waves = make_waves({
        2018: {"id": [1], "accom1": [-2.0], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2018)
    assert pd.isna(row["accom1_filled"])


# ---------------------------------------------------------------------------
# 2020 — fill when accom1 is NaN
# ---------------------------------------------------------------------------

def test_2020_nan_filled():
    """NaN in 2020 with no move → filled from previous wave."""
    waves = make_waves({
        2019: {"id": [1], "accom1": [1.0],    "accom_change": [np.nan]},
        2020: {"id": [1], "accom1": [np.nan], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2020)
    assert row["accom1_filled"] == 1.0


def test_2020_nan_no_fill_when_moved():
    """NaN in 2020 but accom_change == 1 → NOT filled."""
    waves = make_waves({
        2019: {"id": [1], "accom1": [1.0],    "accom_change": [np.nan]},
        2020: {"id": [1], "accom1": [np.nan], "accom_change": [1.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2020)
    assert pd.isna(row["accom1_filled"])


def test_2020_dna_not_filled():
    """-2 in 2020 → NOT filled (-2 fill only applies in 2018/2019)."""
    waves = make_waves({
        2019: {"id": [1], "accom1": [1.0],  "accom_change": [np.nan]},
        2020: {"id": [1], "accom1": [-2.0], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2020)
    assert pd.isna(row["accom1_filled"])


def test_2020_nan_no_prior_value_stays_nan():
    """NaN in 2020 with no prior known value → stays NaN."""
    waves = make_waves({
        2020: {"id": [1], "accom1": [np.nan], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2020)
    assert pd.isna(row["accom1_filled"])


# ---------------------------------------------------------------------------
# Other years — no fill at all
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", [2016, 2017, 2021, 2023, 2025])
def test_other_years_dna_not_filled(year):
    """-2 in years other than 2018/2019 → NOT filled."""
    prev_year = year - 1
    waves = make_waves({
        prev_year: {"id": [1], "accom1": [1.0],  "accom_change": [np.nan]},
        year:      {"id": [1], "accom1": [-2.0], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, year)
    assert pd.isna(row["accom1_filled"])


@pytest.mark.parametrize("year", [2016, 2017, 2021, 2023, 2025])
def test_other_years_nan_not_filled(year):
    """NaN in years other than 2020 → NOT filled."""
    prev_year = year - 1
    waves = make_waves({
        prev_year: {"id": [1], "accom1": [1.0],    "accom_change": [np.nan]},
        year:      {"id": [1], "accom1": [np.nan], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, year)
    assert pd.isna(row["accom1_filled"])


# ---------------------------------------------------------------------------
# General integrity
# ---------------------------------------------------------------------------

def test_valid_value_never_overwritten():
    """A valid accom1 value (>0) should never be overwritten."""
    waves = make_waves({
        2017: {"id": [1], "accom1": [1.0], "accom_change": [np.nan]},
        2018: {"id": [1], "accom1": [2.0], "accom_change": [0.0]},
    })
    row = get_row(build_accom_history(waves), 1, 2018)
    assert row["accom1_filled"] == 2.0


def test_fill_independent_per_respondent():
    """Fill is applied per respondent; IDs must not bleed into each other."""
    waves = make_waves({
        2017: {"id": [1, 2], "accom1": [1.0, 2.0], "accom_change": [np.nan, np.nan]},
        2018: {"id": [1, 2], "accom1": [-2.0, -2.0], "accom_change": [0.0, 0.0]},
    })
    result = build_accom_history(waves)
    r2018 = result[result["year_wave"] == 2018].set_index("id")
    assert r2018.loc[1, "accom1_filled"] == 1.0
    assert r2018.loc[2, "accom1_filled"] == 2.0


def test_fill_carries_across_multiple_waves():
    """A value from 2017 should carry through consecutive -2 rows in 2018 and 2019."""
    waves = make_waves({
        2017: {"id": [1], "accom1": [1.0],  "accom_change": [np.nan]},
        2018: {"id": [1], "accom1": [-2.0], "accom_change": [0.0]},
        2019: {"id": [1], "accom1": [-2.0], "accom_change": [0.0]},
    })
    result = build_accom_history(waves)
    assert get_row(result, 1, 2018)["accom1_filled"] == 1.0
    assert get_row(result, 1, 2019)["accom1_filled"] == 1.0


# ---------------------------------------------------------------------------
# Multiple respondents — mixed conditions in the same wave
# ---------------------------------------------------------------------------

def test_multi_respondent_mixed_2018():
    """
    In 2018, four respondents with different conditions + bystanders in 2021/2023
    who should be completely unaffected.
      - id=1: -2 (DNA), no move  → filled
      - id=2: -2 (DNA), moved    → NOT filled
      - id=3: -1 (DNK), no move  → NOT filled
      - id=4: valid 2.0          → kept as-is
      - id=5: only in 2021 with -2 → NOT filled (wrong year)
      - id=6: only in 2023 with NaN → NOT filled (wrong year)
    """
    waves = make_waves({
        2017: {"id": [1, 2, 3, 4],       "accom1": [1.0, 1.0, 1.0, 1.0],          "accom_change": [np.nan]*4},
        2018: {"id": [1, 2, 3, 4],       "accom1": [-2.0, -2.0, -1.0, 2.0],       "accom_change": [0.0, 1.0, 0.0, 0.0]},
        2021: {"id": [1, 2, 3, 4, 5],    "accom1": [1.0, 1.0, 1.0, 2.0, -2.0],    "accom_change": [np.nan]*5},
        2023: {"id": [1, 2, 3, 4, 5, 6], "accom1": [1.0, 1.0, 1.0, 2.0, 1.0, np.nan], "accom_change": [np.nan]*6},
    })
    result = build_accom_history(waves)
    r2018 = result[result["year_wave"] == 2018].set_index("id")
    assert r2018.loc[1, "accom1_filled"] == 1.0   # DNA no move → filled
    assert pd.isna(r2018.loc[2, "accom1_filled"]) # DNA moved   → not filled
    assert pd.isna(r2018.loc[3, "accom1_filled"]) # DNK         → not filled
    assert r2018.loc[4, "accom1_filled"] == 2.0   # valid       → kept
    # bystanders in other years unaffected
    r2021 = result[result["year_wave"] == 2021].set_index("id")
    assert pd.isna(r2021.loc[5, "accom1_filled"]) # -2 in 2021 → not filled
    r2023 = result[result["year_wave"] == 2023].set_index("id")
    assert pd.isna(r2023.loc[6, "accom1_filled"]) # NaN in 2023 → not filled


def test_multi_respondent_mixed_2019():
    """
    In 2019, same four-respondent scenario + bystanders in 2021/2023.
    """
    waves = make_waves({
        2018: {"id": [1, 2, 3, 4],       "accom1": [2.0, 2.0, 2.0, 2.0],          "accom_change": [np.nan]*4},
        2019: {"id": [1, 2, 3, 4],       "accom1": [-2.0, -2.0, -1.0, 1.0],       "accom_change": [0.0, 1.0, 0.0, 0.0]},
        2021: {"id": [1, 2, 3, 4, 5],    "accom1": [2.0, 2.0, 2.0, 1.0, -2.0],    "accom_change": [np.nan]*5},
        2023: {"id": [1, 2, 3, 4, 5, 6], "accom1": [2.0, 2.0, 2.0, 1.0, 2.0, np.nan], "accom_change": [np.nan]*6},
    })
    result = build_accom_history(waves)
    r2019 = result[result["year_wave"] == 2019].set_index("id")
    assert r2019.loc[1, "accom1_filled"] == 2.0   # DNA no move → filled
    assert pd.isna(r2019.loc[2, "accom1_filled"]) # DNA moved   → not filled
    assert pd.isna(r2019.loc[3, "accom1_filled"]) # DNK         → not filled
    assert r2019.loc[4, "accom1_filled"] == 1.0   # valid       → kept
    # bystanders in other years unaffected
    r2021 = result[result["year_wave"] == 2021].set_index("id")
    assert pd.isna(r2021.loc[5, "accom1_filled"]) # -2 in 2021 → not filled
    r2023 = result[result["year_wave"] == 2023].set_index("id")
    assert pd.isna(r2023.loc[6, "accom1_filled"]) # NaN in 2023 → not filled


def test_multi_respondent_mixed_2020():
    """
    In 2020, three respondents with different conditions + bystanders in 2021/2023.
      - id=1: NaN, no move  → filled
      - id=2: NaN, moved    → NOT filled
      - id=3: -2, no move   → NOT filled (-2 fill only for 2018/2019)
      - id=4: only in 2021 with NaN → NOT filled (wrong year)
      - id=5: only in 2023 with -2  → NOT filled (wrong year)
    """
    waves = make_waves({
        2019: {"id": [1, 2, 3],       "accom1": [1.0, 1.0, 1.0],          "accom_change": [np.nan]*3},
        2020: {"id": [1, 2, 3],       "accom1": [np.nan, np.nan, -2.0],   "accom_change": [0.0, 1.0, 0.0]},
        2021: {"id": [1, 2, 3, 4],    "accom1": [1.0, 1.0, 1.0, np.nan], "accom_change": [np.nan]*4},
        2023: {"id": [1, 2, 3, 4, 5], "accom1": [1.0, 1.0, 1.0, 1.0, -2.0], "accom_change": [np.nan]*5},
    })
    result = build_accom_history(waves)
    r2020 = result[result["year_wave"] == 2020].set_index("id")
    assert r2020.loc[1, "accom1_filled"] == 1.0   # NaN no move → filled
    assert pd.isna(r2020.loc[2, "accom1_filled"]) # NaN moved   → not filled
    assert pd.isna(r2020.loc[3, "accom1_filled"]) # -2          → not filled in 2020
    # bystanders in other years unaffected
    r2021 = result[result["year_wave"] == 2021].set_index("id")
    assert pd.isna(r2021.loc[4, "accom1_filled"]) # NaN in 2021 → not filled
    r2023 = result[result["year_wave"] == 2023].set_index("id")
    assert pd.isna(r2023.loc[5, "accom1_filled"]) # -2 in 2023  → not filled


def test_multi_respondent_different_prior_values():
    """Each respondent carries their own prior; bystanders in 2021/2023 unaffected."""
    waves = make_waves({
        2017: {"id": [1, 2, 3],    "accom1": [1.0, 2.0, 3.0],       "accom_change": [np.nan]*3},
        2018: {"id": [1, 2, 3],    "accom1": [-2.0, -2.0, -2.0],    "accom_change": [0.0]*3},
        2019: {"id": [1, 2, 3],    "accom1": [-2.0, -2.0, -2.0],    "accom_change": [0.0]*3},
        2021: {"id": [1, 2, 3, 4], "accom1": [1.0, 2.0, 3.0, -2.0], "accom_change": [np.nan]*4},
        2023: {"id": [1, 2, 3, 4], "accom1": [1.0, 2.0, 3.0, np.nan], "accom_change": [np.nan]*4},
    })
    result = build_accom_history(waves)
    for yr in [2018, 2019]:
        r = result[result["year_wave"] == yr].set_index("id")
        assert r.loc[1, "accom1_filled"] == 1.0
        assert r.loc[2, "accom1_filled"] == 2.0
        assert r.loc[3, "accom1_filled"] == 3.0
    # bystander id=4 in 2021 and 2023 not filled
    r2021 = result[result["year_wave"] == 2021].set_index("id")
    assert pd.isna(r2021.loc[4, "accom1_filled"]) # -2 in 2021 → not filled
    r2023 = result[result["year_wave"] == 2023].set_index("id")
    assert pd.isna(r2023.loc[4, "accom1_filled"]) # NaN in 2023 → not filled


def test_multi_respondent_one_moves_mid_panel():
    """
    id=1 moves in 2018; id=2 does not. Bystanders in 2021/2023 unaffected.
    """
    waves = make_waves({
        2017: {"id": [1, 2],       "accom1": [1.0, 1.0],          "accom_change": [np.nan, np.nan]},
        2018: {"id": [1, 2],       "accom1": [2.0, -2.0],         "accom_change": [1.0, 0.0]},
        2019: {"id": [1, 2],       "accom1": [-2.0, -2.0],        "accom_change": [0.0, 0.0]},
        2021: {"id": [1, 2, 3],    "accom1": [2.0, 1.0, -2.0],   "accom_change": [np.nan]*3},
        2023: {"id": [1, 2, 3, 4], "accom1": [2.0, 1.0, 1.0, np.nan], "accom_change": [np.nan]*4},
    })
    result = build_accom_history(waves)
    assert get_row(result, 1, 2018)["accom1_filled"] == 2.0
    assert get_row(result, 1, 2019)["accom1_filled"] == 2.0
    assert get_row(result, 2, 2018)["accom1_filled"] == 1.0
    assert get_row(result, 2, 2019)["accom1_filled"] == 1.0
    # bystanders
    r2021 = result[result["year_wave"] == 2021].set_index("id")
    assert pd.isna(r2021.loc[3, "accom1_filled"]) # -2 in 2021 → not filled
    r2023 = result[result["year_wave"] == 2023].set_index("id")
    assert pd.isna(r2023.loc[4, "accom1_filled"]) # NaN in 2023 → not filled


def test_multi_respondent_new_entrant_no_prior():
    """
    id=1 is a returning respondent; id=2 is a new entrant in 2018.
    Bystanders in 2021/2023 are unaffected.
    """
    waves = make_waves({
        2017: {"id": [1],          "accom1": [1.0],              "accom_change": [np.nan]},
        2018: {"id": [1, 2],       "accom1": [-2.0, -2.0],       "accom_change": [0.0, 0.0]},
        2021: {"id": [1, 2, 3],    "accom1": [1.0, 1.0, -2.0],  "accom_change": [np.nan]*3},
        2023: {"id": [1, 2, 3, 4], "accom1": [1.0, 1.0, 1.0, np.nan], "accom_change": [np.nan]*4},
    })
    result = build_accom_history(waves)
    r2018 = result[result["year_wave"] == 2018].set_index("id")
    assert r2018.loc[1, "accom1_filled"] == 1.0   # returning → filled
    assert pd.isna(r2018.loc[2, "accom1_filled"]) # new entrant → stays NaN
    # bystanders
    r2021 = result[result["year_wave"] == 2021].set_index("id")
    assert pd.isna(r2021.loc[3, "accom1_filled"]) # -2 in 2021 → not filled
    r2023 = result[result["year_wave"] == 2023].set_index("id")
    assert pd.isna(r2023.loc[4, "accom1_filled"]) # NaN in 2023 → not filled
