"""
Tests for utils.py using synthetic data.
"""

import numpy as np
import pandas as pd
import pytest
from utils import conditional_ffill, build_car_history, get_data_summary, check_finished


# ---------------------------------------------------------------------------
# conditional_ffill
# ---------------------------------------------------------------------------

def make_group(accom1_filled, change):
    """Helper: build a minimal single-person group DataFrame."""
    return pd.DataFrame({
        "accom1_filled": accom1_filled,
        "accom_change":  change,
    })


def test_conditional_ffill_basic_carries_forward():
    """When change == 0, NaN should be filled from previous valid value."""
    g = make_group([1.0, np.nan], [np.nan, 0.0])
    result = conditional_ffill(g, "accom1_filled", "accom_change")
    assert result.iloc[1] == 1.0


def test_conditional_ffill_no_fill_when_change_1():
    """When change == 1, NaN must stay NaN (person moved)."""
    g = make_group([1.0, np.nan], [np.nan, 1.0])
    result = conditional_ffill(g, "accom1_filled", "accom_change")
    assert pd.isna(result.iloc[1])


def test_conditional_ffill_new_respondent_nan_change():
    """NaN change (new respondent) should trigger carry-forward."""
    g = make_group([2.0, np.nan], [np.nan, np.nan])
    result = conditional_ffill(g, "accom1_filled", "accom_change")
    assert result.iloc[1] == 2.0


def test_conditional_ffill_fill_when_restricts():
    """fill_when=False should block filling even when change != 1."""
    g = make_group([1.0, np.nan, np.nan], [np.nan, 0.0, 0.0])
    fill_when = pd.Series([False, True, False], index=g.index)
    result = conditional_ffill(g, "accom1_filled", "accom_change", fill_when=fill_when)
    assert result.iloc[1] == 1.0   # fill_when True  → filled
    assert pd.isna(result.iloc[2]) # fill_when False → not filled


def test_conditional_ffill_no_previous_value():
    """With no prior valid value, carry-forward should leave NaN."""
    g = make_group([np.nan, np.nan], [np.nan, 0.0])
    result = conditional_ffill(g, "accom1_filled", "accom_change")
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])


def test_conditional_ffill_updates_last_known():
    """last_known should update as new valid values appear."""
    g = make_group([1.0, 2.0, np.nan], [np.nan, 0.0, 0.0])
    result = conditional_ffill(g, "accom1_filled", "accom_change")
    assert result.iloc[2] == 2.0


# ---------------------------------------------------------------------------
# build_car_history
# ---------------------------------------------------------------------------

def make_waves_car(data_by_year: dict) -> dict:
    """Build a minimal all_waves_dict for car history tests."""
    return {str(y): pd.DataFrame(d) for y, d in data_by_year.items()}


def test_build_car_history_carry_forward():
    """mob3_3_filled carries forward when mob3_change != 1."""
    waves = make_waves_car({
        2019: {"id": [1], "mob2_1": [1.0], "mob3_3": [1.0], "mob3_change": [np.nan], "old": [0.0]},
        2020: {"id": [1], "mob2_1": [1.0], "mob3_3": [-2.0], "mob3_change": [0.0],   "old": [1.0]},
    })
    result = build_car_history(waves)
    row_2020 = result[result["year_wave"] == 2020].iloc[0]
    assert row_2020["mob3_3_filled"] == 1.0


def test_build_car_history_no_fill_on_change():
    """mob3_3_filled must be NaN when mob3_change == 1 and new value is invalid."""
    waves = make_waves_car({
        2019: {"id": [1], "mob2_1": [1.0], "mob3_3": [1.0], "mob3_change": [np.nan], "old": [0.0]},
        2020: {"id": [1], "mob2_1": [1.0], "mob3_3": [-2.0], "mob3_change": [1.0],   "old": [1.0]},
    })
    result = build_car_history(waves)
    row_2020 = result[result["year_wave"] == 2020].iloc[0]
    assert pd.isna(row_2020["mob3_3_filled"])


def test_build_car_history_string_fuel_type_mapped():
    """String fuel type labels should be mapped to numeric codes."""
    waves = make_waves_car({
        2019: {"id": [1], "mob2_1": [1.0], "mob3_3": ["Electric"], "mob3_change": [np.nan], "old": [0.0]},
    })
    result = build_car_history(waves)
    assert result.iloc[0]["mob3_3_filled"] == 8.0


def test_build_car_history_multiple_respondents():
    """Carry-forward is applied per respondent, not across IDs."""
    waves = make_waves_car({
        2019: {"id": [1, 2], "mob2_1": [1.0, 1.0], "mob3_3": [1.0, 2.0], "mob3_change": [np.nan, np.nan], "old": [0.0, 0.0]},
        2020: {"id": [1, 2], "mob2_1": [1.0, 1.0], "mob3_3": [-2.0, -2.0], "mob3_change": [0.0, 0.0],    "old": [1.0, 1.0]},
    })
    result = build_car_history(waves)
    r2020 = result[result["year_wave"] == 2020].set_index("id")
    assert r2020.loc[1, "mob3_3_filled"] == 1.0
    assert r2020.loc[2, "mob3_3_filled"] == 2.0


def test_build_car_history_mixed_conditions():
    """
    Four respondents in the same wave with different conditions:
      - id=1: no change (mob3_change=0), invalid code → filled from prior
      - id=2: changed car (mob3_change=1), invalid code → NOT filled
      - id=3: no change, valid new value → kept as-is
      - id=4: new entrant (no prior), invalid code → stays NaN
    """
    waves = make_waves_car({
        2019: {"id": [1, 2, 3],    "mob2_1": [1.0]*3, "mob3_3": [1.0, 2.0, 3.0], "mob3_change": [np.nan]*3, "old": [0.0]*3},
        2020: {"id": [1, 2, 3, 4], "mob2_1": [1.0]*4, "mob3_3": [-2.0, -2.0, 8.0, -2.0],
               "mob3_change": [0.0, 1.0, 0.0, 0.0], "old": [1.0, 1.0, 1.0, 0.0]},
    })
    result = build_car_history(waves)
    r2020 = result[result["year_wave"] == 2020].set_index("id")
    assert r2020.loc[1, "mob3_3_filled"] == 1.0   # no change → filled from 2019
    assert pd.isna(r2020.loc[2, "mob3_3_filled"]) # changed   → not filled
    assert r2020.loc[3, "mob3_3_filled"] == 8.0   # valid EV  → kept
    assert pd.isna(r2020.loc[4, "mob3_3_filled"]) # new entrant, no prior → NaN


def test_build_car_history_different_prior_fuel_types():
    """Each respondent carries their own fuel type, not a neighbour's."""
    waves = make_waves_car({
        2019: {"id": [1, 2, 3, 4], "mob2_1": [1.0]*4,
               "mob3_3": [1.0, 2.0, 5.0, 8.0], "mob3_change": [np.nan]*4, "old": [0.0]*4},
        2020: {"id": [1, 2, 3, 4], "mob2_1": [1.0]*4,
               "mob3_3": [-2.0]*4, "mob3_change": [0.0]*4, "old": [1.0]*4},
        2021: {"id": [1, 2, 3, 4], "mob2_1": [1.0]*4,
               "mob3_3": [-2.0]*4, "mob3_change": [0.0]*4, "old": [1.0]*4},
    })
    result = build_car_history(waves)
    for yr in [2020, 2021]:
        r = result[result["year_wave"] == yr].set_index("id")
        assert r.loc[1, "mob3_3_filled"] == 1.0  # Gasoline
        assert r.loc[2, "mob3_3_filled"] == 2.0  # Diesel
        assert r.loc[3, "mob3_3_filled"] == 5.0  # Hybrid gas
        assert r.loc[4, "mob3_3_filled"] == 8.0  # Electric


def test_build_car_history_one_switches_to_ev():
    """
    id=1 switches to EV in 2020 (mob3_change=1, new valid value=8).
    id=2 keeps same car (no change, carry forward).
    Both then have no change in 2021 → id=1 carries 8, id=2 carries original.
    """
    waves = make_waves_car({
        2019: {"id": [1, 2], "mob2_1": [1.0, 1.0], "mob3_3": [1.0, 2.0], "mob3_change": [np.nan, np.nan], "old": [0.0, 0.0]},
        2020: {"id": [1, 2], "mob2_1": [1.0, 1.0], "mob3_3": [8.0, -2.0], "mob3_change": [1.0, 0.0],    "old": [1.0, 1.0]},
        2021: {"id": [1, 2], "mob2_1": [1.0, 1.0], "mob3_3": [-2.0, -2.0], "mob3_change": [0.0, 0.0],  "old": [1.0, 1.0]},
    })
    result = build_car_history(waves)
    r2020 = result[result["year_wave"] == 2020].set_index("id")
    assert r2020.loc[1, "mob3_3_filled"] == 8.0  # switched to EV
    assert r2020.loc[2, "mob3_3_filled"] == 2.0  # no change, carried
    r2021 = result[result["year_wave"] == 2021].set_index("id")
    assert r2021.loc[1, "mob3_3_filled"] == 8.0  # EV carried forward
    assert r2021.loc[2, "mob3_3_filled"] == 2.0  # Diesel carried forward


def test_build_car_history_string_labels_mixed_with_numeric():
    """String labels and numeric codes in different waves map to the same filled values."""
    waves = make_waves_car({
        2019: {"id": [1, 2], "mob2_1": [1.0, 1.0], "mob3_3": ["Electric", "Diesel"],
               "mob3_change": [np.nan, np.nan], "old": [0.0, 0.0]},
        2020: {"id": [1, 2], "mob2_1": [1.0, 1.0], "mob3_3": [-2.0, -2.0],
               "mob3_change": [0.0, 0.0], "old": [1.0, 1.0]},
    })
    result = build_car_history(waves)
    r2020 = result[result["year_wave"] == 2020].set_index("id")
    assert r2020.loc[1, "mob3_3_filled"] == 8.0  # Electric → 8
    assert r2020.loc[2, "mob3_3_filled"] == 2.0  # Diesel   → 2


# ---------------------------------------------------------------------------
# get_data_summary
# ---------------------------------------------------------------------------

def test_get_data_summary_counts():
    df = pd.DataFrame({
        "q_totalduration": [5, 10, 120, 30],  # 120 is out of range
        "finished":        [1,  1,   1,  0],
    })
    summary = get_data_summary(df)
    assert summary["n_respondents"] == 3          # only duration 1-60
    assert summary["completion_rate"] == pytest.approx(200 / 3, rel=1e-3)


def test_get_data_summary_no_finished_col():
    df = pd.DataFrame({"q_totalduration": [5, 10, 30]})
    summary = get_data_summary(df)
    assert summary["completion_rate"] is None


# ---------------------------------------------------------------------------
# check_finished
# ---------------------------------------------------------------------------

def test_check_finished_returns_dataframe(capsys):
    df = pd.DataFrame({"finished": [1, 1, 0, 1]})
    result = check_finished(df, 2020)
    assert result is not None
    assert result["finished"].iloc[0] == 3
    assert result["total"].iloc[0] == 4


def test_check_finished_missing_column(capsys):
    df = pd.DataFrame({"other_col": [1, 2, 3]})
    result = check_finished(df, 2020)
    assert result is None
