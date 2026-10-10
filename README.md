# 🏛️ महा-इन्फ्रा AI (Maha-Infra AI) — State Civil & Infrastructure Cost Portal

AI-powered multi-sector civil engineering and infrastructure estimation portal built for the **Public Works Department (PWD), Government of Maharashtra**. Compliant with **Maharashtra PWD Schedule of Rates (SSR 2022-23)** and Indian Standard Codes (**IS 456:2000, IRC:37, NBC**).

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Govt Portal](https://img.shields.io/badge/Maharashtra%20PWD-Official%20SSR%20Engine-orange?style=for-the-badge)

## ✨ Multi-Domain Estimation Suites

### 1. 🛣️ Roads & Highways Engineering
- **📸 AI Site Photo Analysis** — Multimodal vision analysis for pavement distress (alligator cracks, potholes, ravelling)
- **📐 3D Pavement Cross-Section** — Interactive isometric CAD visualization of pavement layers (GSB, WMM, DBM, BC, DLC, PQC)
- **📊 Automated BOQ Generation** — Intelligent SSR item selection & quantity calculation for repair and new road construction
- **💬 AI Chat Assistant** — Interactive civil engineering co-pilot with live project context

### 2. 🏢 Full Building Construction Estimator
- **Plinth Area & Storey Method** — Accurate estimates for Residential, Commercial, Schools, Hospitals ($G+N$ storeys)
- **Structural Frame Takeoffs** — Foundation excavation, RCC concrete ($M20/M25/M30$), Fe 500 TMT steel rebar, brick masonry
- **Architectural Finishing & Services** — Internal/external plaster, vitrified tile flooring, teak/glazed doors & windows, painting, plumbing
- **📐 Interactive Structural Frame Elevation** — Dynamic vector CAD cross-section showing column grid, beams, slabs, and footings

### 3. 🚰 Water Supply, Storage & Sanitation
- **Pipeline Distribution Schemes** — GI, Cast Iron, PVC/UPVC, and concrete pipes from $15\text{ mm}$ to $150\text{ mm}$
- **Water Storage Reservoirs** — Elevated RCC reservoirs, ground sumps, and triple-layer HDPE storage tanks
- **Inspection Chambers & Drainage** — Brick masonry chambers ($450\text{ mm}$), salt-glazed/concrete sewer lines, control valves, bib cocks
- **📐 Hydraulic Network Schematic** — Interactive vector flow diagram showing intake, distribution mains, valves, and drainage

### 4. 🌐 Site & Basic Infrastructure Facilities
- **Boundary & Enclosures** — R.C.C. & brick masonry compound walls with coping
- **Storm Water Drainage** — Open/box surface drainage channels and cross-drainage pipe culverts
- **Pedestrian & Internal Pavements** — Interlocking concrete paver blocks ($80\text{ mm}$), M-20 concrete roads, and bituminous walkways
- **Road Furniture & Signage** — Signboards, bollards, and kerb stones

### 5. 🧠 AI Structural Concept & Capex Ideator ("Raw Idea of Structure")
- **Conceptual Sizing from Plain Text** — Enter project vision or select 1-click PWD presets (School, Health Center, Office, Mass Housing)
- **IS 456 Preliminary Member Sizing** — Column grid spacing, column dimensions, beam depth, two-way slab thickness, concrete & steel grades
- **Material Takeoff Forecast** — Concrete volume ($\text{m}^3$), TMT steel rebar ($\text{MT}$), cement bags, river/crushed sand ($\text{Brass}$), coarse aggregate ($\text{Brass}$)
- **Capital Expenditure (Capex) Distribution** — Stage-wise cost split across Substructure, Superstructure, Masonry, Finishing, and MEP Services

---

## 💰 Statutory PWD Estimate & BOQ Calculations

Every module generates official PWD Bill of Quantities (BOQ) with full statutory cost markups:
- **Base Civil Subtotal** (Derived from 2,211 verified SSR items)
- **18.0% Goods and Services Tax (GST)**
- **1.0% BOCW Labour Welfare Cess**
- **4.0% Contingencies & Departmental Supervision Charges**
- **Grand Total Cost** displayed strictly in **₹, Lakhs, and Crores**
- **One-Click CSV Export** for official departmental reporting and NIT tendering

---

## 🛠️ Setup & Running Locally

```bash
# 1. Clone repository & install dependencies
pip install -r requirements.txt

# 2. Run the platform
streamlit run app.py
```

To run unit tests:
```bash
python -m unittest discover tests
```

---

## 📁 Project Architecture

```
├── app.py                 # Main Government Portal Streamlit UI
├── domain_modules.py      # Building, Water Supply, Infrastructure & AI Concept modules
├── infra_visualizers.py   # Vector CAD schematics (Building frame, Water network, Structural blueprint)
├── ai_module.py           # AI backend (OpenRouter LLM + IS 456 rule-based synthesis engine)
├── estimate_service.py    # Multi-domain estimation workflow coordinator
├── quantity_engine.py     # Deterministic civil quantity calculations
├── cost_engine.py         # Statutory cost calculation & BOQ engine
├── schemas.py             # Shared dataclasses (Building, Water, Infra, Structural Concept)
├── ssr_loader.py          # Maharashtra PWD SSR parser
├── ssr_selector.py        # Item candidate search & ranking
├── SSR_2022-23 (2).xlsx   # Maharashtra PWD Schedule of Rates (2,211 items)
└── tests/                 # Unit tests (35 passing tests)
```

## 👨‍💻 Author

**Kalash** — Built for Maharashtra Public Works Department (PWD) infrastructure

