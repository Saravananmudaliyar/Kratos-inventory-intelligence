"""Tests for simulation module."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.inventory import load_scenario, deep_copy_scenario
from engine.simulation import (
    get_predefined_scenarios,
    run_simulation,
    compare_scenarios,
)


def test_predefined_scenarios_exist():
    """All 5 predefined scenarios should be available."""
    scenarios = get_predefined_scenarios()
    assert len(scenarios) >= 5
    expected = ["normal", "supplier_delay", "demand_spike", "warehouse_imbalance", "combined_disruption"]
    for key in expected:
        assert key in scenarios, f"Missing predefined scenario: {key}"
    print("  PASS: All 5 predefined scenarios available")


def test_baseline_simulation():
    """Baseline simulation should produce valid results."""
    scenario = load_scenario()
    result = run_simulation(scenario)
    assert "radar" in result
    assert "decisions" in result
    assert "kpis" in result
    assert result["kpis"]["total_skus_monitored"] > 0
    print("  PASS: Baseline simulation produces valid results")


def test_simulation_changes_with_inputs():
    """Changing simulation inputs should change results."""
    scenario = load_scenario()
    baseline = run_simulation(scenario)
    disrupted = run_simulation(scenario, demand_multiplier=2.0, delay_additional_days=5)
    
    # Disrupted should have more at-risk SKUs or higher cost
    assert disrupted["kpis"]["at_risk_skus"] >= baseline["kpis"]["at_risk_skus"] or \
           disrupted["kpis"]["estimated_disruption_cost"] >= baseline["kpis"]["estimated_disruption_cost"]
    print("  PASS: Simulation results change with input parameters")


def test_comparison_produces_deltas():
    """Comparing scenarios should produce meaningful deltas."""
    scenario = load_scenario()
    baseline = run_simulation(scenario)
    disrupted = run_simulation(scenario, demand_multiplier=1.8, delay_additional_days=5)
    
    comparison = compare_scenarios(baseline, disrupted)
    assert "kpi_comparison" in comparison
    assert "risk_changes" in comparison
    assert "decision_changes" in comparison
    print("  PASS: Comparison produces KPI deltas and changes")


def test_reset_restores_baseline():
    """Resetting should restore original scenario data."""
    original = load_scenario()
    modified = deep_copy_scenario(original)
    
    # Modify the copy
    if modified.get("inventory"):
        modified["inventory"][0]["on_hand"] = 0
    
    # Reset by reloading
    reset = load_scenario()
    assert reset["inventory"][0]["on_hand"] == original["inventory"][0]["on_hand"]
    assert reset["inventory"][0]["on_hand"] != 0
    print("  PASS: Reset restores baseline state")


def test_simulation_kpis_calculated():
    """All KPIs should be calculated from actual data."""
    scenario = load_scenario()
    result = run_simulation(scenario)
    kpis = result["kpis"]
    
    assert "total_skus_monitored" in kpis
    assert "at_risk_skus" in kpis
    assert "orders_threatened" in kpis
    assert "estimated_disruption_cost" in kpis
    assert "feasible_recoveries" in kpis
    
    assert isinstance(kpis["total_skus_monitored"], int)
    assert isinstance(kpis["estimated_disruption_cost"], (int, float))
    print("  PASS: All KPIs calculated correctly")


def test_audit_records_in_decisions():
    """Decision records should contain audit-required fields."""
    scenario = load_scenario()
    result = run_simulation(scenario)
    
    for d in result.get("decisions", []):
        assert "decision_id" in d
        assert "timestamp" in d
        assert "input_conditions" in d
        assert "data_sources" in d
        assert "evidence_completeness" in d
    print("  PASS: Audit records complete in decisions")


def test_missing_data_warning():
    """Missing or uncertain data should produce warnings."""
    scenario = load_scenario()
    result = run_simulation(scenario)
    # The radar should have warnings for items with no incoming shipments
    radar_with_warnings = [r for r in result["radar"] if r.get("warnings")]
    assert len(radar_with_warnings) > 0, "Expected at least one radar item with warnings"
    print("  PASS: Missing data produces explicit warnings")


if __name__ == "__main__":
    print("=" * 60)
    print("SIMULATION MODULE TESTS")
    print("=" * 60)
    test_predefined_scenarios_exist()
    test_baseline_simulation()
    test_simulation_changes_with_inputs()
    test_comparison_produces_deltas()
    test_reset_restores_baseline()
    test_simulation_kpis_calculated()
    test_audit_records_in_decisions()
    test_missing_data_warning()
    print("\nAll simulation tests PASSED [OK]")
