"""
Live Execution Demonstration of Road Cost AI Engine
"""

import sys
import time
from estimate_service import (
    resolve_default_ssr_path,
    prepare_ssr_dataframe,
    generate_estimate,
    get_project_preset_chapters,
)
from schemas import ProjectMeasurements


def live_print(step_num, title, detail):
    print(f"\n=======================================================")
    print(f" [STEP {step_num}] {title}")
    print(f"-------------------------------------------------------")
    print(f" {detail}")
    time.sleep(0.5)


def main():
    print("=" * 60)
    print("      ROAD COST AI - LIVE ENGINE EXECUTION")
    print("=" * 60)

    # STEP 1
    live_print(1, "LOCATING & LOADING SSR DATASET", "Resolving default SSR path...")
    ssr_path = resolve_default_ssr_path()
    print(f" -> Found SSR File: {ssr_path}")
    
    t0 = time.time()
    df = prepare_ssr_dataframe(ssr_path)
    load_time = time.time() - t0
    
    print(f" -> Ingestion complete in {load_time:.2f}s")
    print(f" -> Total SSR Items Loaded: {len(df):,}")
    print(f" -> Unique Chapters: {df['chapter'].nunique()}")

    # STEP 2
    live_print(2, "CONFIGURING PROJECT MEASUREMENTS", "Setting parameters for New Concrete (CC) Road...")
    measurements = ProjectMeasurements(
        length_m=500.0,
        width_m=3.75,
        thickness_mm=150.0,
        drain_length_m=500.0,
        layers=[
            {"name": "subgrade", "thickness_mm": 300.0},
            {"name": "gsb", "thickness_mm": 150.0},
            {"name": "wmm", "thickness_mm": 100.0},
            {"name": "dlc", "thickness_mm": 100.0},
            {"name": "concrete", "thickness_mm": 150.0},
        ]
    )
    print(f" -> Road Length        : {measurements.length_m} m")
    print(f" -> Carriageway Width  : {measurements.width_m} m")
    print(f" -> Pavement Thickness : {measurements.thickness_mm} mm")
    print(f" -> Total Surface Area : {measurements.area_m2:,.2f} sq.m")
    print(f" -> Total CC Volume    : {measurements.volume_m3:,.2f} cu.m")
    print(f" -> Drain/Kerb Length  : {measurements.drain_length_m} m")

    # STEP 3
    live_print(3, "CHAPTER RESOLUTION & CANDIDATE FILTERING", "Mapping relevant road construction chapters...")
    all_chapters = sorted(c for c in df["chapter"].unique() if c)
    presets = get_project_preset_chapters(all_chapters, "New Road Construction", "Concrete (CC)")
    print(f" -> Matched Chapters ({len(presets)}):")
    for ch in presets[:6]:
        print(f"    * {ch}")
    if len(presets) > 6:
        print(f"    * ... and {len(presets) - 6} more")

    # STEP 4
    live_print(4, "RUNNING ESTIMATION & ARITHMETIC ENGINE", "Executing deterministic calculations (CostEngine + QuantityEngine)...")
    t0 = time.time()
    estimate = generate_estimate(
        df=df,
        mode="New Road Construction",
        road_kind="Concrete (CC)",
        measurements=measurements,
        allowed_chapters=presets,
        gst_percent=18.0,
        use_ai_selection=False,
    )
    calc_time = time.time() - t0
    print(f" -> Estimation completed in {calc_time:.3f}s")
    print(f" -> Selected Line Items in BOQ: {len(estimate.items)}")

    # STEP 5
    live_print(5, "BILL OF QUANTITIES (BOQ) BREAKDOWN", "Displaying primary construction line items:")
    print(f"{'Item No':<10} | {'Unit':<12} | {'Quantity':<12} | {'Rate (Rs)':<12} | {'Amount (Rs)':<16} | {'Description'}")
    print("-" * 100)
    for it in estimate.items[:10]:
        desc = it.description[:35] + "..." if len(it.description) > 35 else it.description
        print(f"{it.item_no:<10} | {it.unit:<12} | {it.quantity:<12,.2f} | Rs {it.rate:<9,.2f} | Rs {it.amount:<13,.2f} | {desc}")

    # STEP 6
    live_print(6, "FINANCIAL TOTALS & AUDIT SUMMARY", "Calculating Subtotal, 18% GST, and Grand Total:")
    print(f" -------------------------------------------------------------")
    print(f"  SUBTOTAL (Base Road Work Cost) : Rs {estimate.subtotal:>16,.2f}")
    print(f"  GST ({estimate.gst_percent:.0f}%)                    : Rs {estimate.gst_amount:>16,.2f}")
    print(f" -------------------------------------------------------------")
    print(f"  GRAND TOTAL ESTIMATE           : Rs {estimate.total:>16,.2f}")
    print(f" -------------------------------------------------------------")
    print("\n [SUCCESS] Road Cost AI engine executed live without any errors.")


if __name__ == "__main__":
    main()
