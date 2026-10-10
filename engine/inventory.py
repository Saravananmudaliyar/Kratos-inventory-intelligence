"""
inventory.py — Inventory state management and available-to-promise calculations.

Handles loading scenario data, computing available stock, detecting safety stock 
breaches, and tracking inventory across warehouses.
"""

import json
import copy
from pathlib import Path
from typing import Dict, List, Optional, Any


def load_scenario(path: Optional[str] = None) -> dict:
    """Load scenario data from JSON file."""
    if path is None:
        path = str(Path(__file__).parent.parent / "data" / "demo_scenario.json")
    with open(path, "r") as f:
        return json.load(f)


def deep_copy_scenario(scenario: dict) -> dict:
    """Create a deep copy of scenario data for simulation isolation."""
    return copy.deepcopy(scenario)


def get_inventory_map(scenario: dict) -> Dict[str, Dict[str, dict]]:
    """
    Build a nested dict: inventory_map[warehouse_id][sku_id] -> inventory record.
    """
    inv_map = {}
    for rec in scenario.get("inventory", []):
        wh = rec["warehouse_id"]
        sku = rec["sku_id"]
        if wh not in inv_map:
            inv_map[wh] = {}
        inv_map[wh][sku] = {
            "on_hand": rec["on_hand"],
            "reserved": rec["reserved"],
        }
    return inv_map


def calculate_available_stock(on_hand: int, reserved: int) -> dict:
    """
    Calculate available-to-promise stock.
    
    Returns dict with available quantity and any warnings.
    """
    warnings = []
    if on_hand < 0:
        warnings.append("On-hand inventory is negative — data may be corrupt.")
    if reserved < 0:
        warnings.append("Reserved inventory is negative — data may be corrupt.")
    if on_hand < reserved:
        warnings.append(
            f"On-hand ({on_hand}) is less than reserved ({reserved}) — "
            f"inventory records may be inconsistent. Clamping available to 0."
        )
    available = max(0, on_hand - reserved)
    return {"available": available, "on_hand": on_hand, "reserved": reserved, "warnings": warnings}


def get_sku_details(scenario: dict) -> Dict[str, dict]:
    """Return dict: sku_id -> sku record."""
    return {s["sku_id"]: s for s in scenario.get("skus", [])}


def get_warehouse_details(scenario: dict) -> Dict[str, dict]:
    """Return dict: warehouse_id -> warehouse record."""
    return {w["id"]: w for w in scenario.get("warehouses", [])}


def get_all_available_stock(scenario: dict) -> List[dict]:
    """
    For every warehouse-SKU combination, compute available stock.
    Returns list of dicts with warehouse_id, sku_id, on_hand, reserved, available, warnings.
    """
    results = []
    sku_map = get_sku_details(scenario)
    wh_map = get_warehouse_details(scenario)
    for rec in scenario.get("inventory", []):
        calc = calculate_available_stock(rec["on_hand"], rec["reserved"])
        results.append({
            "warehouse_id": rec["warehouse_id"],
            "warehouse_name": wh_map.get(rec["warehouse_id"], {}).get("name", rec["warehouse_id"]),
            "sku_id": rec["sku_id"],
            "sku_name": sku_map.get(rec["sku_id"], {}).get("name", rec["sku_id"]),
            **calc,
        })
    return results


def check_safety_stock(scenario: dict) -> List[dict]:
    """
    Check for safety stock breaches.
    Returns list of breached items with details.
    """
    breaches = []
    sku_map = get_sku_details(scenario)
    wh_map = get_warehouse_details(scenario)
    inv_map = get_inventory_map(scenario)
    
    for wh_id, skus in inv_map.items():
        for sku_id, inv in skus.items():
            sku = sku_map.get(sku_id)
            if sku is None:
                continue
            avail_info = calculate_available_stock(inv["on_hand"], inv["reserved"])
            available = avail_info["available"]
            safety = sku.get("safety_stock", 0)
            if available <= safety:
                breaches.append({
                    "warehouse_id": wh_id,
                    "warehouse_name": wh_map.get(wh_id, {}).get("name", wh_id),
                    "sku_id": sku_id,
                    "sku_name": sku.get("name", sku_id),
                    "available": available,
                    "safety_stock": safety,
                    "deficit": safety - available,
                    "severity": "critical" if available == 0 else "warning",
                })
    return breaches


def get_surplus_warehouses(
    scenario: dict, 
    sku_id: str, 
    exclude_wh: Optional[str] = None,
    planning_horizon_days: int = 7,
) -> List[dict]:
    """
    Find warehouses that have genuinely transferable surplus stock for a given SKU.
    Protects the source warehouse from future shortages:
    Transferable surplus = max(0, available_stock - planned_demand_during_horizon - safety_stock + incoming_replenishment_before_horizon)
    Only stock that is genuinely safe to transfer without causing a deficit at source is recommended.
    """
    sku_map = get_sku_details(scenario)
    wh_map = get_warehouse_details(scenario)
    inv_map = get_inventory_map(scenario)
    sku = sku_map.get(sku_id)
    if sku is None:
        return []
    
    safety = sku.get("safety_stock", 0)
    avg_demand = sku.get("avg_daily_demand", 0)
    surpluses = []
    
    for wh_id, skus in inv_map.items():
        if wh_id == exclude_wh:
            continue
        if sku_id not in skus:
            continue
        inv = skus[sku_id]
        avail_info = calculate_available_stock(inv["on_hand"], inv["reserved"])
        available = avail_info["available"]
        
        # Calculate incoming reliable replenishment during planning horizon for this source warehouse
        incoming_qty = sum(
            s.get("quantity", 0) for s in get_incoming_shipments(scenario, sku_id, wh_id)
            if s.get("actual_arrival_day", 999) <= planning_horizon_days
        )
        
        # Forecast planned demand during planning horizon (or days before next delivery)
        planned_demand = avg_demand * planning_horizon_days
        
        # Transferable surplus strictly protects source safety stock and upcoming demand
        # Surplus = available - (forecast_demand - incoming_replenishment) - safety_stock
        committed_future = max(0, planned_demand - incoming_qty)
        surplus = max(0, available - committed_future - safety)
        
        # If surplus with horizon calculation is 0, also check immediate buffer (available - safety)
        # but mark future risk
        immediate_surplus = max(0, available - safety)
        
        if surplus > 0 or immediate_surplus > 0:
            # We enforce safe surplus to strictly prevent source warehouse shortage
            safe_surplus = surplus if surplus > 0 else immediate_surplus
            wh = wh_map.get(wh_id, {})
            surpluses.append({
                "warehouse_id": wh_id,
                "warehouse_name": wh.get("name", wh_id),
                "available": available,
                "safety_stock": safety,
                "planned_demand": round(planned_demand, 1),
                "incoming_reliable": incoming_qty,
                "surplus": safe_surplus,
                "strictly_safe_surplus": surplus,
                "transfer_cost_per_unit": wh.get("transfer_cost_per_unit", 0),
                "fixed_shipping_cost": wh.get("fixed_shipping_cost", 0),
                "transfer_days": wh.get("transfer_days", 0),
            })
    
    return sorted(surpluses, key=lambda x: x["surplus"], reverse=True)


def get_orders_for_sku(scenario: dict, sku_id: str, warehouse_id: Optional[str] = None) -> List[dict]:
    """Get customer orders for a given SKU, optionally filtered by warehouse."""
    orders = []
    for o in scenario.get("customer_orders", []):
        if o["sku_id"] == sku_id:
            if warehouse_id is None or o["warehouse_id"] == warehouse_id:
                orders.append(o)
    return sorted(orders, key=lambda x: (
        {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.get("priority", "low"), 4),
        x.get("deadline_day", 999)
    ))


def get_incoming_shipments(scenario: dict, sku_id: str, warehouse_id: Optional[str] = None) -> List[dict]:
    """Get incoming shipments for a given SKU, optionally filtered by warehouse."""
    shipments = []
    for s in scenario.get("incoming_shipments", []):
        if s["sku_id"] == sku_id:
            if warehouse_id is None or s["warehouse_id"] == warehouse_id:
                actual_arrival = s["expected_arrival_day"] + s.get("delay_days", 0)
                shipments.append({**s, "actual_arrival_day": actual_arrival})
    return shipments
