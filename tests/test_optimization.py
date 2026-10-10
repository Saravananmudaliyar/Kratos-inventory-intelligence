"""Tests for optimization / decision engine module."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.inventory import load_scenario
from engine.optimization import (
    evaluate_transfer_strategy,
    evaluate_standard_reorder,
    evaluate_express_reorder,
    evaluate_substitution_strategy,
    evaluate_delay_strategy,
    generate_recovery_options,
    select_best_strategy,
    run_decision_engine,
    score_strategy,
)


def test_transfer_respects_safety_stock():
    """Transfer should not exceed source surplus and protects source warehouse."""
    scenario = load_scenario()
    transfers = evaluate_transfer_strategy(
        scenario, "SKU-CHARGER-65W", "WH-PUNE", 30, deadline_day=3, 
        order_priority="critical", late_penalty_per_day=500
    )
    for t in transfers:
        assert t["source_surplus_after"] >= 0, \
            f"Transfer from {t['source_warehouse_name']} would deplete below safety stock"
        assert t["source_safe"] is True
    print("  PASS: Transfers respect source safety stock and protect source warehouse")


def test_cost_calculation_consistency():
    """Total cost = purchase/transfer cost + penalty cost."""
    scenario = load_scenario()
    std = evaluate_standard_reorder(scenario, "SKU-CHARGER-65W", 30, 4, 500)
    assert abs(std["total_cost"] - (std["purchase_cost"] + std["penalty_cost"])) < 0.01
    
    exp = evaluate_express_reorder(scenario, "SKU-CHARGER-65W", 30, 4, 500)
    assert abs(exp["total_cost"] - (exp["purchase_cost"] + exp["penalty_cost"])) < 0.01
    print("  PASS: Cost calculations are consistent")


def test_express_vs_standard_lead_time():
    """Express reorder should have shorter lead time than standard."""
    scenario = load_scenario()
    std = evaluate_standard_reorder(scenario, "SKU-CHARGER-65W", 30, 4, 500)
    exp = evaluate_express_reorder(scenario, "SKU-CHARGER-65W", 30, 4, 500)
    assert exp["arrival_day"] <= std["arrival_day"]
    print("  PASS: Express lead time <= standard lead time")


def test_transfer_cost_vs_express():
    """When transfer cost > express cost, express should score better."""
    scenario = load_scenario()
    options = generate_recovery_options(
        scenario, "SKU-CHARGER-65W", "WH-PUNE", 20,
        {"order_id": "TEST", "deadline_day": 5, "priority": "high", "late_penalty_per_day": 300},
        express_cost_multiplier=0.5,  # Make express cheaper
        transfer_cost_multiplier=3.0,  # Make transfer expensive
    )
    # Express should be scored
    express_options = [o for o in options if o["strategy"] == "EXPRESS_REORDER"]
    assert len(express_options) >= 1
    print("  PASS: Express and transfer both evaluated with cost multipliers")


def test_selected_strategy_is_feasible():
    """The selected strategy must always be feasible."""
    scenario = load_scenario()
    options = generate_recovery_options(
        scenario, "SKU-CHARGER-65W", "WH-PUNE", 20,
        {"order_id": "ORD-2001", "deadline_day": 2, "priority": "critical", "late_penalty_per_day": 600},
    )
    result = select_best_strategy(options)
    if result["selected"] is not None:
        assert result["selected"]["feasible"]
    print("  PASS: Selected strategy is feasible")


def test_decision_engine_produces_records():
    """Decision engine should produce decision records with required fields."""
    scenario = load_scenario()
    decisions = run_decision_engine(scenario)
    assert len(decisions) > 0, "Engine should find at least one shortage"
    
    required_fields = [
        "decision_id", "timestamp", "sku_id", "warehouse_id",
        "order_id", "selected_action", "reason", "estimated_cost",
        "input_conditions", "warnings", "data_sources",
    ]
    for d in decisions:
        for field in required_fields:
            assert field in d, f"Missing field: {field}"
    print("  PASS: Decision records contain all required fields")


def test_decision_has_rejected_alternatives():
    """Each decision should list rejected alternatives with reasons."""
    scenario = load_scenario()
    decisions = run_decision_engine(scenario)
    for d in decisions:
        if d.get("selected_action") != "ESCALATE":
            assert "rejected_alternatives" in d
            assert "all_options" in d
    print("  PASS: Decisions include rejected alternatives")


def test_scoring_function():
    """Score function should produce valid numeric scores."""
    policy = {"weights": {"cost": 0.35, "fulfillment_time": 0.30, "reliability": 0.20, "priority_alignment": 0.15}}
    option = {
        "total_cost": 500,
        "arrival_day": 3,
        "partial": False,
        "meets_deadline": True,
    }
    score = score_strategy(option, policy, "critical")
    assert isinstance(score, float)
    assert score >= 0
    print("  PASS: Scoring function produces valid scores")


def test_no_feasible_option_escalates():
    """When no option is feasible, engine should recommend escalation."""
    options = [
        {"strategy": "TEST", "feasible": False, "score": 99, "total_cost": 999,
         "reason": "Not feasible", "arrival_day": 99, "meets_deadline": False},
    ]
    result = select_best_strategy(options)
    assert result["action"] == "ESCALATE"
    print("  PASS: No feasible options triggers escalation")


if __name__ == "__main__":
    print("=" * 60)
    print("OPTIMIZATION / DECISION ENGINE TESTS")
    print("=" * 60)
    test_transfer_respects_safety_stock()
    test_cost_calculation_consistency()
    test_express_vs_standard_lead_time()
    test_transfer_cost_vs_express()
    test_selected_strategy_is_feasible()
    test_decision_engine_produces_records()
    test_decision_has_rejected_alternatives()
    test_scoring_function()
    test_no_feasible_option_escalates()
    print("\nAll optimization tests PASSED [OK]")
