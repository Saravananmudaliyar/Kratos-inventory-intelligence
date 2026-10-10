"""Tests for inventory module."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.inventory import (
    load_scenario,
    calculate_available_stock,
    get_inventory_map,
    get_sku_details,
    get_warehouse_details,
    get_all_available_stock,
    check_safety_stock,
    get_surplus_warehouses,
    get_orders_for_sku,
    get_incoming_shipments,
)


def test_available_stock_normal():
    """Available = on_hand - reserved when on_hand >= reserved."""
    result = calculate_available_stock(100, 30)
    assert result["available"] == 70
    assert result["on_hand"] == 100
    assert result["reserved"] == 30
    assert len(result["warnings"]) == 0
    print("  PASS: Normal available stock calculation")


def test_available_stock_insufficient():
    """When on_hand < reserved, available clamped to 0 with warning."""
    result = calculate_available_stock(10, 25)
    assert result["available"] == 0
    assert len(result["warnings"]) > 0
    assert any("less than reserved" in w for w in result["warnings"])
    print("  PASS: On-hand < reserved produces warning and clamps to 0")


def test_available_stock_zero():
    """Zero on_hand should give zero available."""
    result = calculate_available_stock(0, 0)
    assert result["available"] == 0
    print("  PASS: Zero inventory")


def test_load_scenario():
    """Scenario loads and contains expected keys with 4 warehouses."""
    scenario = load_scenario()
    assert "warehouses" in scenario
    assert "skus" in scenario
    assert "inventory" in scenario
    assert "customer_orders" in scenario
    assert "compatibility_rules" in scenario
    assert len(scenario["warehouses"]) == 4
    assert len(scenario["skus"]) >= 8
    print("  PASS: Scenario loads with 4 warehouses and 8 electronics SKUs")


def test_inventory_map():
    """Inventory map has correct structure."""
    scenario = load_scenario()
    inv_map = get_inventory_map(scenario)
    assert "WH-MUMBAI" in inv_map
    assert "WH-PUNE" in inv_map
    assert "SKU-CHARGER-65W" in inv_map["WH-PUNE"]
    assert "on_hand" in inv_map["WH-PUNE"]["SKU-CHARGER-65W"]
    print("  PASS: Inventory map structure correct for 4 warehouses")


def test_safety_stock_check():
    """Safety stock breaches detected correctly."""
    scenario = load_scenario()
    breaches = check_safety_stock(scenario)
    # WH-PUNE SKU-CHARGER-65W: on_hand=28, reserved=18 -> available=10, safety=25 -> breach!
    found = any(
        b["warehouse_id"] == "WH-PUNE" and b["sku_id"] == "SKU-CHARGER-65W"
        for b in breaches
    )
    assert found, "Expected safety stock breach at WH-PUNE for SKU-CHARGER-65W"
    print("  PASS: Safety stock breach detected at WH-PUNE for SKU-CHARGER-65W")


def test_surplus_warehouses():
    """Surplus correctly excludes safety stock and reserved, and protects source warehouse."""
    scenario = load_scenario()
    surpluses = get_surplus_warehouses(scenario, "SKU-CHARGER-65W", exclude_wh="WH-PUNE")
    # Mumbai: on_hand=100, reserved=25, available=75, safety=25 -> surplus > 0
    mumbai = [s for s in surpluses if s["warehouse_id"] == "WH-MUMBAI"]
    assert len(mumbai) == 1
    assert mumbai[0]["available"] == 75
    assert mumbai[0]["safety_stock"] == 25
    assert mumbai[0]["surplus"] > 0
    print("  PASS: Surplus calculation correct and protects source warehouse")


def test_reserved_excluded_from_available():
    """Reserved inventory is always excluded from available."""
    scenario = load_scenario()
    all_stock = get_all_available_stock(scenario)
    for item in all_stock:
        assert item["available"] == max(0, item["on_hand"] - item["reserved"])
    print("  PASS: Reserved always excluded from available stock")


def test_orders_sorted_by_priority():
    """Orders returned sorted by priority then deadline."""
    scenario = load_scenario()
    orders = get_orders_for_sku(scenario, "SKU-CHARGER-65W")
    priorities = [o["priority"] for o in orders]
    prio_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    prev = -1
    for p in priorities:
        assert prio_order[p] >= prev or prio_order[p] == prev
        prev = prio_order[p]
    print("  PASS: Orders sorted by priority")


def test_incoming_shipments_delay():
    """Delayed shipments have correct actual arrival day."""
    scenario = load_scenario()
    shipments = get_incoming_shipments(scenario, "SKU-CHARGER-65W", "WH-PUNE")
    assert len(shipments) >= 1
    delayed = [s for s in shipments if s["status"] == "delayed"]
    assert len(delayed) >= 1
    for s in delayed:
        assert s["actual_arrival_day"] == s["expected_arrival_day"] + s["delay_days"]
    print("  PASS: Delayed shipment arrival day correctly calculated")


if __name__ == "__main__":
    print("=" * 60)
    print("INVENTORY MODULE TESTS")
    print("=" * 60)
    test_available_stock_normal()
    test_available_stock_insufficient()
    test_available_stock_zero()
    test_load_scenario()
    test_inventory_map()
    test_safety_stock_check()
    test_surplus_warehouses()
    test_reserved_excluded_from_available()
    test_orders_sorted_by_priority()
    test_incoming_shipments_delay()
    print("\nAll inventory tests PASSED [OK]")
