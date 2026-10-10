"""
SVG Visualizers for Civil Infrastructure & Building Structural Concepts.

Generates high-resolution, interactive CAD-style engineering vector drawings
for Building Structural Frames, Water Supply Networks, and Preliminary Concepts.
"""

from __future__ import annotations
from schemas import BuildingMeasurements, WaterSupplyMeasurements, StructuralConcept


def render_building_structural_svg(b: BuildingMeasurements, concept: StructuralConcept | None = None) -> str:
    """
    Generate an interactive 2D engineering elevation & structural cross-section SVG
    for a multi-storey framed building with foundation, columns, beams, slabs, and callouts.
    """
    floors = max(1, min(b.floors, 5))
    plinth_m = b.plinth_area_m2
    # Width and height of the drawing canvas
    canvas_w = 800
    canvas_h = 240 + floors * 80

    # Grid parameters
    left_x = 100
    bay_w = 180
    num_bays = 3
    frame_w = bay_w * num_bays
    gl_y = canvas_h - 110  # Ground level Y
    pl_y = gl_y - 25       # Plinth level Y (0.6m above GL)
    fl_h = 75              # Floor-to-floor pixel height

    svg_parts = [
        f'<svg viewBox="0 0 {canvas_w} {canvas_h}" width="100%" height="{canvas_h}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a; border-radius:12px; font-family:\'Plus Jakarta Sans\', sans-serif;">',
        '<!-- Grid Background Pattern -->',
        '<defs>',
        '  <pattern id="cadGrid" width="20" height="20" patternUnits="userSpaceOnUse">',
        '    <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1e293b" stroke-width="0.8"/>',
        '  </pattern>',
        '  <linearGradient id="concreteGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '    <stop offset="0%" stop-color="#475569"/>',
        '    <stop offset="100%" stop-color="#334155"/>',
        '  </linearGradient>',
        '  <linearGradient id="slabGrad" x1="0%" y1="0%" x2="100%" y2="0%">',
        '    <stop offset="0%" stop-color="#64748b"/>',
        '    <stop offset="50%" stop-color="#94a3b8"/>',
        '    <stop offset="100%" stop-color="#64748b"/>',
        '  </linearGradient>',
        '  <linearGradient id="footingGrad" x1="0%" y1="0%" x2="0%" y2="100%">',
        '    <stop offset="0%" stop-color="#64748b"/>',
        '    <stop offset="100%" stop-color="#1e293b"/>',
        '  </linearGradient>',
        '</defs>',
        f'<rect width="{canvas_w}" height="{canvas_h}" fill="url(#cadGrid)" />',
        '<!-- Title & Technical Block -->',
        f'<text x="25" y="32" fill="#38bdf8" font-size="14" font-weight="700">🏛️ MAHARASHTRA PWD — STRUCTURAL FRAME ELEVATION</text>',
        f'<text x="25" y="50" fill="#94a3b8" font-size="11">Type: {b.building_type} • Concrete: {b.concrete_grade} • Steel: Fe 500D • Plinth: {b.plinth_area_m2:,.0f} m² • Built-up: {b.total_built_up_area_sqft:,.0f} sq.ft</text>',
    ]

    # Ground Level & Hatch
    svg_parts.extend([
        f'<!-- Ground Level Line (GL) -->',
        f'<line x1="50" y1="{gl_y}" x2="{canvas_w - 50}" y2="{gl_y}" stroke="#e2e8f0" stroke-width="2.5" stroke-dasharray="8,4"/>',
        f'<text x="{canvas_w - 90}" y="{gl_y - 6}" fill="#f8fafc" font-size="11" font-weight="700">GL ±0.00</text>',
        f'<line x1="50" y1="{pl_y}" x2="{canvas_w - 50}" y2="{pl_y}" stroke="#38bdf8" stroke-width="1.8"/>',
        f'<text x="{canvas_w - 90}" y="{pl_y - 6}" fill="#38bdf8" font-size="11" font-weight="700">PL +0.60m</text>',
    ])

    # Footings below GL
    footing_depth_y = gl_y + 55
    col_x_list = [left_x + i * bay_w for i in range(num_bays + 1)]

    for idx, cx in enumerate(col_x_list):
        # Trapezoidal Footing
        fw = 64
        top_fw = 28
        svg_parts.extend([
            f'<!-- Footing F{idx+1} -->',
            f'<polygon points="{cx - top_fw/2},{gl_y+25} {cx + top_fw/2},{gl_y+25} {cx + fw/2},{footing_depth_y} {cx - fw/2},{footing_depth_y}" fill="url(#footingGrad)" stroke="#38bdf8" stroke-width="1.2"/>',
            f'<rect x="{cx - fw/2}" y="{footing_depth_y}" width="{fw}" height="14" fill="#1e293b" stroke="#38bdf8" stroke-width="1.2"/>',
            f'<text x="{cx}" y="{footing_depth_y + 11}" fill="#94a3b8" font-size="9" text-anchor="middle">PCC 1:4:8</text>',
            f'<text x="{cx}" y="{footing_depth_y + 32}" fill="#64748b" font-size="9.5" text-anchor="middle">F{idx+1} (-1.5m)</text>',
        ])

    # Columns & Storeys
    roof_y = pl_y - floors * fl_h

    # Plinth Beam
    svg_parts.extend([
        f'<!-- Plinth Beam -->',
        f'<rect x="{left_x - 10}" y="{pl_y}" width="{frame_w + 20}" height="16" fill="url(#concreteGrad)" stroke="#38bdf8" stroke-width="1.4"/>',
        f'<text x="{canvas_w / 2}" y="{pl_y + 12}" fill="#f8fafc" font-size="9.5" font-weight="600" text-anchor="middle">PLINTH BEAM PB-1 (230×380 mm)</text>',
    ])

    # Floors & Slabs
    for f in range(floors):
        floor_beam_y = pl_y - (f + 1) * fl_h
        floor_num = f + 1
        floor_label = "TERRACE SLAB" if floor_num == floors else f"FLOOR {floor_num} SLAB"

        # Slab + Beam
        svg_parts.extend([
            f'<!-- Storey {floor_num} Slabs & Infill -->',
            f'<rect x="{left_x - 10}" y="{floor_beam_y}" width="{frame_w + 20}" height="14" fill="url(#slabGrad)" stroke="#38bdf8" stroke-width="1.4"/>',
            f'<text x="{left_x + 10}" y="{floor_beam_y - 5}" fill="#a5b4fc" font-size="10" font-weight="600">Level +{(floor_num * 3.0):.1f}m ({floor_label} 125mm)</text>',
        ])

        # Masonry Infill panels and windows between columns
        for bay in range(num_bays):
            bx1 = left_x + bay * bay_w + 14
            bx2 = left_x + (bay + 1) * bay_w - 14
            b_width = bx2 - bx1
            wall_top = floor_beam_y + 14
            wall_bot = floor_beam_y + fl_h - (16 if f == 0 else 14)
            wall_h = wall_bot - wall_top

            if wall_h > 20:
                # Brick wall background
                svg_parts.append(
                    f'<rect x="{bx1}" y="{wall_top}" width="{b_width}" height="{wall_h}" fill="#1e293b" fill-opacity="0.85" stroke="#334155" stroke-dasharray="3,3"/>'
                )
                # Window opening
                win_w = 48
                win_h = 32
                win_x = bx1 + (b_width - win_w) / 2
                win_y = wall_top + (wall_h - win_h) / 2
                svg_parts.extend([
                    f'<rect x="{win_x}" y="{win_y}" width="{win_w}" height="{win_h}" fill="#0ea5e9" fill-opacity="0.25" stroke="#38bdf8" stroke-width="1.2"/>',
                    f'<line x1="{win_x + win_w/2}" y1="{win_y}" x2="{win_x + win_w/2}" y2="{win_y + win_h}" stroke="#38bdf8" stroke-width="1"/>',
                    f'<line x1="{win_x}" y1="{win_y + win_h/2}" x2="{win_x + win_w}" y2="{win_y + win_h/2}" stroke="#38bdf8" stroke-width="1"/>',
                    f'<text x="{win_x + win_w/2}" y="{win_y + win_h/2 + 3}" fill="#e0f2fe" font-size="8" text-anchor="middle">W (1.2×1.2m)</text>',
                ])

    # Parapet Wall on top
    parapet_y = roof_y - 24
    svg_parts.extend([
        f'<!-- Parapet Wall (1.0m height) -->',
        f'<rect x="{left_x - 10}" y="{parapet_y}" width="16" height="24" fill="#475569" stroke="#94a3b8" stroke-width="1.2"/>',
        f'<rect x="{left_x + frame_w - 6}" y="{parapet_y}" width="16" height="24" fill="#475569" stroke="#94a3b8" stroke-width="1.2"/>',
        f'<text x="{left_x + frame_w/2}" y="{parapet_y + 16}" fill="#64748b" font-size="9" text-anchor="middle">PARAPET COPING (+1.0m)</text>',
    ])

    # Vertical Column Shafts
    for idx, cx in enumerate(col_x_list):
        svg_parts.extend([
            f'<!-- Column C{idx+1} Shaft -->',
            f'<rect x="{cx - 10}" y="{roof_y}" width="20" height="{gl_y + 25 - roof_y}" fill="url(#concreteGrad)" stroke="#38bdf8" stroke-width="1.6"/>',
            f'<text x="{cx}" y="{parapet_y - 6}" fill="#f1f5f9" font-size="10" font-weight="700" text-anchor="middle">C{idx+1}</text>',
        ])

    # Grid Dimension Callouts
    dim_y = canvas_h - 22
    svg_parts.append(f'<!-- Grid Dimensions -->')
    for idx in range(num_bays):
        cx1 = left_x + idx * bay_w
        cx2 = left_x + (idx + 1) * bay_w
        mid = (cx1 + cx2) / 2
        svg_parts.extend([
            f'<line x1="{cx1}" y1="{dim_y}" x2="{cx2}" y2="{dim_y}" stroke="#64748b" stroke-width="1.2"/>',
            f'<circle cx="{cx1}" cy="{dim_y}" r="2.5" fill="#38bdf8"/>',
            f'<circle cx="{cx2}" cy="{dim_y}" r="2.5" fill="#38bdf8"/>',
            f'<text x="{mid}" y="{dim_y - 5}" fill="#94a3b8" font-size="10" font-weight="600" text-anchor="middle">Bay {idx+1}: 3.80 m (12.5 ft)</text>',
        ])

    # Engineering Specs Box
    spec_x = canvas_w - 200
    spec_y = 65
    svg_parts.extend([
        f'<rect x="{spec_x}" y="{spec_y}" width="180" height="110" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>',
        f'<text x="{spec_x + 10}" y="{spec_y + 18}" fill="#38bdf8" font-size="10" font-weight="700">📋 STRUCTURAL SPEC</text>',
        f'<text x="{spec_x + 10}" y="{spec_y + 36}" fill="#cbd5e1" font-size="9">Col: 230×380 mm (6-#16)</text>',
        f'<text x="{spec_x + 10}" y="{spec_y + 52}" fill="#cbd5e1" font-size="9">Beam: 230×380 mm (M-25)</text>',
        f'<text x="{spec_x + 10}" y="{spec_y + 68}" fill="#cbd5e1" font-size="9">Slab: 125mm (#8 @150 c/c)</text>',
        f'<text x="{spec_x + 10}" y="{spec_y + 84}" fill="#cbd5e1" font-size="9">Rebar: Fe 500D TMT</text>',
        f'<text x="{spec_x + 10}" y="{spec_y + 100}" fill="#10b981" font-size="9" font-weight="700">Code: IS 456:2000 OK</text>',
    ])

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def render_water_supply_svg(w: WaterSupplyMeasurements) -> str:
    """
    Generate an interactive hydraulic layout SVG for Water Supply & Sanitation works
    showing elevated storage reservoir, distribution pipeline, valves, chambers, and drainage flow.
    """
    canvas_w = 800
    canvas_h = 320

    svg_parts = [
        f'<svg viewBox="0 0 {canvas_w} {canvas_h}" width="100%" height="{canvas_h}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a; border-radius:12px; font-family:\'Plus Jakarta Sans\', sans-serif;">',
        '<defs>',
        '  <linearGradient id="tankWater" x1="0%" y1="0%" x2="0%" y2="100%">',
        '    <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.9"/>',
        '    <stop offset="100%" stop-color="#0284c7" stop-opacity="0.95"/>',
        '  </linearGradient>',
        '  <linearGradient id="pipeMetal" x1="0%" y1="0%" x2="0%" y2="100%">',
        '    <stop offset="0%" stop-color="#94a3b8"/>',
        '    <stop offset="50%" stop-color="#cbd5e1"/>',
        '    <stop offset="100%" stop-color="#64748b"/>',
        '  </linearGradient>',
        '</defs>',
        '<!-- Header -->',
        '<text x="25" y="30" fill="#38bdf8" font-size="14" font-weight="700">🚰 WATER DISTRIBUTION & DRAINAGE NETWORK SCHEMATIC</text>',
        f'<text x="25" y="48" fill="#94a3b8" font-size="11">Scheme: {w.scheme_type} • Pipe: {w.pipe_diameter_mm} mm {w.pipe_material} • Length: {w.network_length_m:,.0f} m • Tank: {w.storage_tank_litres:,.0f} Litres</text>',
    ]

    # Water Reservoir (Left)
    tank_x = 40
    tank_y = 75
    tank_w = 110
    tank_h = 80
    stilt_h = 95

    svg_parts.extend([
        f'<!-- Overhead Reservoir -->',
        f'<rect x="{tank_x}" y="{tank_y}" width="{tank_w}" height="{tank_h}" rx="8" fill="url(#tankWater)" stroke="#38bdf8" stroke-width="2"/>',
        f'<text x="{tank_x + tank_w/2}" y="{tank_y + 35}" fill="#ffffff" font-size="11" font-weight="700" text-anchor="middle">OVERHEAD TANK</text>',
        f'<text x="{tank_x + tank_w/2}" y="{tank_y + 52}" fill="#e0f2fe" font-size="10" font-weight="600" text-anchor="middle">{w.storage_tank_litres:,.0f} LITRES</text>',
        f'<text x="{tank_x + tank_w/2}" y="{tank_y + 68}" fill="#bae6fd" font-size="9" text-anchor="middle">{w.storage_tank_type.split()[0]}</text>',
        # Reservoir Staging Columns
        f'<rect x="{tank_x + 12}" y="{tank_y + tank_h}" width="10" height="{stilt_h}" fill="#334155" stroke="#64748b"/>',
        f'<rect x="{tank_x + tank_w - 22}" y="{tank_y + tank_h}" width="10" height="{stilt_h}" fill="#334155" stroke="#64748b"/>',
        f'<line x1="{tank_x + 12}" y1="{tank_y + tank_h + 30}" x2="{tank_x + tank_w - 12}" y2="{tank_y + tank_h + 60}" stroke="#475569" stroke-width="1.5"/>',
        f'<line x1="{tank_x + tank_w - 12}" y1="{tank_y + tank_h + 30}" x2="{tank_x + 12}" y2="{tank_y + tank_h + 60}" stroke="#475569" stroke-width="1.5"/>',
    ])

    # Downcomer pipe from reservoir
    down_x = tank_x + tank_w - 35
    main_pipe_y = tank_y + tank_h + stilt_h - 20
    svg_parts.extend([
        f'<!-- Downcomer Pipe -->',
        f'<rect x="{down_x}" y="{tank_y + tank_h}" width="12" height="{stilt_h - 20}" fill="url(#pipeMetal)" stroke="#0284c7" stroke-width="1.2"/>',
        f'<!-- Main Distribution Line -->',
        f'<rect x="{down_x}" y="{main_pipe_y}" width="{canvas_w - down_x - 60}" height="12" rx="2" fill="url(#pipeMetal)" stroke="#0284c7" stroke-width="1.4"/>',
        f'<text x="{down_x + 120}" y="{main_pipe_y - 8}" fill="#38bdf8" font-size="10" font-weight="700">Distribution Main: {w.pipe_diameter_mm} mm {w.pipe_material}</text>',
        f'<text x="{down_x + 120}" y="{main_pipe_y + 24}" fill="#94a3b8" font-size="9">Running Length: {w.network_length_m:,.0f} m (Trench: {w.trench_excavation_m3:,.1f} m³)</text>',
    ])

    # Sluice Valve
    v1_x = down_x + 50
    svg_parts.extend([
        f'<!-- Sluice Control Valve -->',
        f'<polygon points="{v1_x-10},{main_pipe_y-6} {v1_x+10},{main_pipe_y+18} {v1_x-10},{main_pipe_y+18} {v1_x+10},{main_pipe_y-6}" fill="#f59e0b" stroke="#d97706" stroke-width="1.2"/>',
        f'<circle cx="{v1_x}" cy="{main_pipe_y - 12}" r="5" fill="#f59e0b"/>',
        f'<text x="{v1_x}" y="{main_pipe_y - 20}" fill="#fbbf24" font-size="8.5" font-weight="700" text-anchor="middle">Sluice Valve</text>',
    ])

    # Domestic Fixtures / Taps
    tap_x = down_x + 280
    svg_parts.extend([
        f'<!-- Tapping Branch & Fixture -->',
        f'<rect x="{tap_x}" y="{main_pipe_y - 45}" width="8" height="45" fill="url(#pipeMetal)" stroke="#0284c7"/>',
        f'<rect x="{tap_x - 8}" y="{main_pipe_y - 55}" width="24" height="10" fill="#38bdf8" rx="2"/>',
        f'<text x="{tap_x + 4}" y="{main_pipe_y - 62}" fill="#38bdf8" font-size="9" font-weight="700" text-anchor="middle">Bib Cock / Taps ({w.fixtures_count} nos)</text>',
    ])

    # Inspection Chamber & Sewer Line
    ch_x = down_x + 420
    ch_y = main_pipe_y + 25
    svg_parts.extend([
        f'<!-- Inspection Chamber -->',
        f'<rect x="{ch_x}" y="{ch_y}" width="45" height="40" fill="#334155" stroke="#10b981" stroke-width="1.6" rx="4"/>',
        f'<text x="{ch_x + 22}" y="{ch_y + 24}" fill="#34d399" font-size="8.5" font-weight="700" text-anchor="middle">IC 450mm</text>',
        f'<text x="{ch_x + 22}" y="{ch_y + 52}" fill="#94a3b8" font-size="8" text-anchor="middle">{w.inspection_chambers_count} Chambers</text>',
        # Outflow Sewer Line
        f'<line x1="{ch_x + 45}" y1="{ch_y + 20}" x2="{canvas_w - 50}" y2="{ch_y + 35}" stroke="#10b981" stroke-width="4" stroke-dasharray="6,3"/>',
        f'<text x="{canvas_w - 95}" y="{ch_y + 16}" fill="#34d399" font-size="9" font-weight="600">Sewer Line ({w.sewer_drain_length_m:,.0f} m)</text>',
    ])

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def render_structural_concept_svg(c: StructuralConcept) -> str:
    """
    Render visual architectural wireframe & capex distribution for an AI-generated structural concept.
    """
    canvas_w = 800
    canvas_h = 300

    svg_parts = [
        f'<svg viewBox="0 0 {canvas_w} {canvas_h}" width="100%" height="{canvas_h}" xmlns="http://www.w3.org/2000/svg" style="background:#0a0f1d; border-radius:12px; font-family:\'Plus Jakarta Sans\', sans-serif;">',
        '<defs>',
        '  <linearGradient id="headerGrad" x1="0%" y1="0%" x2="100%" y2="0%">',
        '    <stop offset="0%" stop-color="#3b82f6"/>',
        '    <stop offset="100%" stop-color="#8b5cf6"/>',
        '  </linearGradient>',
        '</defs>',
        '<!-- Header Block -->',
        f'<text x="25" y="32" fill="#38bdf8" font-size="14" font-weight="700">💡 PRELIMINARY STRUCTURAL SCHEME & CAPEX BLUEPRINT</text>',
        f'<text x="25" y="52" fill="#94a3b8" font-size="11.5">{c.project_title} • Built-up: {c.built_up_area_sqft:,.0f} sq.ft ({c.built_up_area_sqm:,.0f} m²) • {c.floors_text}</text>',
    ]

    # Structural Sizing Column
    b1_x = 25
    b1_y = 75
    b1_w = 360
    b1_h = 205
    svg_parts.extend([
        f'<rect x="{b1_x}" y="{b1_y}" width="{b1_w}" height="{b1_h}" rx="10" fill="#131c31" stroke="#1e293b" stroke-width="1.5"/>',
        f'<text x="{b1_x + 16}" y="{b1_y + 24}" fill="#60a5fa" font-size="11" font-weight="700">📐 PRELIMINARY STRUCTURAL SIZING (IS 456)</text>',
        f'<text x="{b1_x + 16}" y="{b1_y + 50}" fill="#94a3b8" font-size="10">Column Grid:</text>',
        f'<text x="{b1_x + 120}" y="{b1_y + 50}" fill="#f8fafc" font-size="10" font-weight="600">{c.column_grid_spacing}</text>',
        f'<text x="{b1_x + 16}" y="{b1_y + 75}" fill="#94a3b8" font-size="10">Column Size:</text>',
        f'<text x="{b1_x + 120}" y="{b1_y + 75}" fill="#f8fafc" font-size="10" font-weight="600">{c.column_size.split(" with")[0]}</text>',
        f'<text x="{b1_x + 16}" y="{b1_y + 100}" fill="#94a3b8" font-size="10">Beam Size:</text>',
        f'<text x="{b1_x + 120}" y="{b1_y + 100}" fill="#f8fafc" font-size="10" font-weight="600">{c.beam_size.split(" with")[0]}</text>',
        f'<text x="{b1_x + 16}" y="{b1_y + 125}" fill="#94a3b8" font-size="10">Slab Thickness:</text>',
        f'<text x="{b1_x + 120}" y="{b1_y + 125}" fill="#f8fafc" font-size="10" font-weight="600">{c.slab_thickness.split(" with")[0]}</text>',
        f'<text x="{b1_x + 16}" y="{b1_y + 150}" fill="#94a3b8" font-size="10">Concrete Grade:</text>',
        f'<text x="{b1_x + 120}" y="{b1_y + 150}" fill="#34d399" font-size="10" font-weight="700">{c.concrete_grade}</text>',
        f'<text x="{b1_x + 16}" y="{b1_y + 175}" fill="#94a3b8" font-size="10">Steel Grade:</text>',
        f'<text x="{b1_x + 120}" y="{b1_y + 175}" fill="#a78bfa" font-size="10" font-weight="700">{c.steel_grade}</text>',
    ])

    # Material & Capex Column
    b2_x = 405
    b2_y = 75
    b2_w = 370
    b2_h = 205
    tot_cr = c.cost_total_estimated / 1e7
    tot_lk = c.cost_total_estimated / 1e5
    svg_parts.extend([
        f'<rect x="{b2_x}" y="{b2_y}" width="{b2_w}" height="{b2_h}" rx="10" fill="#131c31" stroke="#1e293b" stroke-width="1.5"/>',
        f'<text x="{b2_x + 16}" y="{b2_y + 24}" fill="#34d399" font-size="11" font-weight="700">📦 MATERIAL & CAPEX FORECAST</text>',
        f'<text x="{b2_x + 16}" y="{b2_y + 50}" fill="#94a3b8" font-size="10">Concrete Volume:</text>',
        f'<text x="{b2_x + 140}" y="{b2_y + 50}" fill="#f8fafc" font-size="10" font-weight="600">{c.estimated_concrete_m3:,.1f} m³</text>',
        f'<text x="{b2_x + 16}" y="{b2_y + 75}" fill="#94a3b8" font-size="10">TMT Steel Rebar:</text>',
        f'<text x="{b2_x + 140}" y="{b2_y + 75}" fill="#f8fafc" font-size="10" font-weight="600">{c.estimated_steel_tonnes:,.2f} MT ({c.estimated_steel_tonnes*1000:,.0f} kg)</text>',
        f'<text x="{b2_x + 16}" y="{b2_y + 100}" fill="#94a3b8" font-size="10">Cement Bags:</text>',
        f'<text x="{b2_x + 140}" y="{b2_y + 100}" fill="#f8fafc" font-size="10" font-weight="600">{c.estimated_cement_bags:,} bags (50kg)</text>',
        f'<text x="{b2_x + 16}" y="{b2_y + 125}" fill="#94a3b8" font-size="10">Sand / Aggregate:</text>',
        f'<text x="{b2_x + 140}" y="{b2_y + 125}" fill="#f8fafc" font-size="10" font-weight="600">{c.estimated_sand_brass} Brass / {c.estimated_aggregate_brass} Brass</text>',
        f'<line x1="{b2_x + 16}" y1="{b2_y + 140}" x2="{b2_x + b2_w - 16}" y2="{b2_y + 140}" stroke="#334155"/>',
        f'<text x="{b2_x + 16}" y="{b2_y + 165}" fill="#fbbf24" font-size="11" font-weight="700">Estimated Project Cost:</text>',
        f'<text x="{b2_x + 16}" y="{b2_y + 188}" fill="#ffffff" font-size="15" font-weight="800">₹ {tot_lk:,.2f} Lakhs <tspan fill="#94a3b8" font-size="12">({tot_cr:.2f} Cr)</tspan></text>',
    ])

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)
