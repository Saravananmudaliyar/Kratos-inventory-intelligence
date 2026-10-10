"""
forecasting.py — Deterministic inventory forecasting over a 7-day horizon.

Projects daily inventory levels, estimates days-to-stockout, classifies risk,
and identifies affected orders.
"""

from typing import Dict, List, Optional, Any
from engine.inventory import (
    get_inventory_map,
    get_sku_details,
    get_warehouse_details,
    calculate_available_stock,
    get_incoming_shipments,
    get_orders_for_sku,
)


def project_inventory(
    available: int,
    avg_daily_demand: float,
    incoming_shipments: List[dict],
    horizon_days: int = 7,
    demand_multiplier: float = 1.0,
) -> List[dict]:
    """
    Project daily inventory levels over the given horizon.
    
    Args:
        available: Current available-to-promise stock.
        avg_daily_demand: Average daily consumption.
        incoming_shipments: List of dicts with 'actual_arrival_day' and 'quantity'.
        horizon_days: Number of days to project.
        demand_multiplier: Multiplier for demand (for what-if scenarios).
    
    Returns:
        List of daily records: day, opening_stock, demand, incoming, closing_stock, stockout.
    """
    daily = []
    stock = float(available)
    adjusted_demand = avg_daily_demand * demand_multiplier
    
    for day in range(1, horizon_days + 1):
        opening = stock
        demand = adjusted_demand
        incoming = sum(
            s["quantity"] for s in incoming_shipments
            if s.get("actual_arrival_day") == day
        )
        closing = opening - demand + incoming
        # Physical available stock cannot be negative in warehouse operations
        physical_closing = max(0.0, closing)
        unmet = max(0.0, -closing) if closing < 0 else 0.0
        
        daily.append({
            "day": day,
            "opening_stock": round(opening, 1),
            "demand": round(demand, 1),
            "incoming": incoming,
            "closing_stock": round(closing, 1),
            "physical_closing_stock": round(physical_closing, 1),
            "unmet_demand": round(unmet, 1),
            "stockout": closing <= 0,
        })
        stock = closing
    
    return daily


def estimate_days_to_stockout(
    available: int,
    avg_daily_demand: float,
    incoming_shipments: List[dict],
    horizon_days: int = 30,
    demand_multiplier: float = 1.0,
) -> Optional[int]:
    """
    Estimate number of days until stockout.
    
    Returns day number of first stockout, or None if no stockout within horizon.
    """
    if avg_daily_demand <= 0:
        return None  # No demand, no stockout
    
    projection = project_inventory(
        available, avg_daily_demand, incoming_shipments, 
        horizon_days, demand_multiplier
    )
    for rec in projection:
        if rec["stockout"]:
            return rec["day"]
    return None


def classify_risk(days_to_stockout: Optional[int], safety_stock_breached: bool) -> dict:
    """
    Classify inventory risk based on days to stockout.
    
    Returns dict with risk_level, color, and description.
    """
    if days_to_stockout is not None and days_to_stockout <= 2:
        return {
            "risk_level": "CRITICAL",
            "color": "red",
            "description": f"Stockout expected in {days_to_stockout} day(s). Immediate action required.",
        }
    elif days_to_stockout is not None and days_to_stockout <= 4:
        return {
            "risk_level": "HIGH",
            "color": "orange",
            "description": f"Stockout expected in {days_to_stockout} days. Urgent attention needed.",
        }
    elif days_to_stockout is not None and days_to_stockout <= 7:
        return {
            "risk_level": "MEDIUM",
            "color": "gold",
            "description": f"Stockout expected in {days_to_stockout} days. Plan replenishment.",
        }
    elif safety_stock_breached:
        return {
            "risk_level": "MEDIUM",
            "color": "gold",
            "description": "Safety stock breached but no imminent stockout.",
        }
    else:
        return {
            "risk_level": "LOW",
            "color": "green",
            "description": "Sufficient inventory for the forecast horizon.",
        }


def get_affected_orders(scenario: dict, sku_id: str, warehouse_id: str, days_to_stockout: Optional[int]) -> List[dict]:
    """
    Identify customer orders affected by a potential stockout.
    """
    orders = get_orders_for_sku(scenario, sku_id, warehouse_id)
    affected = []
    for o in orders:
        if days_to_stockout is not None and o.get("deadline_day", 999) >= days_to_stockout:
            affected.append({
                **o,
                "at_risk": True,
                "reason": f"Stockout projected on day {days_to_stockout}, order deadline is day {o['deadline_day']}.",
            })
        elif days_to_stockout is not None and days_to_stockout <= o.get("deadline_day", 999):
            affected.append({
                **o,
                "at_risk": True,
                "reason": f"Stockout projected before delivery deadline.",
            })
        else:
            affected.append({
                **o,
                "at_risk": False,
                "reason": "Order can likely be fulfilled before projected stockout." if days_to_stockout else "No stockout projected.",
            })
    return affected


def generate_shortage_radar(scenario: dict, demand_multiplier: float = 1.0, delay_additional_days: int = 0) -> List[dict]:
    """
    MODULE 1: Early Shortage Radar
    
    Scans all warehouse-SKU combinations and produces a comprehensive shortage 
    risk assessment.
    
    Returns list of risk records sorted by severity.
    """
    inv_map = get_inventory_map(scenario)
    sku_map = get_sku_details(scenario)
    wh_map = get_warehouse_details(scenario)
    
    radar_items = []
    
    for wh_id, skus in inv_map.items():
        for sku_id, inv_rec in skus.items():
            sku = sku_map.get(sku_id)
            if sku is None:
                radar_items.append({
                    "warehouse_id": wh_id,
                    "sku_id": sku_id,
                    "warnings": [f"SKU {sku_id} not found in SKU catalog. Forecast uncertain."],
                    "risk_level": "UNKNOWN",
                })
                continue
            
            wh = wh_map.get(wh_id, {})
            avail_info = calculate_available_stock(inv_rec["on_hand"], inv_rec["reserved"])
            available = avail_info["available"]
            
            # Get shipments with scenario adjustments
            shipments = get_incoming_shipments(scenario, sku_id, wh_id)
            if delay_additional_days > 0:
                for s in shipments:
                    s["actual_arrival_day"] += delay_additional_days
            
            avg_demand = sku.get("avg_daily_demand", 0)
            safety = sku.get("safety_stock", 0)
            safety_breached = available <= safety
            
            # Project 7-day inventory
            projection = project_inventory(
                available, avg_demand, shipments,
                horizon_days=7, demand_multiplier=demand_multiplier
            )
            
            days_out = estimate_days_to_stockout(
                available, avg_demand, shipments,
                horizon_days=30, demand_multiplier=demand_multiplier
            )
            
            risk = classify_risk(days_out, safety_breached)
            
            # Affected orders
            affected = get_affected_orders(scenario, sku_id, wh_id, days_out)
            
            warnings = avail_info.get("warnings", [])
            if avg_demand <= 0:
                warnings.append("No demand data available — forecast may be unreliable.")
            if not shipments:
                warnings.append("No incoming shipments scheduled for this SKU at this warehouse.")
            
            radar_items.append({
                "warehouse_id": wh_id,
                "warehouse_name": wh.get("name", wh_id),
                "sku_id": sku_id,
                "sku_name": sku.get("name", sku_id),
                "on_hand": inv_rec["on_hand"],
                "reserved": inv_rec["reserved"],
                "available": available,
                "safety_stock": safety,
                "safety_breached": safety_breached,
                "avg_daily_demand": avg_demand,
                "demand_multiplier": demand_multiplier,
                "effective_demand": round(avg_demand * demand_multiplier, 1),
                "days_to_stockout": days_out,
                "projection": projection,
                "risk_level": risk["risk_level"],
                "risk_color": risk["color"],
                "risk_description": risk["description"],
                "affected_orders": affected,
                "incoming_shipments": shipments,
                "warnings": warnings,
            })
    
    # Sort by risk severity
    risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 4}
    radar_items.sort(key=lambda x: (risk_order.get(x.get("risk_level", "UNKNOWN"), 5), -(x.get("available", 0))))
    
    return radar_items
