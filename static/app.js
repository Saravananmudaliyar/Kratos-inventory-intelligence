/**
 * StockShield AI — Enterprise Inventory Operations Cockpit
 * Frontend Application Controller
 */

// Global State Object
const AppState = {
    data: null,
    selectedWhId: "WH-PUNE",
    selectedMatrixSku: "SKU-CHARGER-65W",
    chartInstance: null,
    activeTab: "overview"
};

// Hub Map Coordinates
const HubCoords = {
    "WH-DELHI": { x: 260, y: 50, code: "DEL", name: "Delhi Warehouse" },
    "WH-MUMBAI": { x: 120, y: 170, code: "BOM", name: "Mumbai Warehouse" },
    "WH-PUNE": { x: 180, y: 220, code: "PNQ", name: "Pune Warehouse" },
    "WH-CHENNAI": { x: 270, y: 290, code: "MAA", name: "Chennai Warehouse" }
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initFilters();
    initTransferForm();
    initScenarioPlanner();
    fetchAppState();
});

// Toast System
function showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icon = type === "success" ? "fa-circle-check" : type === "error" ? "fa-circle-exclamation" : "fa-circle-info";
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// Navigation Tabs
function initNavigation() {
    const tabButtons = document.querySelectorAll(".nav-btn");
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const target = btn.getAttribute("data-target");
            tabButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            document.querySelectorAll(".page-view").forEach(view => {
                view.classList.remove("active");
            });
            const activeView = document.getElementById(`view-${target}`);
            if (activeView) activeView.classList.add("active");
            AppState.activeTab = target;

            if (target === "overview" && AppState.data) {
                renderTrajectoryChart(AppState.selectedWhId);
            }
        });
    });
}

// Fetch Full Application State from FastAPI Backend
async function fetchAppState() {
    try {
        const response = await fetch("/api/state");
        if (!response.ok) throw new Error("Failed to fetch system state");
        AppState.data = await response.json();
        
        renderExecutiveKpis();
        renderEarlyWarning();
        renderWarehouseCards();
        renderTrajectoryChart(AppState.selectedWhId);
        renderCatalogTable();
        populateMatrixSkuDropdown();
        renderMatrixTable();
        initMapNodes();
        populateTransferDropdowns();
        evaluateTransferSafety();
        renderTransferLogs();
        renderCompatibilitySection();
        renderDeliveries();
        renderDelayAnalysis();
        renderPresets();
        renderDecisionHistory();
        if (AppState.data.comparison) {
            renderSimulationComparison(AppState.data.comparison);
        }
    } catch (err) {
        console.error("Error loading application state:", err);
        showToast("Error communicating with decision engine: " + err.message, "error");
    }
}

// Render Executive KPIs Banner
function renderExecutiveKpis() {
    const kpis = AppState.data.kpis;
    if (!kpis) return;

    const monitored = kpis.total_skus_monitored || kpis.monitored_skus || 32;
    const atRisk = kpis.at_risk_skus || 0;
    const critical = kpis.critical_skus || 0;
    const orders = kpis.orders_threatened || 0;
    const cost = kpis.estimated_disruption_cost || kpis.est_disruption_cost || 0;
    const feasible = kpis.feasible_recoveries || kpis.verified_feasible_options || 0;

    document.getElementById("kpiMonitored").textContent = `${monitored} SKUs`;
    document.getElementById("kpiAtRisk").textContent = `${atRisk} SKUs`;
    document.getElementById("kpiCriticalSub").textContent = `${critical} critical shortages`;
    document.getElementById("kpiOrdersThreatened").textContent = `${orders} Orders`;
    document.getElementById("kpiDisruptionCost").textContent = `₹${cost.toLocaleString()}`;
    document.getElementById("kpiFeasible").textContent = `${feasible} / ${feasible}`;

    const pill = document.getElementById("globalStatusPill");
    if (critical > 0) {
        pill.className = "status-pill status-pill-critical";
        pill.innerHTML = `<span class="pulse-dot"></span> Critical Shortages Detected`;
    } else if (atRisk > 0) {
        pill.className = "status-pill status-pill-warning";
        pill.innerHTML = `<span class="pulse-dot"></span> Warning: Buffer Breached`;
    } else {
        pill.className = "status-pill status-pill-healthy";
        pill.innerHTML = `<span class="pulse-dot"></span> Network Nominal`;
    }
}

// Render Early Warning Strip
function renderEarlyWarning() {
    const warn = AppState.data.early_warning;
    const banner = document.getElementById("earlyWarningBanner");
    const textEl = document.getElementById("earlyWarningText");
    if (!warn || !warn.text) {
        banner.style.display = "none";
        return;
    }
    banner.style.display = "flex";
    banner.className = `alert-banner alert-banner-${warn.type || 'warning'}`;
    textEl.innerHTML = warn.text;
}

// Render 2x2 Warehouse Overview Grid
function renderWarehouseCards() {
    const grid = document.getElementById("warehouseGrid");
    grid.innerHTML = "";
    const warehouses = AppState.data.warehouses || [];

    warehouses.forEach(wh => {
        const card = document.createElement("div");
        const statusClass = wh.critical_count > 0 ? "status-critical" : wh.at_risk_count > 0 ? "status-warning" : "status-healthy";
        const isSelected = wh.wh_id === AppState.selectedWhId ? "selected" : "";
        card.className = `warehouse-card ${statusClass} ${isSelected}`;
        card.onclick = () => selectWarehouse(wh.wh_id);

        const badgeClass = wh.critical_count > 0 ? "wh-badge-critical" : wh.at_risk_count > 0 ? "wh-badge-warning" : "wh-badge-healthy";
        const badgeText = wh.critical_count > 0 ? "Critical Shortage" : wh.at_risk_count > 0 ? "Buffer At Risk" : "Optimal Stock";

        card.innerHTML = `
            <div class="wh-header">
                <div>
                    <div class="wh-name">${wh.name}</div>
                    <div class="wh-loc"><i class="fa-solid fa-location-dot"></i> ${wh.location}</div>
                </div>
                <span class="wh-badge ${badgeClass}">${badgeText}</span>
            </div>
            <div class="wh-stats-grid">
                <div class="wh-stat-item">
                    <div class="wh-stat-num">${wh.available_units}</div>
                    <div class="wh-stat-lbl">Available ATP</div>
                </div>
                <div class="wh-stat-item">
                    <div class="wh-stat-num">${wh.physical_units}</div>
                    <div class="wh-stat-lbl">Physical Stock</div>
                </div>
                <div class="wh-stat-item">
                    <div class="wh-stat-num">${wh.reserved_units}</div>
                    <div class="wh-stat-lbl">Committed</div>
                </div>
            </div>
            <div class="wh-footer">
                <div><i class="fa-solid fa-triangle-exclamation"></i> <strong>${wh.at_risk_count}</strong> at risk (${wh.critical_count} critical)</div>
                <div><i class="fa-solid fa-clock"></i> Earliest stockout: <strong>${wh.earliest_stockout_date || 'None'}</strong></div>
            </div>
        `;
        grid.appendChild(card);
    });
}

// Select Warehouse & Update Detail View
function selectWarehouse(whId) {
    AppState.selectedWhId = whId;
    renderWarehouseCards();
    renderTrajectoryChart(whId);
}

// Render Trajectory Chart using Chart.js
function renderTrajectoryChart(whId) {
    const wh = (AppState.data.warehouses || []).find(w => w.wh_id === whId) || (AppState.data.warehouses && AppState.data.warehouses[0]);
    if (!wh) return;

    document.getElementById("whDetailTitle").textContent = `${wh.name} — 7-Day Forecast Stock Trajectory`;
    document.getElementById("whDetailSub").textContent = `Monitored SKUs, dynamic customer reservation drawdowns, and supplier arrival points for ${wh.location}`;

    // Get products for this warehouse
    const products = (AppState.data.products || []).filter(p => p.wh_id === whId);
    
    // Update Products Table in warehouse detail
    const tbody = document.querySelector("#whProductsTable tbody");
    tbody.innerHTML = "";
    products.forEach(p => {
        const row = document.createElement("tr");
        const statusBadge = p.status === "CRITICAL" ? '<span class="badge badge-critical">Critical</span>' :
                            p.status === "HIGH" ? '<span class="badge badge-warning">High Risk</span>' :
                            p.status === "MEDIUM" ? '<span class="badge badge-warning">Buffer Breached</span>' :
                            '<span class="badge badge-success">Healthy</span>';
        
        row.innerHTML = `
            <td><strong>${p.product_name}</strong></td>
            <td class="mono">${p.sku_id}</td>
            <td>${p.physical_stock}</td>
            <td class="text-muted">${p.reserved_stock}</td>
            <td><strong class="text-primary">${p.available_stock}</strong></td>
            <td>${p.safety_buffer}</td>
            <td>${p.daily_demand}/day</td>
            <td><strong>${p.forecast_stockout_date || 'None (Safe)'}</strong></td>
            <td>${statusBadge}</td>
        `;
        tbody.appendChild(row);
    });

    // Generate 7-Day Forecast Chart Data
    const days = ["Day 0 (Now)", "Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"];
    const datasets = products.slice(0, 4).map((p, idx) => {
        const colors = ["#2563eb", "#dc2626", "#059669", "#d97706"];
        const dataPoints = [];
        let cur = p.available_stock;
        for (let d = 0; d <= 7; d++) {
            dataPoints.push(Math.max(0, Math.round(cur)));
            cur -= p.daily_demand;
        }
        return {
            label: p.product_name,
            data: dataPoints,
            borderColor: colors[idx % colors.length],
            backgroundColor: colors[idx % colors.length] + "15",
            borderWidth: 2,
            tension: 0.25,
            fill: false
        };
    });

    const chartCanvas = document.getElementById("whTrajectoryChart");
    if (!chartCanvas) return;
    const ctx = chartCanvas.getContext("2d");
    if (AppState.chartInstance) {
        AppState.chartInstance.destroy();
    }
    AppState.chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: days,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        font: { family: 'Plus Jakarta Sans', size: 12, weight: 600 },
                        boxWidth: 14
                    }
                },
                tooltip: {
                    padding: 10,
                    bodyFont: { family: 'Plus Jakarta Sans' }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Available Units (ATP)' },
                    grid: { color: '#f1f5f9' }
                },
                x: {
                    grid: { color: '#f8fafc' }
                }
            }
        }
    });
}

// Product Catalog & Filter Controls
function initFilters() {
    const search = document.getElementById("prodSearchInput");
    const whFilter = document.getElementById("prodWarehouseFilter");
    const stFilter = document.getElementById("prodStatusFilter");

    const onFilterChange = () => renderCatalogTable();
    if (search) search.addEventListener("input", onFilterChange);
    if (whFilter) whFilter.addEventListener("change", onFilterChange);
    if (stFilter) stFilter.addEventListener("change", onFilterChange);
}

function renderCatalogTable() {
    const tbody = document.querySelector("#catalogTable tbody");
    if (!tbody || !AppState.data) return;
    tbody.innerHTML = "";

    const search = (document.getElementById("prodSearchInput")?.value || "").toLowerCase();
    const whFilter = document.getElementById("prodWarehouseFilter")?.value || "ALL";
    const stFilter = document.getElementById("prodStatusFilter")?.value || "ALL";

    const filtered = (AppState.data.products || []).filter(p => {
        const matchesSearch = p.product_name.toLowerCase().includes(search) || p.sku_id.toLowerCase().includes(search);
        const matchesWh = whFilter === "ALL" || p.wh_id === whFilter;
        const matchesSt = stFilter === "ALL" || p.status === stFilter;
        return matchesSearch && matchesWh && matchesSt;
    });

    filtered.forEach(p => {
        const row = document.createElement("tr");
        const statusBadge = p.status === "CRITICAL" ? '<span class="badge badge-critical">Critical Shortage</span>' :
                            p.status === "HIGH" ? '<span class="badge badge-warning">High Risk</span>' :
                            p.status === "MEDIUM" ? '<span class="badge badge-warning">Medium Risk</span>' :
                            '<span class="badge badge-success">Nominal</span>';

        row.innerHTML = `
            <td><strong>${p.wh_name}</strong></td>
            <td>${p.product_name}</td>
            <td class="mono">${p.sku_id}</td>
            <td>${p.physical_stock}</td>
            <td class="text-muted">${p.reserved_stock}</td>
            <td><strong class="text-primary">${p.available_stock}</strong></td>
            <td>${p.safety_buffer}</td>
            <td>${p.daily_demand}/day</td>
            <td><strong>${p.forecast_stockout_date || 'Safe'}</strong></td>
            <td>${statusBadge}</td>
        `;
        tbody.appendChild(row);
    });
}

// Cross Warehouse Matrix
function populateMatrixSkuDropdown() {
    const select = document.getElementById("matrixSkuSelect");
    if (!select || !AppState.data) return;
    
    // Get unique SKUs
    const skus = new Map();
    (AppState.data.products || []).forEach(p => {
        if (!skus.has(p.sku_id)) {
            skus.set(p.sku_id, p.product_name);
        }
    });

    select.innerHTML = "";
    skus.forEach((name, sku) => {
        const opt = document.createElement("option");
        opt.value = sku;
        opt.textContent = `${name} (${sku})`;
        if (sku === AppState.selectedMatrixSku) opt.selected = true;
        select.appendChild(opt);
    });

    select.addEventListener("change", (e) => {
        AppState.selectedMatrixSku = e.target.value;
        renderMatrixTable();
    });
}

function renderMatrixTable() {
    const tbody = document.querySelector("#matrixTable tbody");
    if (!tbody || !AppState.data) return;
    tbody.innerHTML = "";

    const sku = AppState.selectedMatrixSku;
    const items = (AppState.data.products || []).filter(p => p.sku_id === sku);

    items.forEach(p => {
        const row = document.createElement("tr");
        const surplus = Math.max(0, p.available_stock - (p.daily_demand * 7) - p.safety_buffer);
        const surplusBadge = surplus > 0 ? 
            `<strong class="text-success">+${surplus} units surplus</strong>` : 
            `<span class="text-critical">No Surplus (Protected)</span>`;

        row.innerHTML = `
            <td><strong>${p.wh_name}</strong></td>
            <td>${p.wh_location}</td>
            <td>${p.physical_stock}</td>
            <td class="text-muted">${p.reserved_stock}</td>
            <td><strong class="text-primary">${p.available_stock}</strong></td>
            <td>${p.safety_buffer}</td>
            <td>${surplusBadge}</td>
            <td>${p.transit_time_days || '1-2'} days</td>
            <td>₹${p.transfer_cost_per_unit || '12.00'}</td>
        `;
        tbody.appendChild(row);
    });
}

// SVG Map & Transfer Evaluator
function initMapNodes() {
    Object.keys(HubCoords).forEach(whId => {
        const node = document.getElementById(`node-${whId.replace("WH-", "")}`);
        if (node) {
            node.addEventListener("click", () => {
                selectWarehouse(whId);
                const btn = document.querySelector('.nav-btn[data-target="overview"]');
                if (btn) btn.click();
            });
        }
    });
}

function populateTransferDropdowns() {
    const srcSelect = document.getElementById("transferSourceSelect");
    const destSelect = document.getElementById("transferDestSelect");
    const skuSelect = document.getElementById("transferSkuSelect");
    if (!srcSelect || !destSelect || !skuSelect || !AppState.data) return;

    srcSelect.innerHTML = "";
    destSelect.innerHTML = "";
    skuSelect.innerHTML = "";

    const warehouses = AppState.data.warehouses || [];
    warehouses.forEach(w => {
        const optSrc = document.createElement("option");
        optSrc.value = w.wh_id;
        optSrc.textContent = w.name;
        if (w.wh_id === "WH-MUMBAI") optSrc.selected = true;
        srcSelect.appendChild(optSrc);

        const optDest = document.createElement("option");
        optDest.value = w.wh_id;
        optDest.textContent = w.name;
        if (w.wh_id === "WH-PUNE") optDest.selected = true;
        destSelect.appendChild(optDest);
    });

    const skus = new Map();
    (AppState.data.products || []).forEach(p => {
        if (!skus.has(p.sku_id)) skus.set(p.sku_id, p.product_name);
    });
    skus.forEach((name, sku) => {
        const opt = document.createElement("option");
        opt.value = sku;
        opt.textContent = `${name} (${sku})`;
        if (sku === "SKU-CHARGER-65W") opt.selected = true;
        skuSelect.appendChild(opt);
    });

    srcSelect.addEventListener("change", () => { updateMapVisuals(); evaluateTransferSafety(); });
    destSelect.addEventListener("change", () => { updateMapVisuals(); evaluateTransferSafety(); });
    skuSelect.addEventListener("change", () => { evaluateTransferSafety(); renderCompatibilitySection(); });
    document.getElementById("transferQtyInput")?.addEventListener("input", evaluateTransferSafety);

    updateMapVisuals();
}

function updateMapVisuals() {
    const srcId = document.getElementById("transferSourceSelect")?.value || "WH-MUMBAI";
    const destId = document.getElementById("transferDestSelect")?.value || "WH-PUNE";

    const srcCoord = HubCoords[srcId];
    const destCoord = HubCoords[destId];

    if (srcCoord && destCoord) {
        const line = document.getElementById("activeRouteLine");
        if (line) {
            line.setAttribute("x1", srcCoord.x);
            line.setAttribute("y1", srcCoord.y);
            line.setAttribute("x2", destCoord.x);
            line.setAttribute("y2", destCoord.y);
        }

        const anim = document.getElementById("cargoAnim");
        if (anim) {
            anim.setAttribute("path", `M ${srcCoord.x} ${srcCoord.y} L ${destCoord.x} ${destCoord.y}`);
        }

        // Highlight nodes
        Object.keys(HubCoords).forEach(whId => {
            const shortId = whId.replace("WH-", "");
            const circle = document.querySelector(`#node-${shortId} .node-circle`);
            if (circle) {
                circle.classList.remove("active-src", "active-dest");
                if (whId === srcId) circle.classList.add("active-src");
                if (whId === destId) circle.classList.add("active-dest");
            }
        });
    }
}

async function evaluateTransferSafety() {
    const src = document.getElementById("transferSourceSelect")?.value;
    const dest = document.getElementById("transferDestSelect")?.value;
    const sku = document.getElementById("transferSkuSelect")?.value;
    const qty = parseInt(document.getElementById("transferQtyInput")?.value || "20", 10);

    if (!src || !dest || !sku) return;

    try {
        const res = await fetch("/api/transfer/evaluate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ source_wh: src, dest_wh: dest, sku_id: sku, quantity: qty })
        });
        const evalData = await res.json();
        
        document.getElementById("valSrcAvail").textContent = `${evalData.source_available} units`;
        document.getElementById("valSrcAfter").textContent = `${evalData.source_after_transfer} units`;
        document.getElementById("valSrcDemand").textContent = `${evalData.source_7day_demand} units`;
        document.getElementById("valSrcSafety").textContent = `${evalData.source_safety_buffer} units`;
        document.getElementById("valTrCost").textContent = `₹${evalData.freight_cost.toFixed(2)}`;
        document.getElementById("valTrDays").textContent = `${evalData.transit_days} day(s)`;

        const summary = document.getElementById("protectionSummary");
        if (evalData.is_safe) {
            summary.innerHTML = `<span class="text-success"><i class="fa-solid fa-circle-check"></i> Safe: Source maintains sufficient buffer for next 7 days (Max Safe Surplus: ${evalData.max_safe_transfer} units)</span>`;
        } else {
            summary.innerHTML = `<span class="text-critical"><i class="fa-solid fa-triangle-exclamation"></i> Warning: Transferring ${qty} units breaches source 7-day demand buffer (Max Safe Surplus: ${evalData.max_safe_transfer} units)</span>`;
        }
    } catch (err) {
        console.error("Transfer evaluation error:", err);
    }
}

function initTransferForm() {
    const btnSim = document.getElementById("btnSimulateTransfer");
    const btnConfirm = document.getElementById("btnConfirmTransfer");

    if (btnSim) {
        btnSim.addEventListener("click", () => {
            evaluateTransferSafety();
            showToast("Transfer preview simulated successfully. Source safety buffer verified.", "info");
        });
    }

    if (btnConfirm) {
        btnConfirm.addEventListener("click", async () => {
            const src = document.getElementById("transferSourceSelect")?.value;
            const dest = document.getElementById("transferDestSelect")?.value;
            const sku = document.getElementById("transferSkuSelect")?.value;
            const qty = parseInt(document.getElementById("transferQtyInput")?.value || "20", 10);

            try {
                const res = await fetch("/api/transfer/confirm", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ source_wh: src, dest_wh: dest, sku_id: sku, quantity: qty })
                });
                const result = await res.json();
                if (result.success) {
                    showToast(`Transfer confirmed! Manifest #${result.manifest_id} registered.`, "success");
                    await fetchAppState();
                } else {
                    showToast(`Transfer failed: ${result.error}`, "error");
                }
            } catch (err) {
                showToast("Failed to confirm transfer: " + err.message, "error");
            }
        });
    }
}

function renderTransferLogs() {
    const tbody = document.querySelector("#transferLogsTable tbody");
    if (!tbody || !AppState.data) return;
    tbody.innerHTML = "";

    const logs = AppState.data.transfer_logs || [];
    if (logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color: var(--text-dim);">No operational transfer manifests registered yet</td></tr>`;
        return;
    }

    logs.forEach(log => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td class="mono"><strong>#${log.id}</strong></td>
            <td>${log.source}</td>
            <td>${log.dest}</td>
            <td>${log.product}</td>
            <td><strong>${log.quantity} units</strong></td>
            <td>₹${log.freight_cost.toFixed(2)}</td>
            <td>${log.expected_arrival}</td>
            <td><span class="badge badge-info">${log.status}</span></td>
            <td class="text-muted">${log.timestamp}</td>
        `;
        tbody.appendChild(row);
    });
}

// Component Compatibility Engine
function renderCompatibilitySection() {
    const sku = document.getElementById("transferSkuSelect")?.value || "SKU-CHARGER-65W";
    const comp = (AppState.data.compatibility || {})[sku];

    const approvedBox = document.getElementById("approvedSubsList");
    const rejectedBox = document.getElementById("rejectedSubsList");
    if (!approvedBox || !rejectedBox) return;

    if (!comp) {
        approvedBox.innerHTML = "<p class='text-muted'>No direct substitutes required for this product.</p>";
        rejectedBox.innerHTML = "<p class='text-muted'>No incompatible components listed.</p>";
        return;
    }

    approvedBox.innerHTML = "";
    if (comp.approved && comp.approved.length > 0) {
        comp.approved.forEach(sub => {
            const item = document.createElement("div");
            item.style.padding = "8px 12px";
            item.style.background = "var(--success-bg)";
            item.style.borderRadius = "var(--radius-sm)";
            item.style.marginBottom = "6px";
            item.style.border = "1px solid var(--success-border)";
            item.innerHTML = `<strong>${sub.name}</strong> <span class="mono">(${sub.sku_id})</span><br><small class="text-muted">${sub.reason}</small>`;
            approvedBox.appendChild(item);
        });
    } else {
        approvedBox.innerHTML = "<p class='text-muted'>No pre-approved direct substitute defined.</p>";
    }

    rejectedBox.innerHTML = "";
    if (comp.rejected && comp.rejected.length > 0) {
        comp.rejected.forEach(sub => {
            const item = document.createElement("div");
            item.style.padding = "8px 12px";
            item.style.background = "var(--critical-bg)";
            item.style.borderRadius = "var(--radius-sm)";
            item.style.marginBottom = "6px";
            item.style.border = "1px solid var(--critical-border)";
            item.innerHTML = `<strong>${sub.name}</strong> <span class="mono">(${sub.sku_id})</span><br><small class="text-muted"><strong>Reason:</strong> ${sub.reason}</small>`;
            rejectedBox.appendChild(item);
        });
    } else {
        rejectedBox.innerHTML = "<p class='text-muted'>No incompatible components recorded.</p>";
    }
}

// Deliveries & Delay Analysis
function renderDeliveries() {
    const tbody = document.querySelector("#deliveriesTable tbody");
    if (!tbody || !AppState.data) return;
    tbody.innerHTML = "";

    const deliveries = AppState.data.deliveries || [];
    deliveries.forEach(d => {
        const row = document.createElement("tr");
        const statusBadge = d.delay_days > 0 ? 
            `<span class="badge badge-critical"><i class="fa-solid fa-clock-rotate-left"></i> Delayed (+${d.delay_days}d)</span>` : 
            `<span class="badge badge-success">On Schedule</span>`;

        row.innerHTML = `
            <td class="mono"><strong>#${d.shipment_id}</strong></td>
            <td>${d.supplier}</td>
            <td>${d.product_name}</td>
            <td><strong>${d.dest_wh_name}</strong></td>
            <td>${d.quantity} units</td>
            <td>${d.expected_arrival}</td>
            <td class="${d.delay_days > 0 ? 'text-critical' : 'text-muted'}">${d.delay_days > 0 ? `+${d.delay_days} days` : '0 days'}</td>
            <td><strong>${d.actual_projected_arrival}</strong></td>
            <td>${statusBadge}</td>
        `;
        tbody.appendChild(row);
    });
}

function renderDelayAnalysis() {
    const box = document.getElementById("delayAnalysisBox");
    if (!box || !AppState.data) return;

    const analysis = AppState.data.delay_analysis || "All inbound supplier shipments are operating within normal tolerances.";
    box.innerHTML = `
        <div class="alert-banner alert-banner-warning" style="margin-bottom:0;">
            <div class="alert-icon"><i class="fa-solid fa-triangle-exclamation"></i></div>
            <div>${analysis}</div>
        </div>
    `;
}

// Scenario Planner
function initScenarioPlanner() {
    const btnApply = document.getElementById("btnApplySim");
    const btnReset = document.getElementById("btnResetSim");

    if (btnApply) {
        btnApply.addEventListener("click", async () => {
            const demandMult = parseFloat(document.getElementById("simDemandInput")?.value || "1.0");
            const delayDays = parseInt(document.getElementById("simDelayInput")?.value || "0", 10);
            const costMult = parseFloat(document.getElementById("simTransferCostInput")?.value || "1.0");

            try {
                const res = await fetch("/api/simulate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ demand_multiplier: demandMult, supplier_delay_days: delayDays, transfer_cost_multiplier: costMult })
                });
                const simComparison = await res.json();
                renderSimulationComparison(simComparison);
                showToast("Simulation shock applied successfully", "info");
            } catch (err) {
                showToast("Simulation error: " + err.message, "error");
            }
        });
    }

    if (btnReset) {
        btnReset.addEventListener("click", async () => {
            try {
                await fetch("/api/scenario/reset", { method: "POST" });
                document.getElementById("simDemandInput").value = "1.0";
                document.getElementById("simDelayInput").value = "0";
                document.getElementById("simTransferCostInput").value = "1.0";
                await fetchAppState();
                showToast("Restored baseline operations", "success");
            } catch (err) {
                showToast("Reset error: " + err.message, "error");
            }
        });
    }
}

function renderPresets() {
    const container = document.getElementById("presetButtons");
    if (!container || !AppState.data) return;
    container.innerHTML = "";

    const presets = AppState.data.presets || [];
    presets.forEach(p => {
        const card = document.createElement("div");
        card.className = "preset-btn-card";
        card.innerHTML = `
            <h4><i class="fa-solid fa-bolt"></i> ${p.title}</h4>
            <p>${p.description}</p>
        `;
        card.onclick = async () => {
            try {
                const res = await fetch("/api/scenario/preset", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ preset_id: p.id })
                });
                const simComparison = await res.json();
                renderSimulationComparison(simComparison);
                showToast(`Applied preset: ${p.title}`, "info");
            } catch (err) {
                showToast("Preset error: " + err.message, "error");
            }
        };
        container.appendChild(card);
    });
}

function renderSimulationComparison(simData) {
    const tbody = document.querySelector("#simComparisonTable tbody");
    if (!tbody || !simData) return;
    tbody.innerHTML = "";

    const kpiComp = simData.kpi_comparison || {};
    const rows = [
        { label: "At-Risk Monitored SKUs", key: "at_risk_skus", unit: "SKUs" },
        { label: "Critical Stockouts", key: "critical_skus", unit: "SKUs" },
        { label: "Threatened Customer Orders", key: "orders_threatened", unit: "orders" },
        { label: "Est. Disruption / Recovery Cost", key: "estimated_disruption_cost", unit: "₹", isCurrency: true },
        { label: "Feasible Recovery Actions", key: "feasible_recoveries", unit: "actions" }
    ];

    rows.forEach(r => {
        const item = kpiComp[r.key] || { baseline: "-", disrupted: "-", delta: 0 };
        const tr = document.createElement("tr");
        
        let baseStr = r.isCurrency ? `₹${item.baseline?.toLocaleString()}` : `${item.baseline} ${r.unit}`;
        let simStr = r.isCurrency ? `₹${item.disrupted?.toLocaleString()}` : `${item.disrupted} ${r.unit}`;
        let deltaStr = item.delta > 0 ? `+${item.delta}` : `${item.delta}`;
        if (r.isCurrency) deltaStr = `+₹${item.delta?.toLocaleString()}`;

        const deltaBadge = item.delta !== 0 ? `<span class="badge badge-warning">${deltaStr}</span>` : `<span class="badge badge-neutral">No Change</span>`;

        tr.innerHTML = `
            <td><strong>${r.label}</strong></td>
            <td>${baseStr}</td>
            <td><strong class="text-primary">${simStr}</strong></td>
            <td>${deltaBadge}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Decision Audit Logs
function renderDecisionHistory() {
    const container = document.getElementById("decisionHistoryList");
    if (!container || !AppState.data) return;
    container.innerHTML = "";

    const history = AppState.data.decision_history || [];
    if (history.length === 0) {
        container.innerHTML = "<p class='text-muted'>No shortage decisions triggered in current cycle.</p>";
        return;
    }

    history.forEach(item => {
        const card = document.createElement("div");
        card.className = "audit-card";
        card.innerHTML = `
            <div class="audit-header">
                <div>
                    <strong><i class="fa-solid fa-clipboard-check"></i> ${item.title}</strong>
                    <span class="mono text-muted" style="margin-left: 8px;">[${item.sku_id}]</span>
                </div>
                <span class="badge badge-success">${item.status}</span>
            </div>
            <div class="audit-body">
                <p><strong>Primary Recommended Action:</strong> ${item.action_summary}</p>
                <p><strong>Cost & Lead Time Reasoning:</strong> ${item.reasoning}</p>
                <p><strong>Rejection of Inferior Alternatives:</strong> <span class="text-muted">${item.rejection_notes}</span></p>
                <div style="font-size:0.75rem; color: var(--text-dim); margin-top:6px;">Audited at: ${item.timestamp} | Mathematical Model: Deterministic Cost-Minimization OR</div>
            </div>
        `;
        container.appendChild(card);
    });
}
