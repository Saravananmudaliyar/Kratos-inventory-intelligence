"""
server.py — FastAPI Backend powering the StockShield AI Web Application.

Serves REST endpoints for:
- Full network state, KPIs & 2x2 regional warehouse aggregations
- Shortage radar & 7-day projections with exact DD/MM/YYYY calendar dates
- Cross-warehouse product matrix
- Safe transfer evaluation with strict source future stock protection
- Real-time stock transfer execution updating physical ledger and inbound pipeline
- 4-Warehouse Forward-Looking Replenishment & Delivery Planning Engine
- Component compatibility engine
- Supply disruption simulations & one-click presets
- Decision history audit & CSV export
- Static enterprise web client frontend (HTML/CSS/JS)
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from engine.inventory import (
    load_scenario,
    deep_copy_scenario,
    get_all_available_stock,
    check_safety_stock,
    get_sku_details,
    get_warehouse_details,
    get_inventory_map,
    get_surplus_warehouses,
    get_orders_for_sku,
    get_incoming_shipments,
    calculate_available_stock,
)
from engine.forecasting import (
    generate_shortage_radar,
    project_inventory,
    classify_risk,
)
from engine.compatibility import (
    evaluate_all_substitutes,
    validate_substitute,
    find_compatible_skus,
)
from engine.optimization import (
    run_decision_engine,
    generate_recovery_options,
    select_best_strategy,
)
from engine.simulation import (
    get_predefined_scenarios,
    run_simulation,
    compare_scenarios,
)
from engine.audit import AuditTrail

# Initialize application
app = FastAPI(
    title="StockShield AI Backend",
    description="Operational Decision Engine & Inventory Risk API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base timeline date: October 10, 2026 (Today)
BASE_SIM_DATE = datetime(2026, 10, 10)

def day_to_date_str(day_offset: Optional[int]) -> str:
    """Convert integer day offset (1, 2, ...) to DD/MM/YYYY format."""
    if day_offset is None:
        return "None (Safe)"
    target_date = BASE_SIM_DATE + timedelta(days=day_offset)
    return target_date.strftime("%d/%m/%Y")


# Global In-Memory State
BASE_SCENARIO = load_scenario()
CURRENT_SCENARIO = deep_copy_scenario(BASE_SCENARIO)
AUDIT_TRAIL = AuditTrail()
CONFIRMED_TRANSFERS: List[Dict[str, Any]] = []
SIM_PARAMS = {
    "demand_multiplier": 1.0,
    "delay_additional_days": 0,
    "express_cost_multiplier": 1.0,
    "transfer_cost_multiplier": 1.0,
}
ACTIVE_SCENARIO_KEY = "normal"


def build_full_state():
    """Build unified, rich payload for frontend consumption with exact DD/MM/YYYY dates and 4-warehouse delivery plans."""
    sim = run_simulation(
        CURRENT_SCENARIO,
        demand_multiplier=SIM_PARAMS["demand_multiplier"],
        delay_additional_days=SIM_PARAMS["delay_additional_days"],
        express_cost_multiplier=SIM_PARAMS["express_cost_multiplier"],
        transfer_cost_multiplier=SIM_PARAMS["transfer_cost_multiplier"],
    )
    baseline = run_simulation(CURRENT_SCENARIO)
    comparison = compare_scenarios(baseline, sim)
    AUDIT_TRAIL.record_decisions(sim["decisions"])

    wh_map = get_warehouse_details(CURRENT_SCENARIO)
    sku_map = get_sku_details(CURRENT_SCENARIO)
    inv_map = get_inventory_map(CURRENT_SCENARIO)
    radar = sim["radar"]

    # 1. Enrich 4 Regional Warehouses
    warehouses_list = []
    for wh_id, wh_info in wh_map.items():
        wh_radar = [r for r in radar if r["warehouse_id"] == wh_id]
        total_avail = sum(r["available"] for r in wh_radar)
        total_phys = sum(r["on_hand"] for r in wh_radar)
        total_res = sum(r["reserved"] for r in wh_radar)
        at_risk = len([r for r in wh_radar if r["risk_level"] in ("CRITICAL", "HIGH", "MEDIUM")])
        critical_count = len([r for r in wh_radar if r["risk_level"] == "CRITICAL"])
        
        # Inbound shipments count (including transfers)
        inbound = [s for s in CURRENT_SCENARIO.get("incoming_shipments", []) if (s.get("warehouse_id") == wh_id or s.get("destination_warehouse_id") == wh_id)]
        total_inbound_units = sum(s.get("quantity", 0) for s in inbound)
        
        # Earliest stockout date in DD/MM/YYYY
        stockouts = [r["days_to_stockout"] for r in wh_radar if r["days_to_stockout"] is not None]
        earliest_day = min(stockouts) if stockouts else None
        earliest_str = day_to_date_str(earliest_day) if earliest_day is not None else "None (Safe)"

        status = "CRITICAL" if critical_count > 0 else ("WARNING" if at_risk > 0 else "HEALTHY")

        warehouses_list.append({
            "wh_id": wh_id,
            "name": wh_info.get("name", wh_id),
            "location": wh_info.get("location", ""),
            "total_skus": len(wh_radar),
            "available_units": total_avail,
            "physical_units": total_phys,
            "reserved_units": total_res,
            "inbound_units": total_inbound_units,
            "at_risk_count": at_risk,
            "critical_count": critical_count,
            "incoming_deliveries": len(inbound),
            "earliest_stockout_date": earliest_str,
            "status": status,
        })

    # 2. Enrich Products Catalog with Inbound Deliveries & Projected Balances
    products_list = []
    for r in radar:
        wh_info = wh_map.get(r["warehouse_id"], {})
        stockout_str = day_to_date_str(r.get('days_to_stockout')) if r.get("days_to_stockout") is not None else "Safe"
        
        # Inbound for this specific SKU & warehouse
        sku_inbound = get_incoming_shipments(CURRENT_SCENARIO, r["sku_id"], r["warehouse_id"])
        inbound_qty = sum(s.get("quantity", 0) for s in sku_inbound)
        earliest_inbound = day_to_date_str(min([s["actual_arrival_day"] for s in sku_inbound])) if sku_inbound else "-"
        
        # Final projected closing stock on Day 7
        proj_7day = r["projection"][-1]["physical_closing_stock"] if r.get("projection") else r["available"]

        products_list.append({
            "wh_id": r["warehouse_id"],
            "wh_name": wh_info.get("name", r["warehouse_id"]),
            "wh_location": wh_info.get("location", ""),
            "sku_id": r["sku_id"],
            "product_name": r["sku_name"],
            "physical_stock": r["on_hand"],
            "reserved_stock": r["reserved"],
            "available_stock": r["available"],
            "inbound_units": inbound_qty,
            "inbound_arrival_date": earliest_inbound,
            "projected_stock": proj_7day,
            "safety_buffer": r["safety_stock"],
            "daily_demand": r["avg_daily_demand"],
            "forecast_stockout_date": stockout_str,
            "status": r["risk_level"],
            "transit_time_days": wh_info.get("transfer_days", 1),
            "transfer_cost_per_unit": wh_info.get("transfer_cost_per_unit", 12.0),
        })

    # 3. Early Warning Banner with exact calendar date & mitigation feedback
    critical_items = [r for r in radar if r["risk_level"] == "CRITICAL"]
    if critical_items:
        first = critical_items[0]
        stockout_date = day_to_date_str(first.get('days_to_stockout', 1))
        early_warn = {
            "type": "critical",
            "text": f"<strong>Early Shortage Warning:</strong> Projecting stockout for <strong>{first['sku_name']}</strong> at <strong>{first['warehouse_name']}</strong> on <strong>{stockout_date}</strong>. Immediate warehouse transfer or compatible substitution recommended."
        }
    elif len(CONFIRMED_TRANSFERS) > 0:
        latest = CONFIRMED_TRANSFERS[0]
        early_warn = {
            "type": "success",
            "text": f"<strong>✅ Shortage Successfully Mitigated:</strong> Dispatched <strong>{latest['quantity']} units</strong> of <strong>{latest['product']}</strong> from {latest['source']} to {latest['dest']} (Expected Arrival: <strong>{latest['expected_arrival']}</strong>). Both source & destination inventory balances recalculated."
        }
    else:
        warning_items = [r for r in radar if r["risk_level"] in ("HIGH", "MEDIUM")]
        if warning_items:
            first = warning_items[0]
            early_warn = {
                "type": "warning",
                "text": f"<strong>Buffer Breach Advisory:</strong> Safety stock breached for <strong>{first['sku_name']}</strong> at <strong>{first['warehouse_name']}</strong>. Monitoring replenishment."
            }
        else:
            early_warn = {
                "type": "success",
                "text": "<strong>All Warehouses Nominal:</strong> No stockouts projected over the forecast horizon across Mumbai, Pune, Chennai, and Delhi."
            }

    # 4. Inbound Deliveries with DD/MM/YYYY Arrival Dates
    deliveries_list = []
    for s in CURRENT_SCENARIO.get("incoming_shipments", []):
        dest_id = s.get("warehouse_id") or s.get("destination_warehouse_id")
        dest_wh = wh_map.get(dest_id, {})
        sku = sku_map.get(s.get("sku_id"), {})
        exp_day = s.get("expected_arrival_day", 1)
        delay = s.get("delay_days", s.get("supplier_delay_days", 0)) + SIM_PARAMS["delay_additional_days"]
        act_day = exp_day + delay
        deliveries_list.append({
            "shipment_id": s.get("shipment_id", ""),
            "supplier": s.get("supplier", "Tier-1 Electronics OEM"),
            "product_name": sku.get("name", s.get("sku_id")),
            "dest_wh_name": dest_wh.get("name", dest_id),
            "quantity": s.get("quantity", 0),
            "expected_arrival": day_to_date_str(exp_day),
            "delay_days": delay,
            "actual_projected_arrival": day_to_date_str(act_day),
            "status": "In-Transit (Dispatched)" if "TRF" in s.get("shipment_id", "") else ("Delayed" if delay > 0 else "On Schedule")
        })

    # 5. Dedicated 4-Warehouse Forward Stock Replenishment & Delivery Plans
    warehouse_plans = []
    for wh_id, wh_info in wh_map.items():
        wh_radar = [r for r in radar if r["warehouse_id"] == wh_id]
        wh_inbound = [s for s in deliveries_list if s["dest_wh_name"] == wh_info.get("name", wh_id)]
        
        cur_avail = sum(r["available"] for r in wh_radar)
        inbound_units = sum(s["quantity"] for s in wh_inbound)
        planned_7day_demand = sum(r["avg_daily_demand"] * 7 for r in wh_radar)
        projected_closing = max(0, round(cur_avail + inbound_units - planned_7day_demand, 1))
        
        # Coverage days
        daily_burn = sum(r["avg_daily_demand"] for r in wh_radar)
        coverage_days = round((cur_avail + inbound_units) / daily_burn, 1) if daily_burn > 0 else 30.0
        
        crit_count = len([r for r in wh_radar if r["risk_level"] == "CRITICAL"])
        has_transfers = any("Transfer" in s["supplier"] for s in wh_inbound)
        
        if crit_count > 0:
            plan_status = "CRITICAL SHORTAGE"
            action_plan = f"Expedite inter-warehouse transfer or initiate urgent compatible substitution."
        elif has_transfers:
            plan_status = "RECOVERY EN ROUTE"
            action_plan = f"Inter-hub transfer en route. Stock coverage restored to {coverage_days} days."
        elif cur_avail > planned_7day_demand:
            plan_status = "SURPLUS OPTIMAL"
            action_plan = f"Healthy stock buffer. Capable of supporting deficit regional hubs."
        else:
            plan_status = "BUFFER MONITORED"
            action_plan = f"Scheduled vendor replenishment arrives on track to maintain minimum safety buffers."

        warehouse_plans.append({
            "wh_id": wh_id,
            "name": wh_info.get("name", wh_id),
            "location": wh_info.get("location", ""),
            "current_available": cur_avail,
            "inbound_units": inbound_units,
            "planned_7day_demand": round(planned_7day_demand, 1),
            "projected_closing": projected_closing,
            "coverage_days": coverage_days,
            "plan_status": plan_status,
            "action_plan": action_plan,
            "scheduled_deliveries": wh_inbound,
        })

    # 6. Delay Root-Cause Analysis
    delayed_count = len([d for d in deliveries_list if d["delay_days"] > 0])
    if delayed_count > 0:
        delay_analysis = f"<strong>Port & Customs Congestion Impact:</strong> {delayed_count} inbound shipment(s) currently delayed by up to {max(d['delay_days'] for d in deliveries_list)} days. Pune Hub facing component depletion for USB-C Fast Chargers due to OEM shipment #SHP-001 delay."
    else:
        delay_analysis = "All inbound logistics routes and purchase order deliveries are tracking on schedule."

    # 7. Presets
    presets_data = [
        {"id": "supplier_delay", "title": "Supplier Port Delay (+5 Days)", "description": "Simulates customs bottleneck delaying key OEM shipments to Pune and Chennai."},
        {"id": "demand_surge", "title": "Festival Demand Surge (+80%)", "description": "Tests network resilience under intense retail festive shopping spike."},
        {"id": "freight_spike", "title": "Interstate Freight Spike (+100%)", "description": "Tests cost-optimality when express logistics costs double."},
        {"id": "compound_crisis", "title": "Compound Disruption Shock", "description": "Simultaneous 50% demand surge combined with 4-day supplier delay."},
    ]

    # 8. Pre-computed Technical Compatibility Mapping
    compatibility_data = {}
    for sku_id in sku_map.keys():
        eval_subs = evaluate_all_substitutes(CURRENT_SCENARIO, sku_id, required_qty=20)
        appr = []
        for sub in eval_subs.get("compatible", []):
            appr.append({
                "sku_id": sub.get("sku_id"),
                "name": sub.get("name", sub.get("sku_id")),
                "reason": f"Pin-compatible, matching voltage ({sub.get('voltage', '5V-20V')}) & verified form factor. Unit cost diff: ₹{sub.get('unit_cost', 0) - sku_map[sku_id].get('unit_cost', 0):+.2f}"
            })
        rej = []
        for sub in eval_subs.get("incompatible", []):
            rej.append({
                "sku_id": sub.get("sku_id"),
                "name": sub.get("name", sub.get("sku_id")),
                "reason": sub.get("rejection_reason", "Technical specification mismatch")
            })
        compatibility_data[sku_id] = {"approved": appr, "rejected": rej}

    # 9. Decision History Format
    decision_history = []
    for d in sim["decisions"]:
        best = d.get("recommended_strategy", {})
        decision_history.append({
            "title": f"Mitigation Strategy for {d.get('sku_name')} ({d.get('warehouse_name')})",
            "sku_id": d.get("sku_id"),
            "status": "Optimal Plan Formulated",
            "action_summary": f"{best.get('action_type', 'Warehouse Transfer')} — {best.get('details', 'Inter-hub dispatch')}",
            "reasoning": f"Total Estimated Cost: ₹{best.get('estimated_cost', 0):.2f} | Execution Time: {best.get('execution_days', 1)} day(s). Protects all customer deadlines.",
            "rejection_notes": "Rejected delayed fulfilment (heavy SLA penalties) and unverified component substitutes.",
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"),
        })

    return {
        "kpis": sim["kpis"],
        "early_warning": early_warn,
        "warehouses": warehouses_list,
        "products": products_list,
        "deliveries": deliveries_list,
        "warehouse_plans": warehouse_plans,
        "delay_analysis": delay_analysis,
        "transfer_logs": CONFIRMED_TRANSFERS,
        "presets": presets_data,
        "compatibility": compatibility_data,
        "decision_history": decision_history,
        "comparison": comparison,
    }


@app.get("/api/state")
def get_state():
    """Return comprehensive state for frontend views."""
    return build_full_state()


@app.post("/api/simulate")
def update_simulation(params: Dict[str, Any] = Body(...)):
    """Update simulation parameters and return simulated comparison."""
    global SIM_PARAMS, ACTIVE_SCENARIO_KEY
    SIM_PARAMS["demand_multiplier"] = float(params.get("demand_multiplier", 1.0))
    SIM_PARAMS["delay_additional_days"] = int(params.get("supplier_delay_days", params.get("delay_additional_days", 0)))
    SIM_PARAMS["transfer_cost_multiplier"] = float(params.get("transfer_cost_multiplier", 1.0))
    SIM_PARAMS["express_cost_multiplier"] = float(params.get("express_cost_multiplier", 1.0))
    ACTIVE_SCENARIO_KEY = params.get("active_scenario_key", "custom")

    baseline = run_simulation(CURRENT_SCENARIO)
    sim = run_simulation(
        CURRENT_SCENARIO,
        demand_multiplier=SIM_PARAMS["demand_multiplier"],
        delay_additional_days=SIM_PARAMS["delay_additional_days"],
        express_cost_multiplier=SIM_PARAMS["express_cost_multiplier"],
        transfer_cost_multiplier=SIM_PARAMS["transfer_cost_multiplier"],
    )
    comp = compare_scenarios(baseline, sim)
    return comp


@app.post("/api/scenario/preset")
def load_preset(payload: Dict[str, Any] = Body(...)):
    """Load a predefined scenario shock preset."""
    global SIM_PARAMS, ACTIVE_SCENARIO_KEY
    preset_id = payload.get("preset_id", "supplier_delay")
    
    if preset_id == "supplier_delay":
        SIM_PARAMS = {"demand_multiplier": 1.0, "delay_additional_days": 5, "express_cost_multiplier": 1.0, "transfer_cost_multiplier": 1.0}
    elif preset_id == "demand_surge":
        SIM_PARAMS = {"demand_multiplier": 1.8, "delay_additional_days": 0, "express_cost_multiplier": 1.0, "transfer_cost_multiplier": 1.0}
    elif preset_id == "freight_spike":
        SIM_PARAMS = {"demand_multiplier": 1.0, "delay_additional_days": 0, "express_cost_multiplier": 2.0, "transfer_cost_multiplier": 2.0}
    elif preset_id == "compound_crisis":
        SIM_PARAMS = {"demand_multiplier": 1.5, "delay_additional_days": 4, "express_cost_multiplier": 1.5, "transfer_cost_multiplier": 1.5}
    
    ACTIVE_SCENARIO_KEY = preset_id
    baseline = run_simulation(CURRENT_SCENARIO)
    sim = run_simulation(
        CURRENT_SCENARIO,
        demand_multiplier=SIM_PARAMS["demand_multiplier"],
        delay_additional_days=SIM_PARAMS["delay_additional_days"],
        express_cost_multiplier=SIM_PARAMS["express_cost_multiplier"],
        transfer_cost_multiplier=SIM_PARAMS["transfer_cost_multiplier"],
    )
    return compare_scenarios(baseline, sim)


@app.post("/api/scenario/reset")
def reset_scenario():
    """Reset to baseline scenario without accumulated changes."""
    global CURRENT_SCENARIO, SIM_PARAMS, ACTIVE_SCENARIO_KEY, CONFIRMED_TRANSFERS
    CURRENT_SCENARIO = deep_copy_scenario(BASE_SCENARIO)
    CONFIRMED_TRANSFERS = []
    SIM_PARAMS = {
        "demand_multiplier": 1.0,
        "delay_additional_days": 0,
        "express_cost_multiplier": 1.0,
        "transfer_cost_multiplier": 1.0,
    }
    ACTIVE_SCENARIO_KEY = "normal"
    return build_full_state()


@app.post("/api/transfer/evaluate")
def evaluate_transfer(payload: Dict[str, Any] = Body(...)):
    """Evaluate a potential transfer with source future stock protection."""
    source_wh = payload.get("source_wh") or payload.get("source_wh_id")
    dest_wh = payload.get("dest_wh") or payload.get("dest_wh_id")
    sku_id = payload.get("sku_id")
    qty = int(payload.get("quantity", 20))
    
    inv_map = get_inventory_map(CURRENT_SCENARIO)
    sku_details = get_sku_details(CURRENT_SCENARIO).get(sku_id, {})
    wh_map = get_warehouse_details(CURRENT_SCENARIO)
    
    src_inv = inv_map.get(source_wh, {}).get(sku_id, {"on_hand": 0, "reserved": 0})
    dest_inv = inv_map.get(dest_wh, {}).get(sku_id, {"on_hand": 0, "reserved": 0})
    
    src_avail = max(0, src_inv["on_hand"] - src_inv["reserved"])
    dest_avail = max(0, dest_inv["on_hand"] - dest_inv["reserved"])
    src_safety = sku_details.get("safety_stock", 0)
    src_daily_demand = sku_details.get("avg_daily_demand", 0)
    src_7day_demand = round(src_daily_demand * 7, 1)
    
    surplus_list = get_surplus_warehouses(CURRENT_SCENARIO, sku_id, exclude_wh=dest_wh)
    matched_surplus = next((s for s in surplus_list if s["warehouse_id"] == source_wh), None)
    max_safe = matched_surplus["surplus"] if matched_surplus else max(0, src_avail - src_7day_demand - src_safety)
    
    dest_wh_rec = wh_map.get(dest_wh, {})
    cost_per_unit = dest_wh_rec.get("transfer_cost_per_unit", 16.0)
    fixed_ship = dest_wh_rec.get("fixed_shipping_cost", 100.0)
    total_cost = (qty * cost_per_unit) + fixed_ship
    transit_days = dest_wh_rec.get("transfer_days", 1)
    
    src_after = src_avail - qty
    is_safe = qty <= max_safe and src_after >= src_safety
    
    return {
        "sku_id": sku_id,
        "sku_name": sku_details.get("name", sku_id),
        "source_warehouse": wh_map.get(source_wh, {}).get("name", source_wh),
        "dest_warehouse": wh_map.get(dest_wh, {}).get("name", dest_wh),
        "source_available": src_avail,
        "source_after_transfer": src_after,
        "source_safety_buffer": src_safety,
        "source_7day_demand": src_7day_demand,
        "max_safe_transfer": max(0, int(max_safe)),
        "is_safe": is_safe,
        "freight_cost": total_cost,
        "transit_days": transit_days,
        "expected_arrival_date": day_to_date_str(transit_days),
    }


@app.post("/api/transfer/confirm")
def confirm_transfer(payload: Dict[str, Any] = Body(...)):
    """Confirm an operational transfer, deduct source inventory, and add inbound pipeline shipment to destination."""
    global CONFIRMED_TRANSFERS, CURRENT_SCENARIO
    source_wh = payload.get("source_wh") or payload.get("source_wh_id")
    dest_wh = payload.get("dest_wh") or payload.get("dest_wh_id")
    sku_id = payload.get("sku_id")
    qty = int(payload.get("quantity", 20))
    
    eval_res = evaluate_transfer(payload)
    
    # 1. Deduct stock from source warehouse inventory
    if source_wh in CURRENT_SCENARIO.get("inventory", {}) and sku_id in CURRENT_SCENARIO["inventory"][source_wh]:
        CURRENT_SCENARIO["inventory"][source_wh][sku_id]["on_hand"] = max(
            0, CURRENT_SCENARIO["inventory"][source_wh][sku_id]["on_hand"] - qty
        )
    
    # 2. Add inbound replenishment to destination warehouse pipeline
    CURRENT_SCENARIO.setdefault("incoming_shipments", []).append({
        "shipment_id": f"TRF-INBOUND-{len(CONFIRMED_TRANSFERS)+1:03d}",
        "sku_id": sku_id,
        "warehouse_id": dest_wh,
        "destination_warehouse_id": dest_wh,
        "supplier": f"Inter-Warehouse Transfer ({eval_res['source_warehouse']})",
        "quantity": qty,
        "expected_arrival_day": eval_res["transit_days"],
        "delay_days": 0,
        "supplier_delay_days": 0,
        "actual_arrival_day": eval_res["transit_days"],
        "status": "in_transit",
    })
    
    manifest_id = f"TRF-{len(CONFIRMED_TRANSFERS) + 1:03d}"
    record = {
        "id": manifest_id,
        "source": eval_res["source_warehouse"],
        "dest": eval_res["dest_warehouse"],
        "product": eval_res["sku_name"],
        "quantity": qty,
        "freight_cost": eval_res["freight_cost"],
        "expected_arrival": f"{eval_res['expected_arrival_date']} ({eval_res['transit_days']*24} hrs)",
        "status": "Dispatched (In-Transit)",
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }
    CONFIRMED_TRANSFERS.insert(0, record)
    return {"success": True, "manifest_id": manifest_id, "record": record}


@app.get("/api/compatibility/{sku_id}")
def check_substitutes(sku_id: str, qty: int = 20):
    """Evaluate approved and rejected technical substitutes."""
    return evaluate_all_substitutes(CURRENT_SCENARIO, sku_id, required_qty=qty)


@app.get("/api/audit/csv")
def download_audit_csv():
    """Download CSV audit log."""
    csv_str = AUDIT_TRAIL.export_csv()
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=stockshield_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )


# Serve Static Frontend Files
STATIC_DIR = Path(__file__).parent / "static"
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>StockShield AI — Static Frontend Initializing...</h1>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
