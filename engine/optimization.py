"""
optimization.py — MODULE 3: Smart Stock Redistribution + Central Decision Engine.

Evaluates all recovery strategies (transfer, standard reorder, express reorder,
substitution, delay/reschedule), ranks them by cost-effectiveness, applies 
hard constraints, and selects the optimal feasible action.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from engine.inventory import (
    get_sku_details,
    get_warehouse_details,
    get_inventory_map,
    calculate_available_stock,
    get_surplus_warehouses,
    get_orders_for_sku,
    get_incoming_shipments,
)
from engine.compatibility import evaluate_all_substitutes
from engine.forecasting import estimate_days_to_stockout


PRIORITY_WEIGHT = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}


def evaluate_transfer_strategy(
    scenario: dict,
    sku_id: str,
    dest_warehouse_id: str,
    required_qty: int,
    deadline_day: int,
    order_priority: str,
    late_penalty_per_day: float,
) -> List[dict]:
    """
    Evaluate warehouse-to-warehouse transfer options.
    
    For each source warehouse with surplus, calculate:
    - Transferable quantity (respecting safety stock and reservations)
    - Total transfer cost
    - Arrival time
    - Whether it meets the deadline
    """
    surpluses = get_surplus_warehouses(scenario, sku_id, exclude_wh=dest_warehouse_id)
    wh_map = get_warehouse_details(scenario)
    dest_wh = wh_map.get(dest_warehouse_id, {})
    
    options = []
    for src in surpluses:
        transferable = min(src["surplus"], required_qty)
        if transferable <= 0:
            continue
        
        transfer_cost = (
            transferable * src["transfer_cost_per_unit"]
            + src["fixed_shipping_cost"]
        )
        arrival_day = src["transfer_days"]
        meets_deadline = arrival_day <= deadline_day
        
        late_days = max(0, arrival_day - deadline_day) if not meets_deadline else 0
        penalty = late_days * late_penalty_per_day
        total_cost = transfer_cost + penalty
        
        partial = transferable < required_qty
        
        source_surplus_after = src["surplus"] - transferable
        source_avail_after = src["available"] - transferable
        source_safe = source_avail_after >= src["safety_stock"]
        
        options.append({
            "strategy": "TRANSFER",
            "source_warehouse_id": src["warehouse_id"],
            "source_warehouse_name": src["warehouse_name"],
            "dest_warehouse_id": dest_warehouse_id,
            "dest_warehouse_name": dest_wh.get("name", dest_warehouse_id),
            "sku_id": sku_id,
            "quantity": transferable,
            "required_qty": required_qty,
            "partial": partial,
            "shortfall": required_qty - transferable if partial else 0,
            "transfer_cost": round(transfer_cost, 2),
            "penalty_cost": round(penalty, 2),
            "total_cost": round(total_cost, 2),
            "arrival_day": arrival_day,
            "meets_deadline": meets_deadline,
            "late_days": late_days,
            "feasible": True,
            "source_available_before": src["available"],
            "source_available_after": source_avail_after,
            "source_safety_stock": src["safety_stock"],
            "source_planned_demand": src.get("planned_demand", 0),
            "source_surplus_before": src["surplus"],
            "source_surplus_after": source_surplus_after,
            "source_safe": source_safe,
            "source_projected_health": "Healthy (Covers upcoming 7-day demand & safety buffer)" if source_safe else "At Risk",
            "future_protection_notes": (
                f"Source {src['warehouse_name']} retains {source_avail_after} units. "
                f"7-day forecast demand is {src.get('planned_demand', 0)} units with a required safety buffer of {src['safety_stock']} units."
            ),
            "reason": (
                f"Transfer {transferable} units from {src['warehouse_name']} "
                f"(Source stock: {src['available']} -> {source_avail_after}, Safety buffer: {src['safety_stock']}). "
                f"Arrives day {arrival_day}, deadline day {deadline_day}."
            ),
        })
    
    return options


def evaluate_standard_reorder(
    scenario: dict,
    sku_id: str,
    required_qty: int,
    deadline_day: int,
    late_penalty_per_day: float,
) -> dict:
    """Evaluate placing a standard replenishment order with the supplier."""
    sku_map = get_sku_details(scenario)
    sku = sku_map.get(sku_id, {})
    
    lead_time = sku.get("standard_lead_time_days", 7)
    unit_cost = sku.get("unit_cost", 0)
    purchase_cost = required_qty * unit_cost
    
    meets_deadline = lead_time <= deadline_day
    late_days = max(0, lead_time - deadline_day)
    penalty = late_days * late_penalty_per_day
    total_cost = purchase_cost + penalty
    
    return {
        "strategy": "STANDARD_REORDER",
        "sku_id": sku_id,
        "quantity": required_qty,
        "required_qty": required_qty,
        "partial": False,
        "shortfall": 0,
        "purchase_cost": round(purchase_cost, 2),
        "penalty_cost": round(penalty, 2),
        "total_cost": round(total_cost, 2),
        "arrival_day": lead_time,
        "meets_deadline": meets_deadline,
        "late_days": late_days,
        "feasible": True,
        "reason": (
            f"Standard reorder of {required_qty} units at ${unit_cost}/unit. "
            f"Lead time: {lead_time} days. Deadline: day {deadline_day}."
        ),
    }


def evaluate_express_reorder(
    scenario: dict,
    sku_id: str,
    required_qty: int,
    deadline_day: int,
    late_penalty_per_day: float,
    express_cost_multiplier: float = 1.0,
) -> dict:
    """Evaluate placing an express/expedited replenishment order."""
    sku_map = get_sku_details(scenario)
    sku = sku_map.get(sku_id, {})
    
    lead_time = sku.get("express_lead_time_days", 3)
    unit_cost = sku.get("express_cost", sku.get("unit_cost", 0) * 1.5)
    unit_cost *= express_cost_multiplier
    purchase_cost = required_qty * unit_cost
    
    meets_deadline = lead_time <= deadline_day
    late_days = max(0, lead_time - deadline_day)
    penalty = late_days * late_penalty_per_day
    total_cost = purchase_cost + penalty
    
    return {
        "strategy": "EXPRESS_REORDER",
        "sku_id": sku_id,
        "quantity": required_qty,
        "required_qty": required_qty,
        "partial": False,
        "shortfall": 0,
        "purchase_cost": round(purchase_cost, 2),
        "penalty_cost": round(penalty, 2),
        "total_cost": round(total_cost, 2),
        "arrival_day": lead_time,
        "meets_deadline": meets_deadline,
        "late_days": late_days,
        "feasible": True,
        "reason": (
            f"Express reorder of {required_qty} units at ${round(unit_cost,2)}/unit. "
            f"Lead time: {lead_time} days. Deadline: day {deadline_day}."
        ),
    }


def evaluate_substitution_strategy(
    scenario: dict,
    sku_id: str,
    required_qty: int,
    dest_warehouse_id: str,
    deadline_day: int,
    late_penalty_per_day: float,
) -> List[dict]:
    """Evaluate using a compatible substitute from any warehouse."""
    sub_result = evaluate_all_substitutes(scenario, sku_id, required_qty)
    wh_map = get_warehouse_details(scenario)
    
    options = []
    
    for sub in sub_result.get("eligible_substitutes", []):
        # For each location where the substitute is available
        for loc in sub.get("available_locations", []):
            usable = min(loc["usable_for_substitution"], required_qty)
            if usable <= 0:
                continue
            
            is_local = loc["warehouse_id"] == dest_warehouse_id
            transfer_cost = 0 if is_local else (
                usable * loc["transfer_cost_per_unit"] + 
                wh_map.get(loc["warehouse_id"], {}).get("fixed_shipping_cost", 0)
            )
            arrival_day = 0 if is_local else loc["transfer_days"]
            
            sub_unit_cost = sub.get("unit_cost", 0)
            purchase_cost = usable * sub_unit_cost
            meets_deadline = arrival_day <= deadline_day
            late_days = max(0, arrival_day - deadline_day)
            penalty = late_days * late_penalty_per_day
            total_cost = purchase_cost + transfer_cost + penalty
            
            partial = usable < required_qty
            
            transit_info = "Local stock." if is_local else "Transfer {} days.".format(loc["transfer_days"])
            cost_diff = sub.get("cost_difference", 0)
            
            options.append({
                "strategy": "SUBSTITUTE",
                "sku_id": sku_id,
                "substitute_sku_id": sub["substitute_sku_id"],
                "substitute_name": sub.get("substitute_name", sub["substitute_sku_id"]),
                "source_warehouse_id": loc["warehouse_id"],
                "source_warehouse_name": loc["warehouse_name"],
                "dest_warehouse_id": dest_warehouse_id,
                "quantity": usable,
                "required_qty": required_qty,
                "partial": partial,
                "shortfall": required_qty - usable if partial else 0,
                "purchase_cost": round(purchase_cost, 2),
                "transfer_cost": round(transfer_cost, 2),
                "penalty_cost": round(penalty, 2),
                "total_cost": round(total_cost, 2),
                "arrival_day": arrival_day,
                "meets_deadline": meets_deadline,
                "late_days": late_days,
                "feasible": True,
                "cost_difference_per_unit": cost_diff,
                "compatibility_checks": sub.get("checks", []),
                "reason": (
                    "Use substitute {} ({} units) from {}. {} Cost diff: ${}/unit.".format(
                        sub["substitute_sku_id"], usable, loc["warehouse_name"],
                        transit_info, cost_diff
                    )
                ),
            })
    
    # Include rejected substitutes for audit
    rejected = sub_result.get("rejected_alternatives", [])
    
    return options


def evaluate_delay_strategy(
    scenario: dict,
    sku_id: str,
    order: dict,
    required_qty: int,
) -> dict:
    """Evaluate delaying/rescheduling the order."""
    sku_map = get_sku_details(scenario)
    sku = sku_map.get(sku_id, {})
    
    deadline_day = order.get("deadline_day", 7)
    late_penalty_per_day = order.get("late_penalty_per_day", 0)
    standard_lead = sku.get("standard_lead_time_days", 7)
    
    # Estimate delay: wait for standard reorder
    delay_days = max(0, standard_lead - deadline_day)
    penalty = delay_days * late_penalty_per_day
    
    return {
        "strategy": "DELAY",
        "sku_id": sku_id,
        "order_id": order.get("order_id", ""),
        "quantity": required_qty,
        "required_qty": required_qty,
        "partial": False,
        "shortfall": 0,
        "penalty_cost": round(penalty, 2),
        "total_cost": round(penalty, 2),
        "arrival_day": standard_lead,
        "meets_deadline": False,
        "late_days": delay_days,
        "feasible": delay_days <= 14,  # Feasible if delay < 2 weeks
        "reason": (
            f"Delay order {order.get('order_id', '')} by {delay_days} day(s). "
            f"Penalty: ${round(penalty, 2)}. "
            f"{'Feasible as fallback.' if delay_days <= 14 else 'Excessive delay — escalation needed.'}"
        ),
    }


def score_strategy(option: dict, policy: dict, order_priority: str = "medium") -> float:
    """
    Score a recovery strategy using the decision policy weights.
    
    Lower score = better option.
    
    Components:
    - Cost score: normalized total cost
    - Time score: arrival day (lower is better)  
    - Reliability score: partial fills penalized
    - Priority alignment: critical orders get urgency bonus
    """
    weights = policy.get("weights", {
        "cost": 0.35, "fulfillment_time": 0.30,
        "reliability": 0.20, "priority_alignment": 0.15,
    })
    
    # Cost score (0-100 scale, log-ish)
    total_cost = option.get("total_cost", 0)
    cost_score = min(100, total_cost / 10.0)  # $1000 -> 100
    
    # Time score
    arrival = option.get("arrival_day", 7)
    time_score = arrival * 10  # Each day = 10 points
    
    # Reliability score (partial fill penalty)
    reliability_score = 50 if option.get("partial", False) else 0
    if not option.get("meets_deadline", True):
        reliability_score += 30
    
    # Priority alignment
    priority_w = PRIORITY_WEIGHT.get(order_priority, 0.5)
    priority_score = (1.0 - priority_w) * 40  # Critical orders penalize slow options more
    if order_priority == "critical" and not option.get("meets_deadline", True):
        priority_score += 50
    
    total_score = (
        weights["cost"] * cost_score
        + weights["fulfillment_time"] * time_score
        + weights["reliability"] * reliability_score
        + weights["priority_alignment"] * priority_score
    )
    
    return round(total_score, 2)


def generate_recovery_options(
    scenario: dict,
    sku_id: str,
    warehouse_id: str,
    required_qty: int,
    order: dict,
    express_cost_multiplier: float = 1.0,
    transfer_cost_multiplier: float = 1.0,
) -> List[dict]:
    """
    Generate and score all feasible recovery options for a shortage.
    
    This is the central decision engine entry point for a single shortage.
    """
    deadline_day = order.get("deadline_day", 7)
    late_penalty = order.get("late_penalty_per_day", 0)
    priority = order.get("priority", "medium")
    policy = scenario.get("decision_policy", {})
    
    all_options = []
    
    # Strategy A: Transfer from another warehouse
    transfers = evaluate_transfer_strategy(
        scenario, sku_id, warehouse_id, required_qty, deadline_day, priority, late_penalty
    )
    # Apply transfer cost multiplier
    for t in transfers:
        if transfer_cost_multiplier != 1.0:
            t["transfer_cost"] = round(t.get("transfer_cost", 0) * transfer_cost_multiplier, 2)
            t["total_cost"] = round(t["transfer_cost"] + t.get("penalty_cost", 0), 2)
    all_options.extend(transfers)
    
    # Strategy B: Standard reorder
    std = evaluate_standard_reorder(scenario, sku_id, required_qty, deadline_day, late_penalty)
    all_options.append(std)
    
    # Strategy C: Express reorder
    exp = evaluate_express_reorder(
        scenario, sku_id, required_qty, deadline_day, late_penalty, express_cost_multiplier
    )
    all_options.append(exp)
    
    # Strategy D: Compatible substitute
    subs = evaluate_substitution_strategy(
        scenario, sku_id, required_qty, warehouse_id, deadline_day, late_penalty
    )
    all_options.extend(subs)
    
    # Strategy E: Delay/Reschedule
    delay = evaluate_delay_strategy(scenario, sku_id, order, required_qty)
    all_options.append(delay)
    
    # Score all options
    for opt in all_options:
        opt["score"] = score_strategy(opt, policy, priority)
        opt["order_id"] = order.get("order_id", "")
        opt["order_priority"] = priority
    
    # Sort by score (lower = better), then by cost for tie-breaking
    all_options.sort(key=lambda x: (x["score"], x.get("total_cost", 999999), x.get("arrival_day", 999)))
    
    return all_options


def select_best_strategy(options: List[dict]) -> dict:
    """
    Select the best feasible strategy from scored options.
    
    Returns the selected strategy with decision reasoning.
    """
    feasible = [o for o in options if o.get("feasible", False)]
    
    if not feasible:
        return {
            "selected": None,
            "action": "ESCALATE",
            "reason": "No feasible recovery strategy found. Manual escalation required.",
            "all_options": options,
            "feasible_count": 0,
        }
    
    best = feasible[0]
    rejected = feasible[1:] + [o for o in options if not o.get("feasible", False)]
    
    # Build rejection reasons for alternatives
    rejected_with_reasons = []
    for r in rejected:
        if not r.get("feasible", False):
            reason = f"Not feasible: {r.get('reason', 'constraint violation')}"
        elif r["score"] > best["score"]:
            reason = f"Higher cost-adjusted score ({r['score']} vs {best['score']})"
        else:
            reason = "Equivalent or better option available"
        rejected_with_reasons.append({**r, "rejection_reason": reason})
    
    return {
        "selected": best,
        "action": best["strategy"],
        "reason": best.get("reason", ""),
        "score": best["score"],
        "total_cost": best.get("total_cost", 0),
        "arrival_day": best.get("arrival_day", 0),
        "meets_deadline": best.get("meets_deadline", False),
        "all_options": options,
        "rejected_alternatives": rejected_with_reasons,
        "feasible_count": len(feasible),
    }


def run_decision_engine(
    scenario: dict,
    demand_multiplier: float = 1.0,
    delay_additional_days: int = 0,
    express_cost_multiplier: float = 1.0,
    transfer_cost_multiplier: float = 1.0,
) -> List[dict]:
    """
    Central Decision Engine — run across all at-risk orders.
    
    For each order that faces a shortage, generate all recovery options,
    score them, select the best, and compile a full decision record.
    """
    from engine.forecasting import generate_shortage_radar
    
    radar = generate_shortage_radar(scenario, demand_multiplier, delay_additional_days)
    sku_map = get_sku_details(scenario)
    inv_map = get_inventory_map(scenario)
    
    decisions = []
    
    for item in radar:
        if item.get("risk_level") not in ("CRITICAL", "HIGH", "MEDIUM"):
            continue
        
        sku_id = item["sku_id"]
        wh_id = item["warehouse_id"]
        
        # Get affected orders
        affected_orders = item.get("affected_orders", [])
        at_risk_orders = [o for o in affected_orders if o.get("at_risk", False)]
        
        if not at_risk_orders:
            # Even if no at-risk order, if safety stock is breached, we need action
            at_risk_orders = get_orders_for_sku(scenario, sku_id, wh_id)
            if not at_risk_orders:
                continue
        
        for order in at_risk_orders:
            # Calculate the shortage quantity
            inv = inv_map.get(wh_id, {}).get(sku_id, {})
            avail_info = calculate_available_stock(
                inv.get("on_hand", 0), inv.get("reserved", 0)
            )
            available = avail_info["available"]
            order_qty = order.get("quantity", 0)
            shortage_qty = max(0, order_qty - available)
            
            if shortage_qty <= 0:
                continue
            
            # Generate all recovery options
            options = generate_recovery_options(
                scenario, sku_id, wh_id, shortage_qty, order,
                express_cost_multiplier, transfer_cost_multiplier,
            )
            
            # Select best strategy
            decision = select_best_strategy(options)
            
            # Build complete decision record
            decision_record = {
                "decision_id": f"DEC-{uuid.uuid4().hex[:8].upper()}",
                "timestamp": datetime.now().isoformat(),
                "sku_id": sku_id,
                "sku_name": item.get("sku_name", sku_id),
                "warehouse_id": wh_id,
                "warehouse_name": item.get("warehouse_name", wh_id),
                "order_id": order.get("order_id", ""),
                "customer": order.get("customer", ""),
                "order_priority": order.get("priority", "medium"),
                "order_quantity": order_qty,
                "available_stock": available,
                "shortage_quantity": shortage_qty,
                "risk_level": item.get("risk_level", "UNKNOWN"),
                "days_to_stockout": item.get("days_to_stockout"),
                "selected_action": decision.get("action", "ESCALATE"),
                "selected_strategy": decision.get("selected"),
                "reason": decision.get("reason", ""),
                "estimated_cost": decision.get("total_cost", 0),
                "estimated_arrival": decision.get("arrival_day", None),
                "meets_deadline": decision.get("meets_deadline", False),
                "feasible_options_count": decision.get("feasible_count", 0),
                "rejected_alternatives": decision.get("rejected_alternatives", []),
                "all_options": decision.get("all_options", []),
                "input_conditions": {
                    "demand_multiplier": demand_multiplier,
                    "delay_additional_days": delay_additional_days,
                    "express_cost_multiplier": express_cost_multiplier,
                    "transfer_cost_multiplier": transfer_cost_multiplier,
                },
                "warnings": item.get("warnings", []),
                "data_sources": ["demo_scenario.json", "inventory_map", "compatibility_rules"],
                "evidence_completeness": "complete" if not item.get("warnings") else "partial",
            }
            
            decisions.append(decision_record)
    
    return decisions
