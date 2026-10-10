"""
simulation.py — MODULE 4: What-If Supply Simulator.

Provides scenario manipulation, predefined disruption scenarios, 
baseline vs disrupted comparison, and reset functionality.
"""

import copy
from typing import Dict, List, Optional, Any

from engine.inventory import load_scenario, deep_copy_scenario
from engine.forecasting import generate_shortage_radar
from engine.optimization import run_decision_engine


# Predefined scenarios
PREDEFINED_SCENARIOS = {
    "normal": {
        "name": "Normal Operations",
        "description": "Baseline scenario with standard demand and no additional disruptions.",
        "params": {
            "demand_multiplier": 1.0,
            "delay_additional_days": 0,
            "express_cost_multiplier": 1.0,
            "transfer_cost_multiplier": 1.0,
        },
    },
    "supplier_delay": {
        "name": "Critical Supplier Shipment Delayed",
        "description": "Key supplier shipment delayed by 5 additional days, impacting component availability.",
        "params": {
            "demand_multiplier": 1.0,
            "delay_additional_days": 5,
            "express_cost_multiplier": 1.0,
            "transfer_cost_multiplier": 1.0,
        },
    },
    "demand_spike": {
        "name": "Sudden Demand Spike",
        "description": "Demand increases by 80% across all components due to unexpected market conditions.",
        "params": {
            "demand_multiplier": 1.8,
            "delay_additional_days": 0,
            "express_cost_multiplier": 1.0,
            "transfer_cost_multiplier": 1.0,
        },
    },
    "warehouse_imbalance": {
        "name": "Warehouse Stock Imbalance",
        "description": "Transfer costs increase 2x and express costs rise 50%, creating redistribution pressure.",
        "params": {
            "demand_multiplier": 1.0,
            "delay_additional_days": 0,
            "express_cost_multiplier": 1.5,
            "transfer_cost_multiplier": 2.0,
        },
    },
    "combined_disruption": {
        "name": "Combined Disruption: Delay + Demand Spike",
        "description": "Supplier delayed 4 days AND demand spikes 60%. Worst-case stress test.",
        "params": {
            "demand_multiplier": 1.6,
            "delay_additional_days": 4,
            "express_cost_multiplier": 1.3,
            "transfer_cost_multiplier": 1.5,
        },
    },
}


def get_predefined_scenarios() -> Dict[str, dict]:
    """Return all predefined scenario definitions."""
    return PREDEFINED_SCENARIOS


def run_simulation(
    scenario: dict,
    demand_multiplier: float = 1.0,
    delay_additional_days: int = 0,
    express_cost_multiplier: float = 1.0,
    transfer_cost_multiplier: float = 1.0,
) -> dict:
    """
    Run a complete simulation with the given parameters.
    
    Returns:
        Dict with radar results, decisions, and simulation parameters.
    """
    radar = generate_shortage_radar(scenario, demand_multiplier, delay_additional_days)
    decisions = run_decision_engine(
        scenario, demand_multiplier, delay_additional_days,
        express_cost_multiplier, transfer_cost_multiplier,
    )
    
    # Compute KPIs
    total_skus = len(set(
        (r["warehouse_id"], r["sku_id"]) for r in radar
    ))
    at_risk_skus = len([r for r in radar if r.get("risk_level") in ("CRITICAL", "HIGH", "MEDIUM")])
    critical_skus = len([r for r in radar if r.get("risk_level") == "CRITICAL"])
    
    all_affected_orders = set()
    for r in radar:
        for o in r.get("affected_orders", []):
            if o.get("at_risk"):
                all_affected_orders.add(o.get("order_id", ""))
    
    total_disruption_cost = sum(d.get("estimated_cost", 0) for d in decisions)
    feasible_recovery = len([d for d in decisions if d.get("selected_action") != "ESCALATE"])
    
    return {
        "params": {
            "demand_multiplier": demand_multiplier,
            "delay_additional_days": delay_additional_days,
            "express_cost_multiplier": express_cost_multiplier,
            "transfer_cost_multiplier": transfer_cost_multiplier,
        },
        "radar": radar,
        "decisions": decisions,
        "kpis": {
            "total_skus_monitored": total_skus,
            "at_risk_skus": at_risk_skus,
            "critical_skus": critical_skus,
            "orders_threatened": len(all_affected_orders),
            "estimated_disruption_cost": round(total_disruption_cost, 2),
            "feasible_recoveries": feasible_recovery,
            "escalations": len(decisions) - feasible_recovery,
        },
    }


def compare_scenarios(baseline: dict, disrupted: dict) -> dict:
    """
    Compare baseline vs disrupted simulation results.
    
    Returns a comparison dict with deltas for each KPI and per-SKU changes.
    """
    b_kpis = baseline.get("kpis", {})
    d_kpis = disrupted.get("kpis", {})
    
    kpi_comparison = {}
    for key in b_kpis:
        b_val = b_kpis.get(key, 0)
        d_val = d_kpis.get(key, 0)
        kpi_comparison[key] = {
            "baseline": b_val,
            "disrupted": d_val,
            "delta": round(d_val - b_val, 2) if isinstance(d_val, (int, float)) else None,
            "direction": "worse" if isinstance(d_val, (int, float)) and d_val > b_val else "better" if isinstance(d_val, (int, float)) and d_val < b_val else "same",
        }
    
    # Per-SKU risk changes
    b_risk = {}
    for r in baseline.get("radar", []):
        key = f"{r['warehouse_id']}_{r['sku_id']}"
        b_risk[key] = r.get("risk_level", "LOW")
    
    d_risk = {}
    for r in disrupted.get("radar", []):
        key = f"{r['warehouse_id']}_{r['sku_id']}"
        d_risk[key] = r.get("risk_level", "LOW")
    
    risk_changes = []
    risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 4}
    for key in set(list(b_risk.keys()) + list(d_risk.keys())):
        b_r = b_risk.get(key, "LOW")
        d_r = d_risk.get(key, "LOW")
        if b_r != d_r:
            parts = key.split("_", 1)
            risk_changes.append({
                "warehouse_sku": key,
                "warehouse_id": parts[0] if len(parts) > 0 else "",
                "sku_id": parts[1] if len(parts) > 1 else "",
                "baseline_risk": b_r,
                "disrupted_risk": d_r,
                "worsened": risk_order.get(d_r, 4) < risk_order.get(b_r, 4),
            })
    
    # Decision changes
    b_decisions = {d.get("order_id"): d for d in baseline.get("decisions", [])}
    d_decisions = {d.get("order_id"): d for d in disrupted.get("decisions", [])}
    
    decision_changes = []
    for order_id in set(list(b_decisions.keys()) + list(d_decisions.keys())):
        b_dec = b_decisions.get(order_id)
        d_dec = d_decisions.get(order_id)
        
        if b_dec and d_dec:
            if b_dec.get("selected_action") != d_dec.get("selected_action") or \
               b_dec.get("estimated_cost") != d_dec.get("estimated_cost"):
                decision_changes.append({
                    "order_id": order_id,
                    "baseline_action": b_dec.get("selected_action", "N/A"),
                    "disrupted_action": d_dec.get("selected_action", "N/A"),
                    "baseline_cost": b_dec.get("estimated_cost", 0),
                    "disrupted_cost": d_dec.get("estimated_cost", 0),
                    "cost_delta": round(d_dec.get("estimated_cost", 0) - b_dec.get("estimated_cost", 0), 2),
                })
        elif d_dec and not b_dec:
            decision_changes.append({
                "order_id": order_id,
                "baseline_action": "No action needed",
                "disrupted_action": d_dec.get("selected_action", "N/A"),
                "baseline_cost": 0,
                "disrupted_cost": d_dec.get("estimated_cost", 0),
                "cost_delta": d_dec.get("estimated_cost", 0),
            })
    
    return {
        "kpi_comparison": kpi_comparison,
        "risk_changes": risk_changes,
        "decision_changes": decision_changes,
        "newly_affected_skus": len([r for r in risk_changes if r.get("worsened")]),
        "param_changes": {
            "baseline": baseline.get("params", {}),
            "disrupted": disrupted.get("params", {}),
        },
    }
