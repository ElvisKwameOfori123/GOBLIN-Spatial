from pathlib import Path

from goblin_spatial.cattle.cohorts import FINAL_21_COHORTS
from goblin_spatial.scenario.national_cohort_targets import (
    derive_national_cohort_targets,
    load_goblin_cohort_reference,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data/controls/cohort2012-2020.csv"


def test_reference_loads_complete_2020_cattle_profile():
    reference = load_goblin_cohort_reference(REFERENCE, reference_year=2020)
    assert set(reference) == set(FINAL_21_COHORTS)
    assert reference["dairy_cows"] == 1511.85
    assert reference["suckler_cows"] == 953.0


def test_adult_endpoints_generate_complete_exact_21_cohort_target():
    reference = load_goblin_cohort_reference(REFERENCE, reference_year=2020)
    targets = derive_national_cohort_targets(
        dairy_cows=1_600_000,
        suckler_cows=160_000,
        reference_counts=reference,
    )
    assert set(targets) == set(FINAL_21_COHORTS)
    assert targets["dairy_cows"] == 1_600_000
    assert targets["suckler_cows"] == 160_000
    assert sum(targets.values()) > 1_760_000


def test_exact_total_cattle_override_reconciles_followers_only():
    reference = load_goblin_cohort_reference(REFERENCE, reference_year=2020)
    targets = derive_national_cohort_targets(
        dairy_cows=1_600_000,
        suckler_cows=160_000,
        reference_counts=reference,
        total_cattle_target=4_900_000,
    )
    assert targets["dairy_cows"] == 1_600_000
    assert targets["suckler_cows"] == 160_000
    assert sum(targets.values()) == 4_900_000
