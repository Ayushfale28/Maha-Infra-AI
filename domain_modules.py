"""
Domain Estimation Modules for Maha-Infra AI:
    1. Building Construction Estimator
    2. Water Supply & Sanitation Estimator
    3. Site & Basic Infrastructure Estimator
    4. AI Structural Concept & Capex Ideator ("Raw Idea of Structure")

Provides interactive forms, live metrics, CAD-style vector graphics,
itemized Bill of Quantities (BOQ), and statutory PWD cost calculations.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ai_module import generate_structural_concept
from estimate_service import (
    generate_building_estimate,
    generate_water_supply_estimate,
    generate_infra_estimate,
    get_estimate_display_df,
    get_estimate_export_csv,
    remove_items_from_estimate,
    update_quantities_in_estimate,
)
from infra_visualizers import (
    render_building_structural_svg,
    render_water_supply_svg,
    render_structural_concept_svg,
)
from schemas import (
    CostEstimate,
    BuildingMeasurements,
    WaterSupplyMeasurements,
    InfraMeasurements,
    StructuralConcept,
)


def format_crore_lakh(amount: float) -> str:
    """Format total amount in Crores and Lakhs."""
    if amount is None or amount == 0:
        return "₹ 0.00 Lakh"
    abs_amt = abs(amount)
    sign = "-" if amount < 0 else ""
    if abs_amt >= 10_000_000:
        cr = abs_amt / 10_000_000
        return f"{sign}₹ {cr:.2f} Crore"
    else:
        lakh = abs_amt / 100_000
        return f"{sign}₹ {lakh:.2f} Lakh"


# ============================================================
# 1. BUILDING ESTIMATION MODULE
# ============================================================

def render_building_module(df: pd.DataFrame):
    """Render full building estimation workflow."""
    if "b_meas" not in st.session_state:
        st.session_state.b_meas = BuildingMeasurements()
    if "b_est" not in st.session_state:
        st.session_state.b_est = CostEstimate()

    b = st.session_state.b_meas

    st.markdown("""
    <div style="background: linear-gradient(135deg, #0c1524 0%, #172554 100%); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 14px; padding: 18px 24px; margin-bottom: 20px;">
        <span style="background: rgba(59, 130, 246, 0.2); color: #93c5fd; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 999px; border: 1px solid rgba(59, 130, 246, 0.4);">
            🏢 MAHARASHTRA PWD BUILDING WING
        </span>
        <h2 style="color: #ffffff; margin: 8px 0 4px 0; font-size: 22px; font-weight: 800;">Building Construction Cost Estimator</h2>
        <p style="color: #94a3b8; margin: 0; font-size: 13px;">Itemized PWD SSR 2022-23 rates for Foundations, RCC Framing, Masonry, Finishing, and Services.</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 📐 Dimensional Parameters")
        b_type = st.selectbox(
            "Building Classification",
            [
                "Residential Quarters (G+1)",
                "Commercial / Office Complex (G+3)",
                "School / Educational Facility (G+2)",
                "Hospital / Primary Health Center (G+1)",
                "Community Hall / Samaj Mandir",
            ],
            index=0,
            key="b_type_input",
        )
        plinth_sqm = st.number_input(
            "Plinth Area per Floor (m²)",
            min_value=20.0,
            max_value=5000.0,
            value=float(b.plinth_area_m2),
            step=10.0,
            help="1 sqm = 10.764 sq.ft",
            key="b_plinth_input",
        )
        floors = st.number_input(
            "Total Number of Storeys (including Ground)",
            min_value=1,
            max_value=12,
            value=int(b.floors),
            step=1,
            key="b_floors_input",
        )
        floor_h = st.number_input(
            "Floor-to-Floor Height (m)",
            min_value=2.4,
            max_value=5.0,
            value=float(b.floor_height_m),
            step=0.1,
            key="b_floor_h_input",
        )

    with col2:
        st.markdown("##### 🏗️ Structural & Scope Options")
        fnd_type = st.selectbox(
            "Foundation System",
            ["Isolated Footing", "Raft Foundation", "Pile Foundation"],
            index=0,
            key="b_fnd_input",
        )
        conc_grade = st.selectbox(
            "Design Concrete Grade",
            ["M-25", "M-20", "M-30"],
            index=0,
            key="b_conc_input",
        )
        inc_dw = st.checkbox("Include Doors & Windows (Teak / Glazed Shutters)", value=b.include_doors_windows, key="b_dw_input")
        inc_fin = st.checkbox("Include Finishing (Plaster, Vitrified Flooring, Painting)", value=b.include_finishing, key="b_fin_input")
        inc_plumb = st.checkbox("Include Internal Plumbing & Water Supply Fittings", value=b.include_plumbing, key="b_plumb_input")

    # Update state
    b.building_type = b_type
    b.plinth_area_m2 = plinth_sqm
    b.floors = floors
    b.floor_height_m = floor_h
    b.foundation_type = fnd_type
    b.concrete_grade = conc_grade
    b.include_doors_windows = inc_dw
    b.include_finishing = inc_fin
    b.include_plumbing = inc_plumb

    # Live Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Built-up Area", f"{b.total_built_up_area_m2:,.0f} m²", f"{b.total_built_up_area_sqft:,.0f} sq.ft")
    m2.metric("Approx RCC Concrete", f"{b.approx_concrete_m3:,.1f} m³", f"Grade {b.concrete_grade}")
    m3.metric("TMT Rebar (Fe 500)", f"{b.approx_steel_tonnes:,.2f} MT", f"{b.approx_steel_tonnes*1000:,.0f} kg")
    m4.metric("Brick Masonry Work", f"{b.approx_brickwork_m3:,.1f} m³", "230mm/115mm walls")

    # Interactive CAD Visualizer
    with st.expander("📐 Technical CAD Elevation & Structural Cross-Section", expanded=True):
        svg_code = render_building_structural_svg(b)
        st.markdown(svg_code, unsafe_allow_html=True)

    # Generate Estimate Button
    if st.button("🏗️ Generate Building Estimate & Bill of Quantities", type="primary", use_container_width=True, key="btn_gen_building"):
        with st.spinner("Accessing Maharashtra PWD Schedule of Rates (SSR 2022-23)..."):
            st.session_state.b_est = generate_building_estimate(df, b)
            st.rerun()

    # Estimate Display
    b_estimate = st.session_state.b_est
    if b_estimate and b_estimate.items:
        st.markdown("---")
        _render_boq_and_kpis(b_estimate, "building_cost_estimate.csv", "b_est")


# ============================================================
# 2. WATER SUPPLY & SANITATION MODULE
# ============================================================

def render_water_module(df: pd.DataFrame):
    """Render water supply and sanitation estimation workflow."""
    if "w_meas" not in st.session_state:
        st.session_state.w_meas = WaterSupplyMeasurements()
    if "w_est" not in st.session_state:
        st.session_state.w_est = CostEstimate()

    w = st.session_state.w_meas

    st.markdown("""
    <div style="background: linear-gradient(135deg, #022c22 0%, #064e3b 100%); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 14px; padding: 18px 24px; margin-bottom: 20px;">
        <span style="background: rgba(16, 185, 129, 0.2); color: #6ee7b7; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 999px; border: 1px solid rgba(16, 185, 129, 0.4);">
            🚰 PUBLIC HEALTH ENGINEERING (PHE) WING
        </span>
        <h2 style="color: #ffffff; margin: 8px 0 4px 0; font-size: 22px; font-weight: 800;">Water Supply, Storage & Sanitation Estimator</h2>
        <p style="color: #94a3b8; margin: 0; font-size: 13px;">Itemized PWD SSR rates for Distribution Pipelines, Reservoirs, Inspection Chambers, and Fittings.</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 🚰 Pipeline Network")
        scheme = st.selectbox(
            "Water Supply Scheme Type",
            [
                "Village / Layout Distribution Pipeline",
                "Internal Facility Plumbing & Drainage",
                "Dedicated Pumping Main & Overhead Reservoir",
            ],
            key="w_scheme_input",
        )
        pipe_len = st.number_input(
            "Distribution Pipeline Running Length (m)",
            min_value=10.0,
            max_value=20000.0,
            value=float(w.network_length_m),
            step=50.0,
            key="w_len_input",
        )
        pipe_dia = st.selectbox(
            "Pipe Nominal Diameter",
            [15, 20, 25, 32, 40, 50, 80, 100, 150],
            index=2,  # 25 mm
            key="w_dia_input",
        )
        pipe_mat = st.selectbox(
            "Pipe Material Specification",
            ["GI Heavy Grade", "Cast Iron", "PVC / UPVC", "Concrete NP"],
            index=0,
            key="w_mat_input",
        )

    with col2:
        st.markdown("##### 🏢 Storage & Sanitary Appurtenances")
        tank_litres = st.number_input(
            "Water Tank Capacity (Litres)",
            min_value=500.0,
            max_value=200000.0,
            value=float(w.storage_tank_litres),
            step=1000.0,
            key="w_tank_input",
        )
        tank_type = st.selectbox(
            "Storage Reservoir Type",
            ["Elevated RCC / Masonry", "Ground Sump", "Triple-layer HDPE"],
            index=0,
            key="w_ttype_input",
        )
        chambers = st.number_input(
            "Inspection Chambers (nos)",
            min_value=1,
            max_value=50,
            value=int(w.inspection_chambers_count),
            step=1,
            key="w_cham_input",
        )
        fixtures = st.number_input(
            "Sanitary Fixtures, Taps & Control Valves (nos)",
            min_value=1,
            max_value=100,
            value=int(w.fixtures_count),
            step=1,
            key="w_fix_input",
        )
        sewer_len = st.number_input(
            "Sewer / Drainage Line Length (m)",
            min_value=0.0,
            max_value=2000.0,
            value=float(w.sewer_drain_length_m),
            step=10.0,
            key="w_sewer_input",
        )

    # Update state
    w.scheme_type = scheme
    w.network_length_m = pipe_len
    w.pipe_diameter_mm = pipe_dia
    w.pipe_material = pipe_mat
    w.storage_tank_litres = tank_litres
    w.storage_tank_type = tank_type
    w.inspection_chambers_count = chambers
    w.fixtures_count = fixtures
    w.sewer_drain_length_m = sewer_len

    # Live Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pipe Run Length", f"{w.network_length_m:,.0f} m", f"{w.pipe_diameter_mm} mm {w.pipe_material}")
    m2.metric("Trench Excavation", f"{w.trench_excavation_m3:,.1f} m³", "Standard trench width & depth")
    m3.metric("Storage Reservoir", f"{w.storage_tank_litres:,.0f} L", f"{w.storage_tank_litres/1000:,.1f} m³")
    m4.metric("Chambers & Fixtures", f"{w.inspection_chambers_count + w.fixtures_count} nos", f"{w.inspection_chambers_count} chambers")

    # Interactive Visualizer
    with st.expander("📐 Technical Distribution & Hydraulic Layout Diagram", expanded=True):
        svg_code = render_water_supply_svg(w)
        st.markdown(svg_code, unsafe_allow_html=True)

    # Generate Button
    if st.button("🚰 Generate Water Supply & Sanitation BOQ", type="primary", use_container_width=True, key="btn_gen_water"):
        with st.spinner("Compiling water supply schedule items from PWD SSR..."):
            st.session_state.w_est = generate_water_supply_estimate(df, w)
            st.rerun()

    # Estimate Display
    w_estimate = st.session_state.w_est
    if w_estimate and w_estimate.items:
        st.markdown("---")
        _render_boq_and_kpis(w_estimate, "water_supply_estimate.csv", "w_est")


# ============================================================
# 3. SITE & BASIC INFRASTRUCTURE MODULE
# ============================================================

def render_infra_module(df: pd.DataFrame):
    """Render civil infrastructure facility estimation workflow."""
    if "i_meas" not in st.session_state:
        st.session_state.i_meas = InfraMeasurements()
    if "i_est" not in st.session_state:
        st.session_state.i_est = CostEstimate()

    infra = st.session_state.i_meas

    st.markdown("""
    <div style="background: linear-gradient(135deg, #2e1065 0%, #4c1d95 100%); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 14px; padding: 18px 24px; margin-bottom: 20px;">
        <span style="background: rgba(139, 92, 246, 0.2); color: #c4b5fd; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 999px; border: 1px solid rgba(139, 92, 246, 0.4);">
            🌐 BASIC INFRASTRUCTURE DEVELOPMENT WING
        </span>
        <h2 style="color: #ffffff; margin: 8px 0 4px 0; font-size: 22px; font-weight: 800;">Site Infrastructure Facility Estimator</h2>
        <p style="color: #94a3b8; margin: 0; font-size: 13px;">Compound Walls, Storm Drains, Walkways, Cross-Drainage Culverts & Street Furniture.</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 🧱 Boundary & Drainage")
        cw_len = st.number_input("Compound Wall Length (m)", min_value=0.0, value=float(infra.compound_wall_length_m), step=10.0, key="i_cw_l")
        cw_h = st.number_input("Compound Wall Height (m)", min_value=1.0, max_value=4.0, value=float(infra.compound_wall_height_m), step=0.2, key="i_cw_h")
        sd_len = st.number_input("Storm Water Drain Length (m)", min_value=0.0, value=float(infra.storm_drain_length_m), step=10.0, key="i_sd_l")

    with col2:
        st.markdown("##### 🚶 Pavement & Appurtenances")
        paver_area = st.number_input("Internal Pavement / Walkway Area (m²)", min_value=0.0, value=float(infra.internal_pavement_area_m2), step=25.0, key="i_pv_a")
        pave_type = st.selectbox("Pavement Specification", ["Interlocking Paver Blocks", "Concrete M-20", "Bituminous"], index=0, key="i_pv_t")
        culverts = st.number_input("Cross Drainage Culverts (nos)", min_value=0, max_value=20, value=int(infra.culverts_count), step=1, key="i_culv")
        furniture = st.number_input("Site Furniture & Signboards (nos)", min_value=0, max_value=50, value=int(infra.street_furniture_count), step=1, key="i_furn")

    # Update state
    infra.compound_wall_length_m = cw_len
    infra.compound_wall_height_m = cw_h
    infra.storm_drain_length_m = sd_len
    infra.internal_pavement_area_m2 = paver_area
    infra.pavement_type = pave_type
    infra.culverts_count = culverts
    infra.street_furniture_count = furniture

    # Live Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Compound Wall", f"{infra.compound_wall_area_m2:,.0f} m²", f"{infra.compound_wall_length_m:,.0f} m running length")
    m2.metric("Storm Drain", f"{infra.storm_drain_length_m:,.0f} m", f"{infra.storm_drain_volume_m3:,.1f} m³ capacity")
    m3.metric("Pavement Area", f"{infra.internal_pavement_area_m2:,.0f} m²", f"{infra.pavement_type}")
    m4.metric("Culverts & Signs", f"{infra.culverts_count + infra.street_furniture_count} nos", f"{infra.culverts_count} culverts")

    if st.button("🌐 Generate Infrastructure Facility BOQ", type="primary", use_container_width=True, key="btn_gen_infra"):
        with st.spinner("Extracting infrastructure schedule items from PWD SSR..."):
            st.session_state.i_est = generate_infra_estimate(df, infra)
            st.rerun()

    # Estimate Display
    i_estimate = st.session_state.i_est
    if i_estimate and i_estimate.items:
        st.markdown("---")
        _render_boq_and_kpis(i_estimate, "infrastructure_estimate.csv", "i_est")


# ============================================================
# 4. AI STRUCTURAL CONCEPT & CAPEX PLANNER MODULE
# ============================================================

def render_concept_module(df: pd.DataFrame):
    """Render AI Structural Concept & Capex Synthesizer."""
    if "s_concept" not in st.session_state:
        st.session_state.s_concept = None

    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 14px; padding: 18px 24px; margin-bottom: 20px;">
        <span style="background: rgba(99, 102, 241, 0.25); color: #c7d2fe; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 999px; border: 1px solid rgba(99, 102, 241, 0.4);">
            🧠 CHIEF STRUCTURAL ENGINEER AI
        </span>
        <h2 style="color: #ffffff; margin: 8px 0 4px 0; font-size: 22px; font-weight: 800;">AI Structural Concept & Capex Blueprint</h2>
        <p style="color: #94a3b8; margin: 0; font-size: 13px;">Translate architectural raw ideas into IS 456 preliminary member sizing, material volumes & project budget forecast.</p>
    </div>
    """, unsafe_allow_html=True)

    # Preset Quick Buttons
    st.markdown("###### ⚡ Quick PWD Project Presets")
    p1, p2, p3, p4 = st.columns(4)
    if p1.button("🏫 Primary School (G+2)", use_container_width=True):
        st.session_state["c_title"] = "Zilla Parishad Model Primary School"
        st.session_state["c_type"] = "Educational / School"
        st.session_state["c_area"] = 4500.0
        st.session_state["c_floors"] = 3
        st.session_state["c_soil"] = "Medium Hard Murum / Clay"
        st.session_state["c_notes"] = "6 classrooms, laboratory, staff room, and assembly verandah."
    if p2.button("🏥 Rural Hospital (G+1)", use_container_width=True):
        st.session_state["c_title"] = "Primary Health Center & Maternity Wing"
        st.session_state["c_type"] = "Healthcare / Hospital"
        st.session_state["c_area"] = 5500.0
        st.session_state["c_floors"] = 2
        st.session_state["c_soil"] = "Black Cotton / Swelling Clay"
        st.session_state["c_notes"] = "OPD, 10-bed ward, sterile OT, emergency ramp, and medical storage."
    if p3.button("🏢 Sub-Divisional Office", use_container_width=True):
        st.session_state["c_title"] = "PWD Sub-Divisional Office & Citizens Hub"
        st.session_state["c_type"] = "Government Office"
        st.session_state["c_area"] = 4000.0
        st.session_state["c_floors"] = 3
        st.session_state["c_soil"] = "Medium Hard Murum / Clay"
        st.session_state["c_notes"] = "Conference hall, executive chambers, server room, and record storage."
    if p4.button("🏠 PMAY Mass Housing (G+3)", use_container_width=True):
        st.session_state["c_title"] = "Affordable Housing EWS Block"
        st.session_state["c_type"] = "Residential Apartment"
        st.session_state["c_area"] = 8000.0
        st.session_state["c_floors"] = 4
        st.session_state["c_soil"] = "Hard Strata / Basalt Rock"
        st.session_state["c_notes"] = "16 units of 1-BHK, dual staircases, and rainwater harvesting."

    col1, col2 = st.columns([1.2, 1])
    with col1:
        p_title = st.text_input("Project Name / Title", value=st.session_state.get("c_title", "Proposed Community Facility"), key="c_p_title")
        p_notes = st.text_area(
            "Raw Idea of Structure & Special Requirements",
            value=st.session_state.get("c_notes", "G+2 multi-purpose public building with conference hall and ground floor parking."),
            placeholder="Describe your vision, room spans, functional needs, or site constraints...",
            key="c_p_notes",
            height=100,
        )

    with col2:
        b_type = st.selectbox("Occupancy / Building Type", ["Residential", "Educational / School", "Healthcare / Hospital", "Government Office", "Commercial"], index=1, key="c_b_type")
        c_area = st.number_input("Target Built-Up Area (sq.ft)", min_value=500.0, max_value=100000.0, value=float(st.session_state.get("c_area", 4000.0)), step=500.0, key="c_b_area")
        c_floors = st.number_input("Number of Storeys", min_value=1, max_value=8, value=int(st.session_state.get("c_floors", 3)), step=1, key="c_b_fl")
        c_soil = st.selectbox("Site Sub-Soil Condition", ["Medium Hard Murum / Clay", "Black Cotton / Swelling Clay", "Hard Strata / Basalt Rock", "Soft / Reclaimed Soil"], index=0, key="c_b_soil")

    if st.button("🧠 Synthesize Structural Concept & Capex Blueprint", type="primary", use_container_width=True):
        with st.spinner("Synthesizing IS 456 preliminary member dimensions, material takeoffs & capex breakdown..."):
            concept = generate_structural_concept(
                project_title=p_title,
                building_type=b_type,
                built_up_area_sqft=c_area,
                floors=c_floors,
                soil_type=c_soil,
                special_requirements=p_notes,
            )
            st.session_state.s_concept = concept
            st.rerun()

    concept = st.session_state.s_concept
    if concept:
        st.markdown("---")
        st.success(f"**Structural Concept Synthesized:** {concept.raw_idea_summary}")

        # Vector Graphic
        st.markdown(render_structural_concept_svg(concept), unsafe_allow_html=True)

        # Member Sizing & Materials Breakdown
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 📐 IS 456 Structural Sizing Breakdown")
            sizing_data = [
                {"Structural Element": "Column Grid Spacing", "Preliminary Dimension": concept.column_grid_spacing},
                {"Structural Element": "Column Cross-Section", "Preliminary Dimension": concept.column_size},
                {"Structural Element": "Main Longitudinal Beam", "Preliminary Dimension": concept.beam_size},
                {"Structural Element": "Two-Way Slab Panel", "Preliminary Dimension": concept.slab_thickness},
                {"Structural Element": "Foundation Concept", "Preliminary Dimension": concept.foundation_concept},
                {"Structural Element": "Concrete Grade", "Preliminary Dimension": concept.concrete_grade},
                {"Structural Element": "Reinforcement Grade", "Preliminary Dimension": concept.steel_grade},
            ]
            st.dataframe(pd.DataFrame(sizing_data), hide_index=True, width="stretch")

        with c2:
            st.markdown("#### 📦 Material Consumption Forecast")
            mat_data = [
                {"Material": "Ready-Mix / In-Situ Concrete", "Quantity": f"{concept.estimated_concrete_m3:,.1f} m³", "Standard Unit": "Cubic Metres (cum)"},
                {"Material": "TMT High-Ductility Rebar", "Quantity": f"{concept.estimated_steel_tonnes:,.2f} MT", "Standard Unit": "Metric Tonnes"},
                {"Material": "OPC / PPC Cement", "Quantity": f"{concept.estimated_cement_bags:,} bags", "Standard Unit": "50 kg bags"},
                {"Material": "River / VSI Crushed Sand", "Quantity": f"{concept.estimated_sand_brass:,.1f} Brass", "Standard Unit": "100 cu.ft (2.83 m³)"},
                {"Material": "Coarse Metal Aggregate", "Quantity": f"{concept.estimated_aggregate_brass:,.1f} Brass", "Standard Unit": "100 cu.ft (2.83 m³)"},
            ]
            st.dataframe(pd.DataFrame(mat_data), hide_index=True, width="stretch")

        # Capex Expenditure Table
        st.markdown("#### 💰 Capital Expenditure (Capex) Distribution")
        tot = max(1.0, concept.cost_total_estimated)
        capex_data = [
            {"Stage / Sub-Work": "1. Substructure (Excavation, Footings, Plinth)", "Amount (₹)": f"₹ {concept.cost_substructure:,.2f}", "Share": f"{(concept.cost_substructure/tot)*100:.1f}%"},
            {"Stage / Sub-Work": "2. Superstructure RCC Frame (Cols, Beams, Slabs)", "Amount (₹)": f"₹ {concept.cost_superstructure_rcc:,.2f}", "Share": f"{(concept.cost_superstructure_rcc/tot)*100:.1f}%"},
            {"Stage / Sub-Work": "3. Masonry & Plastering Work", "Amount (₹)": f"₹ {concept.cost_masonry_plaster:,.2f}", "Share": f"{(concept.cost_masonry_plaster/tot)*100:.1f}%"},
            {"Stage / Sub-Work": "4. Architectural Finishing, Tiles & Openings", "Amount (₹)": f"₹ {concept.cost_finishing_flooring_doors:,.2f}", "Share": f"{(concept.cost_finishing_flooring_doors/tot)*100:.1f}%"},
            {"Stage / Sub-Work": "5. MEP Services (Plumbing, Sanitary, Electrical)", "Amount (₹)": f"₹ {concept.cost_plumbing_electrical:,.2f}", "Share": f"{(concept.cost_plumbing_electrical/tot)*100:.1f}%"},
        ]
        st.dataframe(pd.DataFrame(capex_data), hide_index=True, width="stretch")

        # Statutory PWD Totals
        gst = concept.cost_total_estimated * 0.18
        cess = concept.cost_total_estimated * 0.01
        cont = concept.cost_total_estimated * 0.04
        grand = concept.cost_total_estimated + gst + cess + cont

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Civil Base Cost", format_crore_lakh(concept.cost_total_estimated))
        k2.metric("Statutory GST (18%)", format_crore_lakh(gst))
        k3.metric("BOCW Labour Cess (1%)", format_crore_lakh(cess))
        k4.metric("Grand Total Project Capex", format_crore_lakh(grand))

        # Engineering Guidelines
        with st.expander("🛡️ Chief Structural Engineer's Field Advisories & Soil Precautions", expanded=True):
            for g in concept.engineering_guidelines:
                st.write(f"- {g}")


# ============================================================
# REUSABLE BOQ & STATUTORY SUMMARY RENDERER
# ============================================================

def _render_boq_and_kpis(estimate: CostEstimate, export_filename: str, state_key: str):
    """Render statutory PWD cost cards and editable Bill of Quantities."""
    subtotal = estimate.subtotal
    gst = estimate.gst_amount
    cess = round(subtotal * 0.01, 2)
    cont = round(subtotal * 0.04, 2)
    grand_total = round(subtotal + gst + cess + cont, 2)

    # 4 Statutory Metric Cards
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Base Civil Cost", format_crore_lakh(subtotal), f"{len(estimate.items)} SSR Items")
    c2.metric("Statutory GST (18%)", format_crore_lakh(gst))
    c3.metric("Labour Cess (1%)", format_crore_lakh(cess))
    c4.metric("Grand Total (inc. Cess & Cont.)", format_crore_lakh(grand_total), f"₹ {grand_total:,.2f}")

    # Editable Itemized BOQ Table
    st.markdown("##### 📋 Official Bill of Quantities (BOQ)")
    table_df = get_estimate_display_df(estimate)
    table_df.insert(0, "Remove", False)

    edited_table = st.data_editor(
        table_df,
        disabled=["ID", "Item No", "Chapter", "Description", "Unit", "Rate (₹)", "Amount (₹)", "Note"],
        column_config={
            "Remove": st.column_config.CheckboxColumn("Drop", default=False),
            "Quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, step=1.0),
        },
        use_container_width=True,
        key=f"editor_{state_key}",
    )

    # Handle inline updates
    items_to_remove = set()
    updated_quantities = {}
    has_changes = False

    for _, r in edited_table.iterrows():
        iid = int(r["ID"])
        if bool(r["Remove"]):
            items_to_remove.add(iid)
            has_changes = True
        else:
            new_q = float(r["Quantity"])
            matching = next((it for it in estimate.items if it.id == iid), None)
            if matching and abs(matching.quantity - new_q) > 1e-4:
                updated_quantities[iid] = new_q
                has_changes = True

    if has_changes:
        cur_est = getattr(st.session_state, state_key)
        if items_to_remove:
            setattr(st.session_state, state_key, remove_items_from_estimate(cur_est, items_to_remove))
        if updated_quantities:
            setattr(st.session_state, state_key, update_quantities_in_estimate(cur_est, updated_quantities))
        st.rerun()

    # Download CSV
    csv_data = get_estimate_export_csv(estimate)
    if csv_data:
        st.download_button(
            "📥 Download Official Bill of Quantities (CSV)",
            data=csv_data,
            file_name=export_filename,
            mime="text/csv",
            use_container_width=True,
            key=f"down_{state_key}",
        )
