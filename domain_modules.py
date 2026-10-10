"""
Domain Estimation Modules for Maha-Infra AI:
    1. Building Construction & Renovation Estimator
    2. Water Supply, Drainage & Storage Estimator
    3. Site & Basic Infrastructure Facility Estimator
    4. AI Structural Concept & Capex Synthesizer ("Raw Idea of Structure")

Provides interactive forms, AI photo inspection, live metrics, CAD-style vector graphics,
itemized Bill of Quantities (BOQ), and statutory Maharashtra PWD cost calculations.
"""

from __future__ import annotations

import os
from pathlib import Path
import pandas as pd
import streamlit as st

from ai_module import (
    generate_structural_concept,
    analyze_domain_photos,
    ai_is_configured,
    get_api_key,
)
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
from docket_generator import render_docket_export_ui



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
# FRONT-END AI ENGINE STATUS (NO KEY EXPOSED)
# ============================================================

def render_ai_engine_status():
    """Render a safe AI engine status badge. Never reveals the API key."""
    is_active = ai_is_configured()

    if is_active:
        st.markdown("""
        <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 8px; padding: 6px 12px; display: inline-flex; align-items: center; gap: 8px; margin-bottom: 10px;">
            <span style="height: 8px; width: 8px; background: #10b981; border-radius: 50%; display: inline-block;"></span>
            <span style="font-size: 12px; font-weight: 700; color: #047857;">🟢 AI Vision Engine Active</span>
            <span style="font-size: 11px; color: #64748b;">• Cloud vision & multimodal defect inspection ready</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 8px; padding: 6px 12px; display: inline-flex; align-items: center; gap: 8px; margin-bottom: 10px;">
            <span style="height: 8px; width: 8px; background: #f59e0b; border-radius: 50%; display: inline-block;"></span>
            <span style="font-size: 12px; font-weight: 700; color: #b45309;">Offline Computer Vision Mode</span>
            <span style="font-size: 11px; color: #64748b;">• Free heuristic inspection (no API key required)</span>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# REUSABLE DOMAIN PHOTO INSPECTOR & DEFECT ANALYZER
# ============================================================

def render_domain_photo_inspector(
    domain_key: str,
    domain_label: str,
    on_apply_callback,
    photo_help: str = "Upload existing structure / site photographs (JPG, PNG) for automated defect detection."
):
    """Render automated photo defect analyzer for any civil engineering domain."""
    results_state_key = f"{domain_key}_ai_results"
    photos_state_key = f"{domain_key}_photos"

    if results_state_key not in st.session_state:
        st.session_state[results_state_key] = []
    if photos_state_key not in st.session_state:
        st.session_state[photos_state_key] = []

    with st.expander(f"📸 Step 1: AI Site Photo Inspection & Renovation Analyzer ({domain_label})", expanded=True):
        render_ai_engine_status()
        st.caption(photo_help)

        uploaded = st.file_uploader(
            f"Upload {domain_label} Photos",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key=f"{domain_key}_file_uploader",
        )

        note = st.text_input(
            "Site Location / Engineer's Field Notes (Optional)",
            placeholder="e.g., Old G+1 school building with wall dampness and cracked plaster in Ward 4",
            key=f"{domain_key}_note_input"
        )

        if uploaded:
            st.session_state[photos_state_key] = [
                {"name": f.name, "bytes": f.getvalue(), "mime": f.type or "image/jpeg"}
                for f in uploaded
            ]

        col_ai, col_cv = st.columns(2)
        run_ai = col_ai.button(
            "🤖 Run AI Vision Inspection",
            type="primary",
            use_container_width=True,
            key=f"{domain_key}_btn_ai"
        )
        run_cv = col_cv.button(
            "👁️ Run Offline Computer Vision (Free)",
            use_container_width=True,
            key=f"{domain_key}_btn_cv"
        )

        if run_ai or run_cv:
            if not st.session_state[photos_state_key]:
                st.warning("Please upload at least one photograph to analyze.")
            else:
                photos = st.session_state[photos_state_key]
                with st.spinner(f"Analyzing {len(photos)} site photo(s) using civil engineering defect models..."):
                    # Temporarily suppress AI API if offline button clicked
                    old_key = os.environ.get("OPENROUTER_API_KEY", "")
                    if run_cv:
                        os.environ["OPENROUTER_API_KEY"] = ""

                    results = analyze_domain_photos(domain_key, photos, note)

                    if run_cv:
                        os.environ["OPENROUTER_API_KEY"] = old_key

                    st.session_state[results_state_key] = results
                    st.toast("Site inspection completed! Identified civil defects and renovation scope.", icon="✅")
                    st.rerun()

        # Display results if available
        ai_res = st.session_state[results_state_key]
        if ai_res:
            st.markdown("#### 🔍 Structural & Defect Observations")
            for idx, item in enumerate(ai_res):
                p_name = item.get("name", f"Photo {idx+1}")
                res = item.get("result", {})
                rec_mode = res.get("recommended_mode", {})
                mode_val = rec_mode.get("value", "repair") if isinstance(rec_mode, dict) else str(rec_mode)
                mode_reason = rec_mode.get("reason", "") if isinstance(rec_mode, dict) else ""

                with st.expander(f"📷 Observation {idx+1}: {p_name} — Mode: {mode_val.upper()}", expanded=True):
                    col_m1, col_m2 = st.columns([1, 2])
                    with col_m1:
                        st.info(f"**Recommended Scope:** {mode_val.title()}\n\n**Condition:** {res.get('surface_condition', 'Inspected')}")
                        if mode_reason:
                            st.caption(f"Reason: {mode_reason}")
                    with col_m2:
                        defects = res.get("defects") or []
                        if defects:
                            st.markdown("**Defects Spotted:**")
                            st.dataframe(pd.DataFrame(defects), hide_index=True, use_container_width=True)

                        works = res.get("suggested_works") or []
                        if works:
                            st.markdown("**Recommended Maharashtra PWD Works:**")
                            for w in works:
                                w_title = w.get("work", "") if isinstance(w, dict) else str(w)
                                w_ch = f" (Ch: {', '.join(w.get('suggested_chapters', []))})" if isinstance(w, dict) and w.get("suggested_chapters") else ""
                                st.write(f"- **{w_title}**{w_ch}")

            # 1-Click Auto Apply Button
            if st.button(
                f"✨ Auto-Apply AI Findings to {domain_label} Parameters & BOQ",
                type="primary",
                use_container_width=True,
                key=f"{domain_key}_auto_apply_btn"
            ):
                on_apply_callback(ai_res)
                st.toast("AI recommendations auto-applied to project estimate!", icon="🚀")
                st.rerun()


# ============================================================
# 1. BUILDING ESTIMATION MODULE
# ============================================================

def render_building_module(df: pd.DataFrame):
    """Render full building estimation workflow with AI photo inspection."""
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
        <h2 style="color: #ffffff; margin: 8px 0 4px 0; font-size: 22px; font-weight: 800;">Building Construction & Renovation Estimator</h2>
        <p style="color: #94a3b8; margin: 0; font-size: 13px;">Itemized PWD SSR 2022-23 rates for Foundations, RCC Framing, Masonry, Finishing, and Services.</p>
    </div>
    """, unsafe_allow_html=True)

    # Callback for AI Auto Apply
    def apply_building_ai(results):
        has_renovation = any(
            r.get("result", {}).get("recommended_mode", {}).get("value") == "renovation"
            for r in results
        )
        if has_renovation:
            b.include_finishing = True
            b.include_doors_windows = True
            b.include_plumbing = True
            b.building_type = "Renovation / Rehabilitation of Existing Structure"
        st.session_state.b_est = generate_building_estimate(df, b)

    # Step 1: Photo Inspector
    render_domain_photo_inspector(
        domain_key="building",
        domain_label="Building Structure & Renovation",
        on_apply_callback=apply_building_ai,
        photo_help="Upload photographs of old or existing building (damaged plaster, damp walls, cracked beams) for automatic renovation scope."
    )

    st.markdown("#### 📐 Step 2: Dimensional Parameters & Structural Specifications")
    col1, col2 = st.columns(2)
    with col1:
        b_type = st.selectbox(
            "Building Classification",
            [
                "Residential Quarters (G+1)",
                "Commercial / Office Complex (G+3)",
                "School / Educational Facility (G+2)",
                "Hospital / Primary Health Center (G+1)",
                "Community Hall / Samaj Mandir",
                "Renovation / Rehabilitation of Existing Structure",
            ],
            index=0 if b.building_type not in ["Renovation / Rehabilitation of Existing Structure"] else 5,
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
    if st.button("🏗️ Calculate Building Cost & Generate Official BOQ", type="primary", use_container_width=True, key="btn_gen_building"):
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
    """Render water supply and sanitation estimation workflow with AI photo inspection."""
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
        <p style="color: #94a3b8; margin: 0; font-size: 13px;">Itemized PWD SSR rates for Distribution Pipelines, Reservoirs, Inspection Chambers, and Valves.</p>
    </div>
    """, unsafe_allow_html=True)

    # Callback for AI Auto Apply
    def apply_water_ai(results):
        w.network_length_m = max(w.network_length_m, 350.0)
        w.storage_tank_litres = max(w.storage_tank_litres, 5000.0)
        w.inspection_chambers_count = max(w.inspection_chambers_count, 4)
        w.fixtures_count = max(w.fixtures_count, 8)
        w.sewer_drain_length_m = max(w.sewer_drain_length_m, 60.0)
        st.session_state.w_est = generate_water_supply_estimate(df, w)

    # Step 1: Photo Inspector
    render_domain_photo_inspector(
        domain_key="water",
        domain_label="Water Pipeline & Sanitation Network",
        on_apply_callback=apply_water_ai,
        photo_help="Upload photographs of leaking pipelines, damaged valve chambers, corroded pipes, or water storage tanks."
    )

    st.markdown("#### 🚰 Step 2: Network Parameters & Storage Capacity")
    col1, col2 = st.columns(2)
    with col1:
        scheme = st.selectbox(
            "Water Supply Scheme Type",
            [
                "Distribution Pipeline & Fixtures",
                "Dedicated Pumping Main & Overhead Reservoir",
                "Internal Facility Plumbing & Drainage",
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
        tank_cap = st.number_input(
            "Water Storage Tank Capacity (Litres)",
            min_value=500.0,
            max_value=100000.0,
            value=float(w.storage_tank_litres),
            step=1000.0,
            key="w_tank_cap_input",
        )
        tank_type = st.selectbox(
            "Water Storage Reservoir Type",
            ["Elevated RCC / Masonry", "Ground Sump", "Triple-layer HDPE Tank"],
            index=0,
            key="w_tank_type_input",
        )
        valves = st.number_input("Distribution Taps / Sluice Valves (nos)", min_value=1, max_value=50, value=int(w.fixtures_count), step=1, key="w_valves_input")
        chambers = st.number_input("Brick Inspection Chambers / Manholes (nos)", min_value=1, max_value=50, value=int(w.inspection_chambers_count), step=1, key="w_chambers_input")
        sewer_len = st.number_input("Sewer / Drainage Line Length (m)", min_value=0.0, max_value=5000.0, value=float(w.sewer_drain_length_m), step=10.0, key="w_sewer_input")

    # Update state
    w.scheme_type = scheme
    w.network_length_m = pipe_len
    w.pipe_diameter_mm = pipe_dia
    w.pipe_material = pipe_mat
    w.storage_tank_litres = tank_cap
    w.storage_tank_type = tank_type
    w.fixtures_count = valves
    w.inspection_chambers_count = chambers
    w.sewer_drain_length_m = sewer_len

    # Live Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pipeline Length", f"{w.network_length_m:,.0f} m", f"Ø {w.pipe_diameter_mm} mm {w.pipe_material}")
    m2.metric("Trench Excavation", f"{w.trench_excavation_m3:,.1f} m³", "Trench depth ~0.9m")
    m3.metric("Water Reservoir", f"{w.storage_tank_litres:,.0f} L", f"{w.storage_tank_type.split()[0]}")
    m4.metric("Sanitary Appurtenances", f"{w.inspection_chambers_count + w.fixtures_count} Units", f"{w.inspection_chambers_count} chambers")

    # Interactive CAD Visualizer
    with st.expander("📐 Technical Pipeline Profile & Chamber Cross-Section", expanded=True):
        svg_code = render_water_supply_svg(w)
        st.markdown(svg_code, unsafe_allow_html=True)

    if st.button("🚰 Calculate Water Supply Cost & Generate Official BOQ", type="primary", use_container_width=True, key="btn_gen_water"):
        with st.spinner("Extracting sanitary schedule items from Maharashtra PWD SSR..."):
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
    """Render civil infrastructure facility estimation workflow with AI photo inspection."""
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

    # Callback for AI Auto Apply
    def apply_infra_ai(results):
        infra.compound_wall_length_m = max(infra.compound_wall_length_m, 120.0)
        infra.storm_drain_length_m = max(infra.storm_drain_length_m, 150.0)
        infra.internal_pavement_area_m2 = max(infra.internal_pavement_area_m2, 400.0)
        st.session_state.i_est = generate_infra_estimate(df, infra)

    # Step 1: Photo Inspector
    render_domain_photo_inspector(
        domain_key="infra",
        domain_label="Site & Boundary Infrastructure",
        on_apply_callback=apply_infra_ai,
        photo_help="Upload photographs of cracked boundary walls, sunken paver blocks, collapsed roadside drains, or damaged culverts."
    )

    st.markdown("#### 🧱 Step 2: Site Dimensions & Campus Specifications")
    col1, col2 = st.columns(2)
    with col1:
        cw_len = st.number_input("Compound Wall Length (m)", min_value=0.0, value=float(infra.compound_wall_length_m), step=10.0, key="i_cw_l")
        cw_h = st.number_input("Compound Wall Height (m)", min_value=1.0, max_value=4.0, value=float(infra.compound_wall_height_m), step=0.2, key="i_cw_h")
        sd_len = st.number_input("Storm Water Drain Length (m)", min_value=0.0, value=float(infra.storm_drain_length_m), step=10.0, key="i_sd_l")

    with col2:
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

    if st.button("🌐 Calculate Infrastructure Cost & Generate Official BOQ", type="primary", use_container_width=True, key="btn_gen_infra"):
        with st.spinner("Extracting infrastructure schedule items from PWD SSR..."):
            st.session_state.i_est = generate_infra_estimate(df, infra)
            st.rerun()

    # Estimate Display
    i_estimate = st.session_state.i_est
    if i_estimate and i_estimate.items:
        st.markdown("---")
        _render_boq_and_kpis(i_estimate, "infrastructure_estimate.csv", "i_est")


# ============================================================
# 4. AI STRUCTURAL CONCEPT & CAPEX SYNTHESIZER
# ============================================================

def render_concept_module(df: pd.DataFrame):
    """Render AI structural concept, IS 456 preliminary member sizing & material takeoffs."""
    if "s_concept" not in st.session_state:
        st.session_state.s_concept = None

    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); border: 1px solid rgba(129, 140, 248, 0.35); border-radius: 14px; padding: 18px 24px; margin-bottom: 20px;">
        <span style="background: rgba(129, 140, 248, 0.2); color: #c7d2fe; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 999px; border: 1px solid rgba(129, 140, 248, 0.4);">
            🧠 AI CHIEF STRUCTURAL ENGINEER WING
        </span>
        <h2 style="color: #ffffff; margin: 8px 0 4px 0; font-size: 22px; font-weight: 800;">AI Structural Concept & Preliminary Capex Synthesizer</h2>
        <p style="color: #94a3b8; margin: 0; font-size: 13px;">IS 456:2000 Member Sizing, Material Takeoffs (Cement, Steel, Aggregates), and Capital Expenditure Breakdown.</p>
    </div>
    """, unsafe_allow_html=True)

    render_ai_engine_status()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 🏛️ Structure Characteristics")
        title = st.text_input("Project / Scheme Title", value="Proposed Administrative Office Complex, Pune", key="sc_title")
        b_type = st.selectbox(
            "Structural Typology",
            [
                "Commercial Office Building (RCC Frame)",
                "Residential Apartment Building (RCC Frame)",
                "Hospital & Healthcare Facility",
                "Educational Institute / School",
                "Industrial Warehouse & PEB Shed",
                "Community Center & Multi-purpose Hall",
            ],
            index=0,
            key="sc_type",
        )
        sqft = st.number_input("Total Built-up Area (sq.ft)", min_value=500.0, max_value=250000.0, value=8000.0, step=500.0, key="sc_sqft")
        floors_t = st.selectbox("Elevation / Storey Configuration", ["G+1 (2 Storeys)", "G+2 (3 Storeys)", "G+3 (4 Storeys)", "G+4 (5 Storeys)", "G+6 (7 Storeys)"], index=2, key="sc_fl")

    with col2:
        st.markdown("##### 🌍 Geotechnical & Material Specifications")
        soil = st.selectbox(
            "Founding Soil Strata",
            ["Medium Hard Murrum (SBC 200 kN/m²)", "Hard Rock / Basalt (SBC 450 kN/m²)", "Black Cotton Soil (Expansive clay, SBC 100 kN/m²)", "Soft Clay / Waterlogged (SBC 80 kN/m²)"],
            index=0,
            key="sc_soil",
        )
        conc = st.selectbox("Preferred Concrete Grade", ["M-25", "M-20", "M-30", "M-35"], index=0, key="sc_conc")
        steel = st.selectbox("Rebar Grade", ["Fe 500D (TMT High Ductility)", "Fe 550D", "Fe 500"], index=0, key="sc_steel")
        notes = st.text_area("Special Architectural or Structural Requirements", placeholder="e.g. Earthquake zone III, column-free conference hall, basement parking", key="sc_notes")

    if st.button("⚡ Synthesize Structural Concept & Capex Breakdown", type="primary", use_container_width=True, key="btn_gen_concept"):
        # Extract integer floor count from selectbox text like "G+2 (3 Storeys)"
        import re
        _fl_match = re.search(r'\((\d+)\s*Storey', floors_t)
        _floors_int = int(_fl_match.group(1)) if _fl_match else 2

        with st.spinner("Executing IS 456 preliminary member sizing algorithms and material takeoffs..."):
            concept = generate_structural_concept(
                project_title=title,
                building_type=b_type,
                built_up_area_sqft=sqft,
                floors=_floors_int,
                soil_type=soil,
                special_requirements=notes,
            )
            st.session_state.s_concept = concept
            st.rerun()

    concept: StructuralConcept = st.session_state.s_concept
    if concept:
        st.markdown("---")
        st.markdown("### 📋 Preliminary Structural Takeoff & Member Sizing")

        # Summary Banner
        st.info(f"**Chief Structural Engineer's Synthesis:** {concept.raw_idea_summary}")

        # Member Sizing Cards
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Column Dimensions", concept.column_size.split(" with")[0], "IS 456 Minimum Sizing")
        c2.metric("Main Beam Size", concept.beam_size.split(" with")[0], "Span/12 Rule")
        c3.metric("Slab Thickness", concept.slab_thickness, "Span/28 Deflection Limit")
        c4.metric("Foundation Scheme", concept.foundation_concept.split(" (")[0], soil.split(" (")[0])

        # Material Takeoff Metrics
        st.markdown("##### 🧱 Raw Material Takeoff Estimate")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Design Concrete", f"{concept.estimated_concrete_m3:,.1f} m³", f"Grade {concept.concrete_grade}")
        m2.metric("TMT Rebar", f"{concept.estimated_steel_tonnes:,.1f} MT", f"Grade {concept.steel_grade}")
        m3.metric("Cement Required", f"{concept.estimated_cement_bags:,.0f} Bags", "~50 kg per bag")
        m4.metric("Sand (River/Crushed)", f"{concept.estimated_sand_brass:,.1f} Brass", "1 brass = 100 cu.ft")
        m5.metric("Coarse Aggregate", f"{concept.estimated_aggregate_brass:,.1f} Brass", "20mm & 10mm metal")

        # Interactive SVG Scheme
        with st.expander("📐 Technical Column Grid Layout & Load Transfer Diagram", expanded=True):
            svg_code = render_structural_concept_svg(concept)
            st.markdown(svg_code, unsafe_allow_html=True)

        # Capex Breakdown Table
        st.markdown("##### 💰 Capital Expenditure Breakdown (By Structural Domain)")
        capex_rows = [
            {"Stage": "1. Foundation & Substructure", "Scope": f"Excavation, PCC, {concept.foundation_concept}, Plinth beams", "Estimated Cost (₹)": concept.cost_substructure},
            {"Stage": "2. Superstructure RCC Framework", "Scope": f"Columns, beams, slabs ({concept.concrete_grade} + {concept.steel_grade})", "Estimated Cost (₹)": concept.cost_superstructure_rcc},
            {"Stage": "3. Masonry & Plastering", "Scope": "External 230mm AAC/fly ash walls, internal partitions, 2-coat plaster", "Estimated Cost (₹)": concept.cost_masonry_plaster},
            {"Stage": "4. Flooring, Doors & Finishing", "Scope": "Vitrified tiles, flush doors, anodized aluminium windows, painting", "Estimated Cost (₹)": concept.cost_finishing_flooring_doors},
            {"Stage": "5. Plumbing & Electrical MEP", "Scope": "Concealed conduits, copper wiring, CPVC water lines, sanitaryware", "Estimated Cost (₹)": concept.cost_plumbing_electrical},
        ]
        capex_df = pd.DataFrame(capex_rows)
        capex_df["Cost (Lakhs)"] = capex_df["Estimated Cost (₹)"].apply(lambda x: f"₹ {x/1e5:.2f} L")
        st.dataframe(capex_df[["Stage", "Scope", "Cost (Lakhs)"]], hide_index=True, use_container_width=True)

        # Statutory Project Grand Total
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
# REUSABLE BOQ & STATUTORY SUMMARY RENDERER (KEYERROR SAFE)
# ============================================================

def _render_boq_and_kpis(estimate: CostEstimate, export_filename: str, state_key: str):
    """Render statutory PWD cost cards and editable Bill of Quantities without KeyError."""
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

    table_rows = []
    for item in estimate.items:
        table_rows.append({
            "Remove": False,
            "ID": item.id,
            "Item No": item.item_no,
            "Chapter": item.chapter,
            "Description": item.description,
            "Unit": item.unit,
            "Rate (₹)": item.rate,
            "Quantity": item.quantity,
            "Amount (₹)": item.amount,
            "Note": item.calculation_note,
        })

    table_df = pd.DataFrame(table_rows)

    edited_table = st.data_editor(
        table_df,
        disabled=["ID", "Item No", "Chapter", "Description", "Unit", "Rate (₹)", "Amount (₹)", "Note"],
        column_config={
            "ID": None,  # Hide ID column completely
            "Remove": st.column_config.CheckboxColumn("Drop", default=False),
            "Quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, step=0.01),
            "Rate (₹)": st.column_config.NumberColumn("Rate (₹)", format="%.2f"),
            "Amount (₹)": st.column_config.NumberColumn("Amount (₹)", format="%.2f"),
        },
        hide_index=True,
        use_container_width=True,
        key=f"editor_{state_key}",
    )

    # Handle inline updates safely
    items_to_remove = set()
    updated_quantities = {}
    has_changes = False

    for _, r in edited_table.iterrows():
        raw_id = r.get("ID")
        if raw_id is None or pd.isna(raw_id):
            continue
        iid = int(raw_id)
        if bool(r.get("Remove", False)):
            items_to_remove.add(iid)
            has_changes = True
        else:
            new_q = float(r.get("Quantity", 0.0))
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

    # Official Government PWD Tender Docket & Printable PDF
    category_map = {
        "b_est": ("Building Construction & Renovation Work", "Building Construction Wing"),
        "w_est": ("Rural & Urban Water Supply Scheme", "Public Health Engineering Wing"),
        "inf_est": ("Basic Infrastructure & Area Development Work", "Infrastructure & Urban Works Wing"),
    }
    title, category = category_map.get(state_key, ("Infrastructure Civil Works", "General Civil Wing"))
    render_docket_export_ui(
        estimate=estimate,
        project_title=title,
        work_category=category,
        location="Maharashtra, India",
        key_suffix=state_key,
    )

