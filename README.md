# 🛡️ StockShield AI — Enterprise Inventory Operations Cockpit
> **Intelligent Inventory Risk Prediction & Recovery Planner**  
> Problem Statement #8: Inventory Shortage Early-Warning & Substitution Planner

StockShield AI is a predictive stockout prevention engine and recovery decision planner designed for real-world retail networks and electronics distribution hubs across **4 regional warehouses (Mumbai, Pune, Chennai, and Delhi)**.

---

## 🚀 Quick Start: How to Run the Prototype

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch the Enterprise Web Application
```bash
python server.py
```
Or with uvicorn:
```bash
uvicorn server:app --reload --port 8000
```

### 3. Open in Browser
Open your browser and navigate to:  
👉 **`http://localhost:8000`**

### 4. Run Automated Test Suites
Verify all unit and integration test suites:
```bash
python tests/test_inventory.py
python tests/test_compatibility.py
python tests/test_optimization.py
python tests/test_simulation.py
```

---

## 🏗️ Architecture & Technology Stack

| Layer | Technology | Purpose & Value Proposition |
| :--- | :--- | :--- |
| **Frontend UI** | **Modern HTML5, CSS3, JavaScript (ES6+), Chart.js** | Enterprise-grade cockpit with horizontal navigation, dynamic 2x2 regional grid, interactive SVG logistics route map with animated cargo pulse, and real-time Chart.js stock trajectory curves. **No sidebars, no clunky templates, zero clutter.** |
| **Backend API** | **FastAPI & Python 3.13** | Ultra-low latency asynchronous REST endpoints serving live network state, simulation shocks, safe transfer evaluations, and audit export. |
| **Data Engine** | **Deterministic In-Memory State & JSON Repository** | Full inventory ledger with physical, reserved, available (ATP), and inbound shipment ledgers across 4 regional hubs and 8 electronic SKUs. |
| **Decision Engine** | **Deterministic Operations Research & Multi-Criteria Optimization** | Cost-minimization and constraint-satisfaction algorithms. Guarantees **100% auditability, zero AI hallucinations, and zero token costs**. |

---

## 🏢 The 4 Regional Warehouses & Product Dataset

- **Mumbai Warehouse (`WH-MUMBAI`)**: West Hub (Surplus source with 1-day transit to Pune).
- **Pune Warehouse (`WH-PUNE`)**: Central Hub (Facing impending stockout of 65W Fast Chargers due to supplier shipment delay).
- **Chennai Warehouse (`WH-CHENNAI`)**: South Hub (Maintains surplus cables and power banks; 2-day transit).
- **Delhi Warehouse (`WH-DELHI`)**: North Hub (Peripherals and keyboard/mouse distribution; 2-day transit).

### Monitored Electronics Catalog:
1. `SKU-CHARGER-65W`: 65W USB-C Fast Charger *(Critical shortage at Pune)*
2. `SKU-CHARGER-65W-PRO`: 65W USB-C GaN Charger Pro *(Approved compatible substitute)*
3. `SKU-CHARGER-18W`: 18W USB-A Charger *(Strictly rejected due to voltage mismatch)*
4. `SKU-MOUSE-WL`: Ergonomic Wireless Mouse
5. `SKU-KEYBOARD-BT`: Slim Bluetooth Keyboard
6. `SKU-POWERBANK-20K`: 20,000mAh PD Power Bank
7. `SKU-HEADPHONES-ANC`: Active Noise Cancelling Headphones
8. `SKU-CABLE-USBC`: Braided USB-C Cable (1.5m)

---

## 🌟 Six Core Application Modules

### 1. 🏢 Warehouse Overview & Early Shortage Radar
- Prominent **Early Shortage Warning Banner** identifying impending buffer breaches.
- **2x2 Regional Warehouse Cards** showing Available ATP, Physical Stock, Reserved Stock, at-risk SKUs, and earliest forecast stockout dates.
- Interactive **7-Day Projected Inventory Trajectory Chart** with Chart.js showing daily customer demand drawdowns and inbound shipment arrival impacts.

### 2. 📦 Stock & Products Catalog + Cross-Warehouse Matrix
- Real-time catalog with instant SKU search, warehouse filtering, and risk tier categorization.
- **Cross-Warehouse Product Matrix**: Side-by-side comparison of any component across Mumbai, Pune, Chennai, and Delhi showing safety stock, immediate surplus, transit time, and freight cost.

### 3. 🚚 Transfer & Substitution Planner (With Live Route Map)
- **Interactive SVG Logistics Route Map**: Visual network corridors connecting hubs with animated moving cargo pulse dots indicating active inter-hub stock transit.
- **Source Future Stock Protection**: Calculates $\text{Transferable Surplus} = \max(0, \text{Available} - \text{7-Day Planned Demand} - \text{Safety Buffer})$. Prevents transferring stock that would cause a shortage at the source hub.
- **Component Compatibility Engine**: Technical voltage, pin-out, and form-factor verification (approves 65W GaN Pro, rejects 18W USB-A).
- **Operational Transfer Manifests**: Records dispatched transfers with live status updates.

### 4. 🚢 Supplier Deliveries & Delay Root-Cause Analysis
- Full inbound PO tracking table displaying expected vs projected arrival dates.
- Root-cause delay assessment identifying supplier bottlenecks and port congestion.

### 5. 🎛️ Scenario Planner (Supply Disruption Stress-Testing)
- **One-Click Disruption Presets**:
  - *Supplier Port Delay (+5 Days)*
  - *Festival Demand Surge (+80%)*
  - *Interstate Freight Spike (+100%)*
  - *Compound Disruption Shock*
- Custom shock sliders and side-by-side **Baseline vs Disrupted Scenario Comparison Matrix**.

### 6. 📋 Decision History & Audit Trail
- Transparent cost and lead-time reasoning for every recommended action.
- Complete logs explaining why inferior alternatives (delayed delivery, invalid substitutes) were rejected.
- **One-click CSV Audit Log Download**.

---

## 🎯 Hackathon Presentation Pitch (3-Minute Winning Demo)

1. **Problem Hook (30s):**  
   *"Retail supply chains face localized stockouts even with aggregate inventory. On our Overview page, Pune is facing an imminent stockout of 65W Fast Chargers in 1-2 days because of a 4-day supplier delay from VoltTech."*
2. **Deterministic Intelligence & Source Protection (45s):**  
   *"Instead of costly emergency reorders or blindly shipping stock, StockShield AI analyzes our 4 hubs. Under 'Transfer & Substitution', notice Mumbai has 75 available units, but our engine protects Mumbai's next 7 days of customer demand and safety buffer (50 units surplus). It guarantees Mumbai will never stockout by helping Pune."*
3. **Live Logistics Visualization (45s):**  
   *"When we simulate and confirm the transfer, our live SVG Route Map highlights the Mumbai $\to$ Pune corridor with an in-transit cargo pulse and generates an operational transfer manifest."*
4. **Strict Compatibility & Auditability (60s):**  
   *"Our Compatibility Engine verifies that the 65W GaN Pro is a direct match, while rejecting the 18W charger due to voltage mismatch. In Scenario Planner, we can stress-test a 80% demand spike with one click. Everything is 100% deterministic and exportable to CSV."*
