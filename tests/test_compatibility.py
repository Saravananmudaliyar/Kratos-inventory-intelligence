"""Tests for compatibility module."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.inventory import load_scenario
from engine.compatibility import (
    find_compatible_skus,
    validate_substitute,
    evaluate_all_substitutes,
)


def test_incompatible_rejected():
    """Incompatible substitute (wattage/voltage mismatch) must be rejected."""
    scenario = load_scenario()
    result = validate_substitute(scenario, "SKU-CHARGER-65W", "SKU-CHARGER-18W", 10)
    assert not result["eligible"]
    assert any("rejected" in r.lower() or "wattage" in r.lower() or "incompatible" in r.lower() for r in result["rejection_reasons"])
    print("  PASS: Incompatible substitute SKU-CHARGER-18W rejected (voltage/wattage mismatch)")


def test_compatible_approved():
    """Compatible substitute (Charger 65W Pro) should be approved."""
    scenario = load_scenario()
    result = validate_substitute(scenario, "SKU-CHARGER-65W", "SKU-CHARGER-65W-PRO", 10)
    assert result["eligible"]
    assert any(c["status"] == "APPROVED" for c in result["checks"])
    print("  PASS: Compatible substitute SKU-CHARGER-65W-PRO approved")


def test_no_compatibility_rule():
    """SKU with no compatibility rule should require verification."""
    scenario = load_scenario()
    result = validate_substitute(scenario, "SKU-MOUSE-WL", "SKU-CABLE-USBC", 10)
    assert not result["eligible"]
    assert any("verification" in r.lower() or "no compatibility" in r.lower() for r in result["rejection_reasons"])
    print("  PASS: Missing compatibility rule requires verification")


def test_evaluate_all_chargers():
    """Evaluate all substitutes for 65W USB-C Charger."""
    scenario = load_scenario()
    result = evaluate_all_substitutes(scenario, "SKU-CHARGER-65W", 10)
    assert result["has_eligible"]  # 65W Pro should be eligible
    assert len(result["rejected_alternatives"]) >= 1  # 18W rejected
    
    # Check 65W Pro is in eligible list
    eligible_ids = [s["substitute_sku_id"] for s in result["eligible_substitutes"]]
    assert "SKU-CHARGER-65W-PRO" in eligible_ids
    
    # Check 18W is in rejected list
    rejected_ids = [s["substitute_sku_id"] for s in result["rejected_alternatives"]]
    assert "SKU-CHARGER-18W" in rejected_ids
    
    print("  PASS: 65W-PRO eligible, 18W rejected for 65W Charger substitution")


def test_substitute_ranking():
    """Eligible substitutes should be ranked by cost then availability."""
    scenario = load_scenario()
    result = evaluate_all_substitutes(scenario, "SKU-CHARGER-65W", 5)
    eligible = result["eligible_substitutes"]
    if len(eligible) > 1:
        for i in range(len(eligible) - 1):
            assert eligible[i]["unit_cost"] <= eligible[i+1]["unit_cost"]
    print("  PASS: Substitutes ranked correctly")


def test_insufficient_inventory_rejected():
    """Substitute with insufficient inventory should be rejected."""
    scenario = load_scenario()
    # Request huge amount that no warehouse has
    result = validate_substitute(scenario, "SKU-CHARGER-65W", "SKU-CHARGER-65W-PRO", 99999)
    assert not result["eligible"]
    assert any("insufficient" in r.lower() for r in result["rejection_reasons"])
    print("  PASS: Insufficient substitute inventory correctly rejected")


def test_reserved_excluded_from_substitute_availability():
    """Reserved stock of substitute must not be counted as available."""
    scenario = load_scenario()
    result = validate_substitute(scenario, "SKU-CHARGER-65W", "SKU-CHARGER-65W-PRO", 10)
    for loc in result["available_locations"]:
        assert loc["available"] == loc["on_hand"] - loc["reserved"]
    print("  PASS: Reserved inventory excluded from substitute availability")


if __name__ == "__main__":
    print("=" * 60)
    print("COMPATIBILITY MODULE TESTS")
    print("=" * 60)
    test_incompatible_rejected()
    test_compatible_approved()
    test_no_compatibility_rule()
    test_evaluate_all_chargers()
    test_substitute_ranking()
    test_insufficient_inventory_rejected()
    test_reserved_excluded_from_substitute_availability()
    print("\nAll compatibility tests PASSED [OK]")
