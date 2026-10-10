"""
Government Tender Docket & Official PWD Estimate Generator.

Produces official Maharashtra Public Works Department (PWD) compliant
tender dockets, abstracts of cost, itemized BOQ sheets, and printable PDF/HTML dockets
with statutory additions, certificates, and signature blocks.
"""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Optional, List
from schemas import CostEstimate, EstimateLineItem


def format_inr(val: float) -> str:
    """Format float into standard Indian currency representation."""
    if val is None:
        return "₹ 0.00"
    return f"₹ {val:,.2f}"


def format_crore_lakh(amount: float) -> str:
    """Format total amount strictly in Crores and Lakhs."""
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


def number_to_inr_words(amount: float) -> str:
    """Convert amount to standard Indian currency text representation in Crores and Lakhs."""
    if amount is None or amount == 0:
        return "Zero Rupees Only"
    
    abs_amt = round(abs(amount), 2)
    crores = int(abs_amt // 10_000_000)
    rem = abs_amt % 10_000_000
    lakhs = int(rem // 100_000)
    rem = rem % 100_000
    thousands = int(rem // 1000)
    rem = rem % 1000
    rupees = int(rem)
    paise = int(round((abs_amt - int(abs_amt)) * 100))

    parts = []
    if crores > 0:
        parts.append(f"{crores} Crore")
    if lakhs > 0:
        parts.append(f"{lakhs} Lakh")
    if thousands > 0:
        parts.append(f"{thousands} Thousand")
    if rupees > 0 or not parts:
        parts.append(f"{rupees}")
    
    result = "Rupees " + " ".join(parts)
    if paise > 0:
        result += f" and {paise} Paise"
    result += " Only"
    return result


def generate_pwd_tender_html(
    estimate: CostEstimate,
    project_title: str = "Infrastructure Development Work",
    work_category: str = "Roads & Highways",
    location: str = "Maharashtra, India",
    tender_no: Optional[str] = None,
    division: str = "Public Works Division",
) -> str:
    """
    Generate complete, official, standalone HTML for Maharashtra PWD Tender Estimate.
    Includes print stylesheets for 1-click browser printing to PDF.
    """
    today_str = datetime.now().strftime("%d-%m-%Y")
    if not tender_no:
        tender_no = f"PWD/MAHA/{datetime.now().strftime('%Y%m')}/{int(datetime.now().timestamp()) % 10000:04d}"

    subtotal = float(estimate.subtotal)
    gst = float(estimate.gst_amount)
    cess = round(subtotal * 0.01, 2)
    cont = round(subtotal * 0.04, 2)
    grand_total = round(subtotal + gst + cess + cont, 2)
    amount_in_words = number_to_inr_words(grand_total)

    # Build BOQ rows
    rows_html = []
    for idx, item in enumerate(estimate.items, 1):
        item_no = item.item_no or f"SSR-{idx:02d}"
        chapter = item.chapter or "Civil Works"
        desc = item.description or ""
        unit = item.unit or "Unit"
        qty = item.quantity or 0.0
        rate = item.rate or 0.0
        amt = item.amount or 0.0
        note = item.calculation_note or ""

        rows_html.append(f"""
        <tr>
            <td style="text-align: center; font-weight: 600;">{idx}</td>
            <td style="font-weight: 700; color: #1e293b; font-family: monospace;">{item_no}</td>
            <td>
                <div style="font-weight: 600; color: #0f172a;">{desc}</div>
                <div style="font-size: 11px; color: #64748b; margin-top: 2px;">
                    <span style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">Chapter: {chapter}</span>
                    {f'<span style="margin-left: 8px; font-style: italic;">{note}</span>' if note else ''}
                </div>
            </td>
            <td style="text-align: center; font-weight: 600;">{unit}</td>
            <td style="text-align: right; font-family: monospace;">{qty:,.2f}</td>
            <td style="text-align: right; font-family: monospace;">₹ {rate:,.2f}</td>
            <td style="text-align: right; font-weight: 700; font-family: monospace; color: #0f172a;">₹ {amt:,.2f}</td>
        </tr>
        """)

    table_body = "\n".join(rows_html)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PWD Official Tender Estimate - {project_title}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
            background: #f8fafc;
            color: #1e293b;
            padding: 24px;
            font-size: 13px;
            line-height: 1.5;
        }}

        .docket-container {{
            max-width: 960px;
            margin: 0 auto;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.06);
            padding: 40px;
        }}

        /* Print Button Bar */
        .action-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            padding: 14px 20px;
            border-radius: 10px;
            color: #ffffff;
        }}

        .btn-print {{
            background: #f59e0b;
            color: #000000;
            border: none;
            padding: 8px 18px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}

        .btn-print:hover {{
            background: #d97706;
            transform: translateY(-1px);
        }}

        /* Official Header */
        .govt-header {{
            text-align: center;
            border-bottom: 2px solid #0f172a;
            padding-bottom: 16px;
            margin-bottom: 20px;
        }}

        .govt-emblem {{
            font-size: 32px;
            margin-bottom: 4px;
        }}

        .govt-title {{
            font-size: 18px;
            font-weight: 800;
            letter-spacing: 0.5px;
            color: #0f172a;
            text-transform: uppercase;
        }}

        .govt-subtitle {{
            font-size: 14px;
            font-weight: 700;
            color: #d97706;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-top: 2px;
        }}

        .govt-office {{
            font-size: 12px;
            color: #475569;
            margin-top: 4px;
        }}

        /* Meta Grid */
        .meta-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 16px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 24px;
        }}

        .meta-item {{
            margin-bottom: 6px;
        }}

        .meta-label {{
            font-size: 11px;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .meta-value {{
            font-size: 13px;
            font-weight: 700;
            color: #0f172a;
        }}

        /* Tables */
        table.boq-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 24px;
        }}

        table.boq-table th {{
            background: #0f172a;
            color: #ffffff;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            padding: 10px 12px;
            border: 1px solid #0f172a;
        }}

        table.boq-table td {{
            padding: 10px 12px;
            border: 1px solid #e2e8f0;
            font-size: 12.5px;
        }}

        table.boq-table tr:nth-child(even) {{
            background: #fbfcfe;
        }}

        /* Statutory Summary Box */
        .summary-box {{
            width: 100%;
            margin-left: auto;
            max-width: 460px;
            margin-bottom: 28px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            overflow: hidden;
        }}

        .summary-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 16px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 12.5px;
        }}

        .summary-row.grand-total {{
            background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
            border-top: 2px solid #10b981;
            border-bottom: none;
            font-weight: 800;
            font-size: 15px;
            color: #047857;
        }}

        /* In words banner */
        .words-banner {{
            background: #f8fafc;
            border-left: 4px solid #f59e0b;
            padding: 12px 16px;
            border-radius: 4px;
            margin-bottom: 30px;
            font-weight: 600;
            color: #1e293b;
        }}

        /* Certificate Clause */
        .certificate-clause {{
            font-size: 11.5px;
            color: #475569;
            line-height: 1.6;
            border-top: 1px dashed #cbd5e1;
            padding-top: 14px;
            margin-bottom: 36px;
        }}

        /* Signature Blocks */
        .signatures-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            text-align: center;
            margin-top: 20px;
            padding-top: 30px;
        }}

        .sig-box {{
            border-top: 1px solid #64748b;
            padding-top: 8px;
        }}

        .sig-role {{
            font-weight: 700;
            font-size: 11.5px;
            color: #0f172a;
        }}

        .sig-dept {{
            font-size: 10.5px;
            color: #64748b;
            margin-top: 2px;
        }}

        /* Print Media Styles */
        @media print {{
            body {{
                background: #ffffff;
                padding: 0;
            }}
            .action-bar {{
                display: none !important;
            }}
            .docket-container {{
                border: none;
                box-shadow: none;
                padding: 0;
                max-width: 100%;
            }}
            table.boq-table th {{
                background: #1e293b !important;
                color: #ffffff !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            .summary-row.grand-total {{
                background: #ecfdf5 !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
        }}
    </style>
</head>
<body>
    <div class="docket-container">
        <!-- Action Bar (Hidden when printed) -->
        <div class="action-bar">
            <div>
                <strong>Official Government Tender Estimate Docket</strong>
                <span style="opacity: 0.8; font-size: 12px; margin-left: 8px;">• PWD Maharashtra SSR 2022-23</span>
            </div>
            <button class="btn-print" onclick="window.print()">
                🖨️ Print / Save to PDF
            </button>
        </div>

        <!-- Maharashtra Govt Header -->
        <div class="govt-header">
            <div class="govt-emblem">🏛️</div>
            <div class="govt-title">Government of Maharashtra</div>
            <div class="govt-subtitle">Public Works Department (PWD)</div>
            <div class="govt-office">{division} • Regional Engineering Wing</div>
        </div>

        <!-- Project Meta Grid -->
        <div class="meta-grid">
            <div>
                <div class="meta-item">
                    <div class="meta-label">Name of Work</div>
                    <div class="meta-value">{project_title}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Work Domain & Classification</div>
                    <div class="meta-value">{work_category}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Location / Site Jurisdiction</div>
                    <div class="meta-value">{location}</div>
                </div>
            </div>
            <div>
                <div class="meta-item">
                    <div class="meta-label">Estimate Reference No.</div>
                    <div class="meta-value" style="font-family: monospace;">{tender_no}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Date of Estimate</div>
                    <div class="meta-value">{today_str}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Schedule of Rates Used</div>
                    <div class="meta-value">Maharashtra PWD SSR 2022-23</div>
                </div>
            </div>
        </div>

        <!-- Itemized BOQ Table -->
        <h3 style="margin-bottom: 12px; font-size: 15px; font-weight: 800; color: #0f172a; text-transform: uppercase;">
            Bill of Quantities (BOQ) & Itemized Measurements
        </h3>

        <table class="boq-table">
            <thead>
                <tr>
                    <th style="width: 4%;">Sr</th>
                    <th style="width: 14%;">SSR Item No</th>
                    <th style="width: 42%;">Description of Item per PWD Standard</th>
                    <th style="width: 8%;">Unit</th>
                    <th style="width: 10%; text-align: right;">Quantity</th>
                    <th style="width: 10%; text-align: right;">Rate (₹)</th>
                    <th style="width: 12%; text-align: right;">Amount (₹)</th>
                </tr>
            </thead>
            <tbody>
                {table_body}
            </tbody>
        </table>

        <!-- Statutory Additions Summary -->
        <div style="display: flex; justify-content: flex-end;">
            <div class="summary-box">
                <div class="summary-row">
                    <span>Base Civil Cost (SSR Total)</span>
                    <strong style="font-family: monospace;">{format_inr(subtotal)}</strong>
                </div>
                <div class="summary-row">
                    <span>Add: GST @ 18.00% (CGST 9% + SGST 9%)</span>
                    <strong style="font-family: monospace;">{format_inr(gst)}</strong>
                </div>
                <div class="summary-row">
                    <span>Add: Labour Welfare Cess @ 1.00%</span>
                    <strong style="font-family: monospace;">{format_inr(cess)}</strong>
                </div>
                <div class="summary-row">
                    <span>Add: Contingencies & Quality Testing @ 4.00%</span>
                    <strong style="font-family: monospace;">{format_inr(cont)}</strong>
                </div>
                <div class="summary-row grand-total">
                    <span>GRAND TOTAL ESTIMATE</span>
                    <span style="font-family: monospace;">{format_inr(grand_total)}</span>
                </div>
            </div>
        </div>

        <!-- Amount In Words -->
        <div class="words-banner">
            <strong>Estimated Amount in Words:</strong> {amount_in_words} ({format_crore_lakh(grand_total)})
        </div>

        <!-- Certificate Clause -->
        <div class="certificate-clause">
            <strong>TECHNICAL CERTIFICATE:</strong> Certified that the rates adopted in this estimate are strictly based on the Maharashtra Public Works Department Schedule of Rates (SSR) for the year 2022-23. The quantities have been computed systematically from approved engineering dimensions and standards per IRC / IS 456 codes. Provisions for GST (18%), Labour Welfare Cess (1%), and contingencies have been incorporated per statutory Government of Maharashtra directives.
        </div>

        <!-- 4-Tier Signature Block -->
        <div class="signatures-grid">
            <div class="sig-box">
                <div class="sig-role">Junior Engineer</div>
                <div class="sig-dept">Prepared & Calculated</div>
            </div>
            <div class="sig-box">
                <div class="sig-role">Sub-Divisional Engineer</div>
                <div class="sig-dept">Checked & Verified</div>
            </div>
            <div class="sig-box">
                <div class="sig-role">Executive Engineer</div>
                <div class="sig-dept">Recommended & Submitted</div>
            </div>
            <div class="sig-box">
                <div class="sig-role">Superintending Engineer</div>
                <div class="sig-dept">Technically Sanctioned</div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    return html


def render_docket_export_ui(
    estimate: CostEstimate,
    project_title: str = "Infrastructure Development Project",
    work_category: str = "Civil Engineering Works",
    location: str = "Maharashtra, India",
    key_suffix: str = "",
):
    """
    Render Streamlit UI components for previewing and downloading the
    official Maharashtra PWD Tender Docket and printing it as a PDF.
    """
    import streamlit as st
    import streamlit.components.v1 as components

    if not estimate or not estimate.items:
        return

    html_content = generate_pwd_tender_html(
        estimate=estimate,
        project_title=project_title,
        work_category=work_category,
        location=location,
    )

    with st.expander("📄 Official PWD Tender Estimate & Printable PDF Docket", expanded=False):
        st.markdown("""
        <div style="background: #f8fafc; border-left: 4px solid #f59e0b; padding: 10px 14px; border-radius: 4px; margin-bottom: 14px; font-size: 13px;">
            <strong>🏛️ Government of Maharashtra Tender Format:</strong>
            This docket complies with official PWD SSR 2022-23 standards, featuring statutory markups (GST 18%, Labour Cess 1%, Contingencies 4%),
            technical certificates, and 4-tier signature blocks. Click <strong>"Print / Save to PDF"</strong> inside the preview to download a vector PDF.
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([1, 1])
        with col1:
            st.download_button(
                "📥 Download Official Docket (.html)",
                data=html_content.encode("utf-8"),
                file_name=f"PWD_Tender_Docket_{key_suffix or 'estimate'}.html",
                mime="text/html",
                use_container_width=True,
                key=f"dl_html_docket_{key_suffix}",
            )
        with col2:
            st.caption("💡 To save as PDF: Open the preview below or the downloaded file, then click 'Print / Save to PDF' and select 'Save as PDF'.")

        components.html(html_content, height=600, scrolling=True)

