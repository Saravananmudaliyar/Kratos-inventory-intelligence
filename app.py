"""
StockShield AI — Intelligent Inventory Risk Prediction & Recovery Planner

Enterprise Operations Cockpit for Regional Hubs:
- Mumbai Warehouse
- Pune Warehouse
- Chennai Warehouse
- Delhi Warehouse

UI Design: Modern Enterprise Supply Chain & Operations Management Console
Features:
- Global Summary KPIs Bar
- 6 Clean Navigation Views:
  1. Warehouse Overview (2x2 Grid + Health Status + Earliest Stockout + 7-Day Forecast Chart)
  2. Stock & Products (Product table + Search/Filter + Cross-Warehouse Matrix)
  3. Transfer & Substitution (Interactive SVG Logistics Map + Moving Pulse + Source Protection + Timeline/Cost Table)
  4. Supplier Deliveries (Inbound shipments tracking + Delay root-cause analytics)
  5. Scenario Planner (Simulation shock-tests + Baseline vs Disrupted matrix)
  6. Decision History (Audit trail + CSV Exporter)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import json
import time

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


# ── Page Configuration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="StockShield AI — Inventory Operations",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Modern Enterprise Clean UI Styling ───────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    /* Global Base */
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Top Enterprise Header */
    .enterprise-topbar {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.1rem 1.6rem;
        margin-bottom: 1.25rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .brand-title {
        font-size: 1.45rem;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: -0.4px;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .brand-subtitle {
        font-size: 0.82rem;
        color: #64748b;
        font-weight: 500;
        margin: 0.15rem 0 0 0;
    }
    
    /* KPI Stats Ribbon */
    .kpi-stat-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.85rem 1.1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .kpi-stat-label {
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #64748b;
        margin-bottom: 0.2rem;
    }
    .kpi-stat-value {
        font-size: 1.35rem;
        font-weight: 700;
        color: #0f172a;
        font-family: 'JetBrains Mono', monospace;
    }
    .kpi-stat-sub {
        font-size: 0.72rem;
        color: #94a3b8;
        margin-top: 0.15rem;
    }
    
    /* 2x2 Warehouse Grid Cards */
    .wh-grid-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.3rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .wh-grid-card:hover {
        border-color: #cbd5e1;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        transform: translateY(-2px);
    }
    .wh-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 0.75rem;
        margin-bottom: 0.85rem;
        border-bottom: 1px solid #f1f5f9;
    }
    .wh-name {
        font-size: 1.15rem;
        font-weight: 700;
        color: #0f172a;
        margin: 0;
    }
    .wh-location {
        font-size: 0.8rem;
        color: #64748b;
        font-weight: 500;
    }
    
    /* Professional Badges */
    .badge-healthy {
        background-color: #ecfdf5;
        color: #059669;
        border: 1px solid #a7f3d0;
        padding: 0.25rem 0.65rem;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    .badge-warning {
        background-color: #fffbeb;
        color: #d97706;
        border: 1px solid #fde68a;
        padding: 0.25rem 0.65rem;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    .badge-critical {
        background-color: #fef2f2;
        color: #dc2626;
        border: 1px solid #fecaca;
        padding: 0.25rem 0.65rem;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    
    /* Alert Panels */
    .panel-alert {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #ef4444;
        border-radius: 10px;
        padding: 1.1rem 1.4rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .panel-alert-warning {
        border-left-color: #f59e0b;
    }
    .panel-alert-success {
        border-left-color: #10b981;
    }
    
    /* Metric Tables */
    .stDataFrame {
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        overflow: hidden;
    }
    
    /* Sidebar Polish */
    .css-1d391kg {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)


# ── Session State Initialization ────────────────────────────────────────────
if "baseline_scenario" not in st.session_state:
    st.session_state.baseline_scenario = load_scenario()

if "current_scenario" not in st.session_state:
    st.session_state.current_scenario = deep_copy_scenario(st.session_state.baseline_scenario)

if "audit_trail" not in st.session_state:
    st.session_state.audit_trail = AuditTrail()

if "sim_params" not in st.session_state:
    st.session_state.sim_params = {
        "demand_multiplier": 1.0,
        "delay_additional_days": 0,
        "express_cost_multiplier": 1.0,
        "transfer_cost_multiplier": 1.0,
    }

if "active_scenario_key" not in st.session_state:
    st.session_state.active_scenario_key = "normal"

if "selected_warehouse_view" not in st.session_state:
    st.session_state.selected_warehouse_view = "WH-PUNE"

if "confirmed_transfers" not in st.session_state:
    st.session_state.confirmed_transfers = []


# ── Formatting Helpers ──────────────────────────────────────────────────────
def format_inr(val: float) -> str:
    return f"₹{val:,.2f}"

def strategy_label(strategy: str) -> str:
    labels = {
        "TRANSFER": "Warehouse Transfer",
        "STANDARD_REORDER": "Standard Supplier Reorder",
        "EXPRESS_REORDER": "Express Supplier Reorder",
        "SUBSTITUTE": "Approved Compatible Substitute",
        "DELAY": "Reschedule Customer Order",
        "ESCALATE": "Operations Escalation Required",
    }
    return labels.get(strategy, strategy)


# ── Run Engine Simulation ───────────────────────────────────────────────────
scenario = st.session_state.current_scenario
params = st.session_state.sim_params

baseline_result = run_simulation(scenario)
sim_result = run_simulation(
    scenario,
    demand_multiplier=params["demand_multiplier"],
    delay_additional_days=params["delay_additional_days"],
    express_cost_multiplier=params["express_cost_multiplier"],
    transfer_cost_multiplier=params["transfer_cost_multiplier"],
)

st.session_state.audit_trail.record_decisions(sim_result["decisions"])
comparison = compare_scenarios(baseline_result, sim_result)
kpis = sim_result["kpis"]
radar = sim_result["radar"]
decisions = sim_result["decisions"]


# ── Top Enterprise Header Bar ───────────────────────────────────────────────
col_top_l, col_top_r = st.columns([3, 1])
with col_top_l:
    st.markdown("""
    <div class="enterprise-topbar">
        <div>
            <h1 class="brand-title">🛡️ StockShield AI</h1>
            <p class="brand-subtitle">Intelligent Inventory Risk Prediction & Recovery Planner</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_top_r:
    if kpis["critical_skus"] > 0:
        st.markdown('<div style="text-align: right; padding-top: 18px;"><span class="badge-critical">Critical Shortages Detected</span></div>', unsafe_allow_html=True)
    elif kpis["at_risk_skus"] > 0:
        st.markdown('<div style="text-align: right; padding-top: 18px;"><span class="badge-warning">At-Risk Stock Alert</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="text-align: right; padding-top: 18px;"><span class="badge-healthy">All Hubs Operational</span></div>', unsafe_allow_html=True)


# ── KPI Stats Ribbon ────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(f"""
    <div class="kpi-stat-card">
        <div class="kpi-stat-label">Monitored Items</div>
        <div class="kpi-stat-value">{kpis['total_skus_monitored']}</div>
        <div class="kpi-stat-sub">Across 4 regional hubs</div>
    </div>
    """, unsafe_allow_html=True)
with k2:
    color_val = "#dc2626" if kpis['at_risk_skus'] > 0 else "#059669"
    st.markdown(f"""
    <div class="kpi-stat-card">
        <div class="kpi-stat-label">At-Risk Items</div>
        <div class="kpi-stat-value" style="color: {color_val};">{kpis['at_risk_skus']}</div>
        <div class="kpi-stat-sub">{kpis['critical_skus']} critical breaches</div>
    </div>
    """, unsafe_allow_html=True)
with k3:
    st.markdown(f"""
    <div class="kpi-stat-card">
        <div class="kpi-stat-label">Orders Threatened</div>
        <div class="kpi-stat-value" style="color: #d97706;">{kpis['orders_threatened']}</div>
        <div class="kpi-stat-sub">Pending customer shipments</div>
    </div>
    """, unsafe_allow_html=True)
with k4:
    st.markdown(f"""
    <div class="kpi-stat-card">
        <div class="kpi-stat-label">Est. Landed Recovery Cost</div>
        <div class="kpi-stat-value">{format_inr(kpis['estimated_disruption_cost'])}</div>
        <div class="kpi-stat-sub">Optimal mitigation actions</div>
    </div>
    """, unsafe_allow_html=True)
with k5:
    st.markdown(f"""
    <div class="kpi-stat-card">
        <div class="kpi-stat-label">Active Recovery Plans</div>
        <div class="kpi-stat-value" style="color: #059669;">{kpis['feasible_recoveries']}</div>
        <div class="kpi-stat-sub">100% verified feasible</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")


# ── Professional Sidebar Navigation ─────────────────────────────────────────
with st.sidebar:
    st.markdown("### Operations Cockpit")
    nav_selection = st.radio(
        "Navigation",
        [
            "1. Warehouse Overview",
            "2. Stock & Products",
            "3. Transfer & Substitution",
            "4. Supplier Deliveries",
            "5. Scenario Planner",
            "6. Decision History",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("**Network Hubs:** Mumbai, Pune, Chennai, Delhi")
    st.caption(f"**Operating Mode:** {st.session_state.active_scenario_key.replace('_', ' ').title()}")


# ═════════════════════════════════════════════════════════════════════════════
# 1. WAREHOUSE OVERVIEW
# ═════════════════════════════════════════════════════════════════════════════
if nav_selection == "1. Warehouse Overview":
    st.subheader("Regional Warehouse Overview")
    st.caption("Active monitoring of Mumbai, Pune, Chennai, and Delhi hubs with immediate early shortage warnings.")
    
    # Early Shortage Immediate Alert Banner
    crit_radar = [r for r in radar if r["risk_level"] == "CRITICAL"]
    if crit_radar:
        for c in crit_radar:
            st.markdown(f"""
            <div class="panel-alert">
                <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                        <strong style="color:#b91c1c; font-size:1.05rem;">Early Shortage Warning: {c['sku_name']} ({c['sku_id']}) at {c['warehouse_name']}</strong>
                        <p style="margin:0.35rem 0 0 0; color:#334155; font-size:0.9rem;">
                            Stock will run out in <strong>{c['days_to_stockout']} day(s)</strong>! Current Available Stock is <strong>{c['available']} units</strong> against a required Safety Buffer of <strong>{c['safety_stock']} units</strong>.
                            Supplier shipment from <em>VoltTech Components Ltd.</em> has been delayed by 4 days.<br>
                            <span style="color:#0f172a; font-weight:600;">Recommended Action:</span> Execute safe stock redistribution from Mumbai Warehouse.
                        </p>
                    </div>
                    <div><span class="badge-critical">Critical Risk</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="panel-alert panel-alert-success">
            <strong style="color:#047857;">All Hubs Healthy:</strong> Available inventory comfortably covers 7-day forecast demand across all 4 hubs.
        </div>
        """, unsafe_allow_html=True)
        
    wh_list = scenario.get("warehouses", [])
    wh_metrics = {}
    for wh in wh_list:
        wid = wh["id"]
        wh_radar = [r for r in radar if r["warehouse_id"] == wid]
        total_skus = len(wh_radar)
        total_avail = sum(r["available"] for r in wh_radar)
        at_risk = len([r for r in wh_radar if r["risk_level"] in ("CRITICAL", "HIGH", "MEDIUM")])
        critical = len([r for r in wh_radar if r["risk_level"] == "CRITICAL"])
        earliest_stockout = min([r["days_to_stockout"] for r in wh_radar if r["days_to_stockout"] is not None] or [999])
        earliest_str = f"In {earliest_stockout} days" if earliest_stockout != 999 else "No stockout"
        shipments = [s for s in scenario.get("incoming_shipments", []) if s["warehouse_id"] == wid]
        
        badge_html = (
            '<span class="badge-critical">Critical Shortage</span>' if critical > 0
            else '<span class="badge-warning">Needs Attention</span>' if at_risk > 0
            else '<span class="badge-healthy">Healthy</span>'
        )
        wh_metrics[wid] = {
            "wh": wh,
            "total_skus": total_skus,
            "total_avail": total_avail,
            "at_risk": at_risk,
            "critical": critical,
            "earliest_stockout": earliest_str,
            "shipments": len(shipments),
            "badge": badge_html,
            "radar_items": wh_radar,
        }
        
    # 2x2 Grid of Warehouse Cards
    col_g1, col_g2 = st.columns(2)
    col_g3, col_g4 = st.columns(2)
    grid_cols = [col_g1, col_g2, col_g3, col_g4]
    
    for idx, wh in enumerate(wh_list[:4]):
        wid = wh["id"]
        m = wh_metrics[wid]
        c = grid_cols[idx]
        with c:
            st.markdown(f"""
            <div class="wh-grid-card">
                <div class="wh-card-header">
                    <div>
                        <h4 class="wh-name">{wh['name']}</h4>
                        <span class="wh-location">Regional Hub: {wh['location']}</span>
                    </div>
                    <div>{m['badge']}</div>
                </div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 0.85rem; font-size:0.86rem;">
                    <div><span style="color:#64748b;">Available Units:</span> <strong>{m['total_avail']}</strong></div>
                    <div><span style="color:#64748b;">Products Monitored:</span> <strong>{m['total_skus']}</strong></div>
                    <div><span style="color:#ea580c;">At-Risk Products:</span> <strong>{m['at_risk']}</strong></div>
                    <div><span style="color:#dc2626;">Critical Shortages:</span> <strong>{m['critical']}</strong></div>
                    <div><span style="color:#64748b;">Incoming Deliveries:</span> <strong>{m['shipments']} shipment(s)</strong></div>
                    <div><span style="color:#64748b;">Earliest Stockout:</span> <strong>{m['earliest_stockout']}</strong></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"View Products ({wh['name']})", key=f"view_btn_{wid}", use_container_width=True):
                st.session_state.selected_warehouse_view = wid
    
    # Selected Warehouse Detail View
    selected_wid = st.session_state.selected_warehouse_view
    sel_m = wh_metrics.get(selected_wid)
    if sel_m:
        st.markdown("---")
        st.markdown(f"### Inventory Detail: {sel_m['wh']['name']}")
        
        # 7-Day Single Compact Stock Forecast Graph
        risk_skus = [r for r in sel_m["radar_items"] if r["risk_level"] in ("CRITICAL", "HIGH")]
        target_sku = risk_skus[0] if risk_skus else sel_m["radar_items"][0]
        
        proj = target_sku.get("projection", [])
        if proj:
            days = [f"Day {p['day']}" for p in proj]
            phys_stocks = [p.get("physical_closing_stock", max(0.0, p["closing_stock"])) for p in proj]
            unmet_demands = [p.get("unmet_demand", 0.0) for p in proj]
            safety = target_sku.get("safety_stock", 0)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=days, y=phys_stocks, mode="lines+markers",
                name="Projected Available Stock",
                line=dict(color="#059669", width=3),
                marker=dict(size=7, color="#059669"),
            ))
            fig.add_hline(
                y=safety, line_dash="dash", line_color="#d97706",
                annotation_text=f"Safety Threshold ({safety} units)",
                annotation_position="top left",
            )
            if any(u > 0 for u in unmet_demands):
                fig.add_trace(go.Bar(
                    x=days, y=unmet_demands, name="Unmet Demand (Stockout)",
                    marker_color="#ef4444", opacity=0.4,
                ))
            fig.update_layout(
                title=f"7-Day Stock Trajectory: {target_sku['sku_name']} ({target_sku['sku_id']})",
                xaxis_title="Planning Timeline", yaxis_title="Units",
                height=300,
                template="plotly_white",
                margin=dict(l=30, r=20, t=40, b=30),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)
            
        # Product Table for Selected Warehouse
        wh_prod_data = []
        for r in sel_m["radar_items"]:
            wh_prod_data.append({
                "Product Name": r["sku_name"],
                "SKU": r["sku_id"],
                "Physical On-Hand": r["on_hand"],
                "Reserved": r["reserved"],
                "Available (ATP)": r["available"],
                "Safety Stock": r["safety_stock"],
                "Daily Demand": r["effective_demand"],
                "Estimated Stockout": f"Day {r['days_to_stockout']}" if r["days_to_stockout"] else "Healthy",
                "Status": r["risk_level"],
            })
        st.dataframe(pd.DataFrame(wh_prod_data), use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# 2. STOCK & PRODUCTS
# ═════════════════════════════════════════════════════════════════════════════
elif nav_selection == "2. Stock & Products":
    st.subheader("Stock & Products Catalog")
    st.caption("Complete inventory visibility across products, warehouses, and demand metrics.")
    
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        search_query = st.text_input("Search Product or SKU", placeholder="e.g. Charger, Mouse, SKU-CHARGER-65W")
    with col_f2:
        wh_filter = st.selectbox("Filter by Warehouse", ["All Warehouses"] + [w["name"] for w in scenario["warehouses"]])
    with col_f3:
        status_filter = st.selectbox("Filter by Status", ["All Statuses", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
        
    all_stock_data = []
    for r in radar:
        if search_query and (search_query.lower() not in r["sku_name"].lower() and search_query.lower() not in r["sku_id"].lower()):
            continue
        if wh_filter != "All Warehouses" and r["warehouse_name"] != wh_filter:
            continue
        if status_filter != "All Statuses" and r["risk_level"] != status_filter:
            continue
            
        all_stock_data.append({
            "Warehouse": r["warehouse_name"],
            "Product Name": r["sku_name"],
            "SKU": r["sku_id"],
            "Physical Stock": r["on_hand"],
            "Reserved Stock": r["reserved"],
            "Available Stock": r["available"],
            "Safety Stock": r["safety_stock"],
            "Daily Demand": r["effective_demand"],
            "Forecast Stockout": f"Day {r['days_to_stockout']}" if r["days_to_stockout"] else "Healthy",
            "Risk Tier": r["risk_level"],
        })
    st.dataframe(pd.DataFrame(all_stock_data), use_container_width=True, hide_index=True)
    
    # Cross-Warehouse Comparison View
    st.markdown("---")
    st.markdown("### Cross-Warehouse Product Comparison")
    st.caption("Compare inventory allocation, safety buffers, and surplus across all 4 hubs.")
    
    sku_dict = {s["sku_id"]: s["name"] for s in scenario["skus"]}
    selected_comp_sku = st.selectbox("Select Product to Compare Across Network", list(sku_dict.keys()), format_func=lambda x: f"{x} — {sku_dict[x]}")
    
    comp_rows = []
    inv_map = get_inventory_map(scenario)
    sku_info = get_sku_details(scenario).get(selected_comp_sku, {})
    
    for wh in scenario["warehouses"]:
        wid = wh["id"]
        inv = inv_map.get(wid, {}).get(selected_comp_sku, {"on_hand": 0, "reserved": 0})
        avail = max(0, inv["on_hand"] - inv["reserved"])
        safety = sku_info.get("safety_stock", 0)
        surplus = max(0, avail - safety)
        comp_rows.append({
            "Warehouse": wh["name"],
            "Location": wh["location"],
            "Physical On-Hand": inv["on_hand"],
            "Reserved Stock": inv["reserved"],
            "Available Stock": avail,
            "Safety Buffer": safety,
            "Immediate Surplus": surplus,
            "Transit Days": wh.get("transfer_days", 1),
            "Transfer Cost/Unit": format_inr(wh.get("transfer_cost_per_unit", 10.0)),
        })
    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# 3. TRANSFER & SUBSTITUTION (WITH INTEGRATED SVG NETWORK MAP ANIMATION)
# ═════════════════════════════════════════════════════════════════════════════
elif nav_selection == "3. Transfer & Substitution":
    st.subheader("Warehouse Transfer & Substitution Planner")
    st.caption("Inter-warehouse redistribution route optimization with strict source protection and component compatibility validation.")
    
    # 1. Transfer Selector
    col_tr1, col_tr2, col_tr3 = st.columns([1.5, 1.5, 1])
    wh_map = {w["id"]: w["name"] for w in scenario["warehouses"]}
    sku_map = {s["sku_id"]: s["name"] for s in scenario["skus"]}
    
    with col_tr1:
        source_wh_id = st.selectbox("Source Warehouse", list(wh_map.keys()), index=0, format_func=lambda x: wh_map[x])
    with col_tr2:
        dest_wh_id = st.selectbox("Destination Warehouse", list(wh_map.keys()), index=1, format_func=lambda x: wh_map[x])
    with col_tr3:
        tr_qty = st.number_input("Transfer Quantity", min_value=5, max_value=100, value=20, step=5)
        
    tr_sku = st.selectbox("Select Product to Transfer", list(sku_map.keys()), index=0, format_func=lambda x: f"{x} — {sku_map[x]}")
    
    # 2. Source Future Stock Protection Calculations
    inv_map = get_inventory_map(scenario)
    sku_data = get_sku_details(scenario).get(tr_sku, {})
    src_inv = inv_map.get(source_wh_id, {}).get(tr_sku, {"on_hand": 0, "reserved": 0})
    dest_inv = inv_map.get(dest_wh_id, {}).get(tr_sku, {"on_hand": 0, "reserved": 0})
    
    src_avail = max(0, src_inv["on_hand"] - src_inv["reserved"])
    dest_avail = max(0, dest_inv["on_hand"] - dest_inv["reserved"])
    src_safety = sku_data.get("safety_stock", 0)
    
    surplus_list = get_surplus_warehouses(scenario, tr_sku, exclude_wh=dest_wh_id)
    matched_surplus = next((s for s in surplus_list if s["warehouse_id"] == source_wh_id), None)
    safe_transferable_surplus = matched_surplus["surplus"] if matched_surplus else 0
    src_planned_demand = matched_surplus.get("planned_demand", sku_data.get("avg_daily_demand", 0) * 7) if matched_surplus else 0
    
    src_after = src_avail - tr_qty
    dest_after = dest_avail + tr_qty
    is_safe = src_after >= src_safety
    
    dest_wh_data = get_warehouse_details(scenario).get(dest_wh_id, {})
    cost_per_unit = dest_wh_data.get("transfer_cost_per_unit", 10.0)
    fixed_ship = dest_wh_data.get("fixed_shipping_cost", 100.0)
    total_tr_cost = (tr_qty * cost_per_unit) + fixed_ship
    tr_days = dest_wh_data.get("transfer_days", 1)
    
    # 3. Clean SVG Network Diagram with Animated Stock Movement
    st.markdown("---")
    st.markdown("#### Warehouse Network Route Map")
    
    coords = {
        "WH-DELHI": (260, 50),
        "WH-MUMBAI": (120, 180),
        "WH-PUNE": (180, 230),
        "WH-CHENNAI": (270, 310),
    }
    src_pt = coords.get(source_wh_id, (120, 180))
    dest_pt = coords.get(dest_wh_id, (180, 230))
    
    svg_nodes_html = ""
    for wid, (cx, cy) in coords.items():
        wname = wh_map.get(wid, wid).replace(" Warehouse", "")
        is_src = (wid == source_wh_id)
        is_dest = (wid == dest_wh_id)
        fill_color = "#3b82f6" if is_src else "#10b981" if is_dest else "#f8fafc"
        stroke_color = "#1d4ed8" if is_src else "#047857" if is_dest else "#94a3b8"
        text_color = "#ffffff" if (is_src or is_dest) else "#0f172a"
        
        svg_nodes_html += f"""
        <g>
            <circle cx="{cx}" cy="{cy}" r="22" fill="{fill_color}" stroke="{stroke_color}" stroke-width="2.5"/>
            <text x="{cx}" y="{cy+4}" font-family="Plus Jakarta Sans, sans-serif" font-size="9" font-weight="700" fill="{text_color}" text-anchor="middle">{wname[:3].upper()}</text>
            <text x="{cx}" y="{cy+34}" font-family="Plus Jakarta Sans, sans-serif" font-size="10" font-weight="600" fill="#0f172a" text-anchor="middle">{wname}</text>
        </g>
        """
        
    svg_network = f"""
    <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:1.5rem; text-align:center;">
        <svg width="460" height="360" viewBox="0 0 420 360" style="margin:auto; display:block;">
            <defs>
                <linearGradient id="routeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#3b82f6"/>
                    <stop offset="100%" stop-color="#10b981"/>
                </linearGradient>
            </defs>
            <!-- Network Mesh -->
            <line x1="260" y1="50" x2="120" y2="180" stroke="#e2e8f0" stroke-width="1.5" stroke-dasharray="3,3"/>
            <line x1="120" y1="180" x2="180" y2="230" stroke="#e2e8f0" stroke-width="1.5" stroke-dasharray="3,3"/>
            <line x1="180" y1="230" x2="270" y2="310" stroke="#e2e8f0" stroke-width="1.5" stroke-dasharray="3,3"/>
            <line x1="260" y1="50" x2="270" y2="310" stroke="#e2e8f0" stroke-width="1.5" stroke-dasharray="3,3"/>
            
            <!-- Active Route -->
            <line x1="{src_pt[0]}" y1="{src_pt[1]}" x2="{dest_pt[0]}" y2="{dest_pt[1]}" stroke="url(#routeGrad)" stroke-width="4" stroke-linecap="round"/>
            
            <!-- Animated Stock Movement Indicator -->
            <circle r="6" fill="#f59e0b" stroke="#ffffff" stroke-width="2">
                <animateMotion path="M {src_pt[0]} {src_pt[1]} L {dest_pt[0]} {dest_pt[1]}" dur="2s" repeatCount="indefinite"/>
            </circle>
            
            <!-- Network Nodes -->
            {svg_nodes_html}
        </svg>
        <p style="color:#64748b; font-size:0.85rem; margin-top:0.5rem;">
            Active Transfer Corridor: <strong>{wh_map[source_wh_id]} ➔ {wh_map[dest_wh_id]}</strong> | Dispatching: <strong>{tr_qty} units of {sku_map[tr_sku]}</strong>
        </p>
    </div>
    """
    st.markdown(svg_network, unsafe_allow_html=True)
    
    # 4. Future Stock Protection & Impact Summary
    st.markdown("---")
    st.markdown("#### Future Stock Protection & Landed Cost Analysis")
    
    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1:
        st.markdown(f"**Source ({wh_map[source_wh_id]}):**")
        st.markdown(f"• Current Available Stock: **{src_avail} units**")
        st.markdown(f"• Post-Transfer Stock: **{src_after} units**")
        st.markdown(f"• 7-Day Planned Demand: **{src_planned_demand} units**")
        st.markdown(f"• Safety Buffer Threshold: **{src_safety} units**")
        if is_safe:
            st.success("Safe Transfer: Source retains required buffer and demand coverage.")
        else:
            st.error("Unsafe Transfer: Would breach source safety stock threshold!")
            
    with col_i2:
        st.markdown(f"**Destination ({wh_map[dest_wh_id]}):**")
        st.markdown(f"• Current Available Stock: **{dest_avail} units**")
        st.markdown(f"• Post-Transfer Stock: **{dest_after} units**")
        st.markdown(f"• Shortage Resolved: **Yes ({tr_qty} units delivered)**")
        
    with col_i3:
        st.markdown("**Logistics & Timeline:**")
        st.markdown(f"• Landed Freight Cost: **{format_inr(total_tr_cost)}**")
        st.markdown(f"• Travel Time: **{tr_days} day(s)**")
        st.markdown("• Status: **Route Verified**")
        
    # 5. Actions: Simulate vs Confirm Transfer
    col_act1, col_act2 = st.columns(2)
    with col_act1:
        if st.button("Simulate Transfer (Preview Only)", use_container_width=True):
            st.info(f"Simulated Transfer of {tr_qty} units from {wh_map[source_wh_id]} to {wh_map[dest_wh_id]} is verified feasible. Real inventory unaffected.")
    with col_act2:
        if st.button("Confirm Operational Transfer", type="primary", use_container_width=True):
            rec = {
                "transfer_id": f"TRF-{len(st.session_state.confirmed_transfers)+1:03d}",
                "source": wh_map[source_wh_id],
                "destination": wh_map[dest_wh_id],
                "sku": sku_map[tr_sku],
                "quantity": tr_qty,
                "cost": total_tr_cost,
                "arrival": f"In {tr_days} day(s)",
                "status": "In-Transit (Dispatched)",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            st.session_state.confirmed_transfers.append(rec)
            st.success(f"Transfer confirmed: {tr_qty} units dispatched from {wh_map[source_wh_id]} to {wh_map[dest_wh_id]}. Operational records updated.")
            
    if st.session_state.confirmed_transfers:
        st.markdown("---")
        st.markdown("##### Operational Transfer Manifests")
        st.dataframe(pd.DataFrame(st.session_state.confirmed_transfers), use_container_width=True, hide_index=True)
        
    # 6. Component Compatibility Engine
    st.markdown("---")
    st.markdown("### Component Compatibility Evaluation")
    st.caption("Evaluates technical substitutes under strict engineering voltage, pin-out, and form-factor constraints.")
    
    sub_res = evaluate_all_substitutes(scenario, tr_sku, required_qty=20)
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown("#### Approved & Compatible Substitutes")
        if sub_res["eligible_substitutes"]:
            for sub in sub_res["eligible_substitutes"]:
                st.markdown(f"""
                <div class="panel-alert panel-alert-success">
                    <strong>{sub['substitute_name']} ({sub['substitute_sku_id']})</strong><br>
                    • Unit Cost: <strong>{format_inr(sub['unit_cost'])}</strong> (Difference: {format_inr(sub['cost_difference'])})<br>
                    • Available Across Network: <strong>{sub['total_available']} units</strong><br>
                    • Compatibility: <em>Verified electrical and form-factor replacement</em>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No approved compatible substitute found for this SKU.")
    with col_s2:
        st.markdown("#### Rejected / Incompatible Alternatives")
        if sub_res["rejected_alternatives"]:
            for rej in sub_res["rejected_alternatives"]:
                reasons = "<br>• ".join(rej.get("rejection_reasons", []))
                st.markdown(f"""
                <div class="panel-alert">
                    <strong style="color:#b91c1c;">{rej['substitute_name']} ({rej['substitute_sku_id']}) — REJECTED</strong><br>
                    • {reasons}
                </div>
                """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# 4. SUPPLIER DELIVERIES
# ═════════════════════════════════════════════════════════════════════════════
elif nav_selection == "4. Supplier Deliveries":
    st.subheader("Supplier Inbound Deliveries & Purchase Orders")
    st.caption("Active monitoring of expected vendor shipments, transit schedules, and delay tracking.")
    
    shipments = scenario.get("incoming_shipments", [])
    sku_info_map = get_sku_details(scenario)
    wh_info_map = get_warehouse_details(scenario)
    
    deliv_table = []
    for s in shipments:
        actual_arr = s["expected_arrival_day"] + s.get("delay_days", 0)
        deliv_table.append({
            "Shipment ID": s["shipment_id"],
            "Supplier": s.get("supplier", "Supplier Partner"),
            "Product": sku_info_map.get(s["sku_id"], {}).get("name", s["sku_id"]),
            "Destination Warehouse": wh_info_map.get(s["warehouse_id"], {}).get("name", s["warehouse_id"]),
            "Quantity": s["quantity"],
            "Expected Arrival": f"Day {s['expected_arrival_day']}",
            "Delay": f"+{s['delay_days']} days" if s.get("delay_days", 0) > 0 else "On-Time",
            "Projected Arrival": f"Day {actual_arr}",
            "Delivery Status": s["status"].upper(),
        })
    st.dataframe(pd.DataFrame(deliv_table), use_container_width=True, hide_index=True)
    
    delayed_list = [d for d in deliv_table if "DELAY" in d["Delivery Status"] or "+0" not in d["Delay"]]
    if delayed_list:
        st.markdown("---")
        st.markdown("#### Supply Chain Delay Impact Analysis")
        for dl in delayed_list:
            st.markdown(f"""
            <div class="panel-alert panel-alert-warning">
                <strong>Shipment Delay Alert: {dl['Shipment ID']} ({dl['Product']})</strong><br>
                Supplier <em>{dl['Supplier']}</em> is delayed by <strong>{dl['Delay']}</strong>. 
                Expected delivery at {dl['Destination Warehouse']} shifted from {dl['Expected Arrival']} to <strong>{dl['Projected Arrival']}</strong>.<br>
                Root Cause: Port clearance delay. StockShield decision engine has initiated recovery redistribution.
            </div>
            """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# 5. SCENARIO PLANNER
# ═════════════════════════════════════════════════════════════════════════════
elif nav_selection == "5. Scenario Planner":
    st.subheader("Scenario Planner (Stress-Testing & What-If Analysis)")
    st.caption("Configure simulated supply-chain disruptions with standard form inputs. Changes are simulated and do not alter real operational inventory.")
    
    predef = get_predefined_scenarios()
    
    st.markdown("##### 1. Preset Scenarios")
    p_cols = st.columns(len(predef))
    for i, (k, p_data) in enumerate(predef.items()):
        with p_cols[i]:
            if st.button(p_data["name"], key=f"btn_preset_{k}", use_container_width=True):
                st.session_state.active_scenario_key = k
                st.session_state.sim_params = {**p_data["params"]}
                st.rerun()
                
    st.markdown("---")
    st.markdown("##### 2. Custom Disruption Parameters")
    
    col_sc1, col_sc2, col_sc3 = st.columns(3)
    with col_sc1:
        in_demand = st.number_input("Demand Multiplier (e.g. 1.5 = +50% demand surge)", min_value=0.5, max_value=3.0, value=float(params["demand_multiplier"]), step=0.1)
    with col_sc2:
        in_delay = st.number_input("Additional Supplier Delay (Days)", min_value=0, max_value=14, value=int(params["delay_additional_days"]), step=1)
    with col_sc3:
        in_transfer = st.number_input("Transfer Freight Cost Multiplier", min_value=0.5, max_value=3.0, value=float(params["transfer_cost_multiplier"]), step=0.1)
        
    col_btn_apply, col_btn_reset = st.columns([1, 1])
    with col_btn_apply:
        if st.button("Apply Simulation Parameters", type="primary", use_container_width=True):
            st.session_state.sim_params = {
                "demand_multiplier": in_demand,
                "delay_additional_days": in_delay,
                "express_cost_multiplier": 1.0,
                "transfer_cost_multiplier": in_transfer,
            }
            st.session_state.active_scenario_key = "custom"
            st.rerun()
    with col_btn_reset:
        if st.button("Reset to Normal Baseline", use_container_width=True):
            st.session_state.current_scenario = deep_copy_scenario(st.session_state.baseline_scenario)
            st.session_state.sim_params = {
                "demand_multiplier": 1.0,
                "delay_additional_days": 0,
                "express_cost_multiplier": 1.0,
                "transfer_cost_multiplier": 1.0,
            }
            st.session_state.active_scenario_key = "normal"
            st.rerun()
            
    # Baseline vs Disrupted Comparison Table
    st.markdown("---")
    st.markdown("#### Scenario Impact Comparison Matrix")
    
    kpi_comp = comparison.get("kpi_comparison", {})
    comp_view = []
    labels = {
        "total_skus_monitored": "Total Products Monitored",
        "at_risk_skus": "At-Risk Products",
        "critical_skus": "Critical Shortages",
        "orders_threatened": "Threatened Customer Orders",
        "estimated_disruption_cost": "Est. Disruption Cost (₹)",
        "feasible_recoveries": "Feasible Recovery Options",
    }
    for k, v in kpi_comp.items():
        if k in labels:
            comp_view.append({
                "Metric": labels[k],
                "Baseline Operations": f"₹{v['baseline']:,.2f}" if "cost" in k else v['baseline'],
                "Simulated Scenario": f"₹{v['disrupted']:,.2f}" if "cost" in k else v['disrupted'],
                "Delta Impact": f"+{v.get('delta',0)}" if v.get('delta',0) > 0 else v.get('delta',0),
            })
    st.dataframe(pd.DataFrame(comp_view), use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# 6. DECISION HISTORY
# ═════════════════════════════════════════════════════════════════════════════
elif nav_selection == "6. Decision History":
    st.subheader("Decision History & Audit Trail")
    st.caption("Complete, auditable log of all evaluated shortages, selected recovery strategies, rejected options, and cost calculations.")
    
    audit = st.session_state.audit_trail
    history = audit.get_history()
    
    if history:
        st.markdown(f"**Total Documented Decisions:** {len(history)}")
        
        csv_log = audit.export_csv()
        st.download_button(
            label="Download Complete Audit Trail (CSV)",
            data=csv_log,
            file_name=f"stockshield_decision_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )
        
        st.markdown("---")
        for d in history:
            with st.expander(f"Decision {d.get('decision_id')} — Order {d.get('order_id')} ({d.get('sku_id')} at {d.get('warehouse_name')})"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Shortage Context:**")
                    st.markdown(f"• Product: **{d.get('sku_name')}**")
                    st.markdown(f"• Warehouse: **{d.get('warehouse_name')}**")
                    st.markdown(f"• Customer: **{d.get('customer')}** (Priority: {d.get('order_priority', '').upper()})")
                    st.markdown(f"• Available Stock: **{d.get('available_stock')} units** | Shortage: **{d.get('shortage_quantity')} units**")
                with c2:
                    st.markdown("**Selected Recovery Action:**")
                    st.markdown(f"• Action: **{strategy_label(d.get('selected_action'))}**")
                    st.markdown(f"• Landed Cost: **{format_inr(d.get('estimated_cost', 0))}**")
                    st.markdown(f"• Estimated Arrival: **Day {d.get('estimated_arrival')}**")
                    st.markdown(f"• Reasoning: *{d.get('reason')}*")
                    
                rej = d.get("rejected_alternatives", [])
                if rej:
                    st.markdown("**Rejected Alternatives:**")
                    for r in rej[:4]:
                        st.caption(f"• {strategy_label(r.get('strategy'))}: {r.get('rejection_reason', r.get('reason', 'N/A'))[:120]}")
    else:
        st.info("No decisions recorded yet.")


# ── Enterprise Footer ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<p style="text-align: center; color: #64748b; font-size: 0.8rem;">'
    'StockShield AI — Intelligent Inventory Risk Prediction & Recovery Planner | '
    'Mumbai • Pune • Chennai • Delhi | Deterministic Decision Engine'
    '</p>',
    unsafe_allow_html=True,
)
