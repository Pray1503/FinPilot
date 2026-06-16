from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

from modules.categorizer import CATEGORIES, categorize_expense
from modules.dashboard import (
    category_pie_chart,
    dashboard_metrics,
    financial_health_score,
    monthly_trend_chart,
    spending_pattern_analysis,
    top_categories_chart,
)
from modules.data_extractor import extract_bill_data
from modules.database import add_bill, database_schema, delete_bill, get_bills, init_db, update_bill
from modules.ocr_engine import load_uploaded_file_as_images, run_ocr_on_images, save_uploaded_file
from modules.reports import category_report, monthly_expense_report, to_csv_bytes, to_excel_bytes


APP_TITLE = "Smart Bill OCR Scanner"
BASE_DIR = Path(__file__).resolve().parent


st.set_page_config(page_title=APP_TITLE, page_icon="SB", layout="wide", initial_sidebar_state="expanded")


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #020617;
            --muted: #1E293B;
            --line: #BFDBFE;
            --blue: #0EA5E9;
            --green: #22C55E;
            --amber: #F59E0B;
            --red: #F43F5E;
            --bg: #ECFEFF;
        }
        html, body, [class*="css"] {
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: var(--ink);
        }
        p, span, label, div, section {
            color: var(--ink);
        }
        [data-testid="stMarkdownContainer"],
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p {
            color: var(--ink) !important;
        }
        input, textarea, select {
            color: #020617 !important;
            background-color: #FFFFFF !important;
        }
        .stApp {
            background:
                linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(236,254,255,0.95) 54%, rgba(240,253,244,0.95) 100%);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #FFFFFF 0%, #E0F2FE 48%, #DCFCE7 100%);
            border-right: 1px solid #BAE6FD;
        }
        [data-testid="stSidebar"] * {
            color: #020617 !important;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid #7DD3FC;
            border-radius: 8px;
            padding: 0.35rem 0.5rem;
            margin-bottom: 0.25rem;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:hover {
            background: #E0F2FE;
        }
        .block-container {
            max-width: 1440px;
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
        }
        .app-title {
            font-size: clamp(1.75rem, 3vw, 2.8rem);
            font-weight: 800;
            letter-spacing: 0;
            margin: 0 0 0.25rem;
        }
        .app-subtitle {
            color: var(--muted);
            margin: 0 0 1.25rem;
            font-size: 1rem;
        }
        .soft-panel {
            background: rgba(255,255,255,0.94);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 14px 36px rgba(14, 165, 233, 0.12);
        }
        .highlight-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 0.75rem;
            margin: 0.5rem 0 1rem;
        }
        .highlight-item {
            border: 1px solid #BAE6FD;
            background: linear-gradient(180deg, #FFFFFF 0%, #F0F9FF 100%);
            border-radius: 8px;
            padding: 0.75rem;
        }
        .highlight-label {
            color: #0F172A;
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: 0.2rem;
        }
        .highlight-value {
            font-size: 1rem;
            font-weight: 800;
            word-break: break-word;
            color: #020617;
        }
        .confidence {
            display: inline-flex;
            align-items: center;
            padding: 0.28rem 0.55rem;
            border-radius: 999px;
            background: #DCFCE7;
            color: #166534;
            font-weight: 800;
            font-size: 0.82rem;
        }
        .schema-block {
            background: #F0F9FF;
            color: #020617;
            border: 1px solid #BAE6FD;
            border-radius: 8px;
            padding: 1rem;
            overflow-x: auto;
            font-size: 0.86rem;
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, #FFFFFF 0%, #F0FDFA 100%);
            border: 1px solid #A7F3D0;
            border-radius: 8px;
            padding: 0.85rem;
            box-shadow: 0 12px 28px rgba(34, 197, 94, 0.10);
        }
        .stButton > button, button[kind="primary"] {
            border-radius: 8px !important;
            min-height: 42px;
            font-weight: 800 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    st.markdown(f"<h1 class='app-title'>{title}</h1><p class='app-subtitle'>{subtitle}</p>", unsafe_allow_html=True)


def money(value: float) -> str:
    return f"Rs {value:,.2f}"


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def render_extracted_highlights(extracted: dict, category: str, confidence: float) -> None:
    values = {
        "Vendor": extracted.get("vendor", "Unknown"),
        "Bill Date": extracted.get("date") or "Missing",
        "Total Amount": money(float(extracted.get("amount") or 0)),
        "Tax Amount": money(float(extracted.get("tax") or 0)),
        "Invoice No.": extracted.get("invoice_number") or "Missing",
        "Payment": extracted.get("payment_method") or "Missing",
        "Category": category,
    }
    cards = "".join(
        f"<div class='highlight-item'><div class='highlight-label'>{label}</div><div class='highlight-value'>{value}</div></div>"
        for label, value in values.items()
    )
    st.markdown(f"<div class='confidence'>OCR confidence: {confidence:.2f}%</div><div class='highlight-grid'>{cards}</div>", unsafe_allow_html=True)


def dashboard_page() -> None:
    page_header("Dashboard", "Track student expenses from scanned bills and spot spending patterns early.")
    bills = get_bills()
    metrics = dashboard_metrics(bills)
    health_score, insights = financial_health_score(bills)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Expenses", money(metrics["total"]))
    c2.metric("Number of Bills", f"{metrics['count']}")
    c3.metric("Average Bill Amount", money(metrics["average"]))
    c4.metric("Highest Expense", money(metrics["highest"]))
    c5.metric("Financial Health", f"{health_score}/100")

    tabs = st.tabs(["Overview", "Spending Insights"])
    with tabs[0]:
        left, right = st.columns([1, 1])
        with left:
            st.plotly_chart(category_pie_chart(bills), use_container_width=True)
        with right:
            st.plotly_chart(monthly_trend_chart(bills), use_container_width=True)
        st.plotly_chart(top_categories_chart(bills), use_container_width=True)

    with tabs[1]:
        analysis = spending_pattern_analysis(bills)
        left, right = st.columns([1, 1])
        with left:
            st.subheader("Pattern Analysis")
            st.write(f"Predicted most common expense category: **{analysis['predicted_category']}**")
            st.write(f"Monthly spending trend: **{analysis['trend_direction']}** ({analysis['monthly_change_pct']}%)")
            frequent_vendors = analysis["frequent_vendors"]
            if frequent_vendors:
                st.write("Frequently visited vendors")
                st.dataframe(pd.DataFrame(frequent_vendors, columns=["Vendor", "Bills"]), hide_index=True, use_container_width=True)
            else:
                st.info("Scan bills to learn frequent vendor behavior.")
        with right:
            st.subheader("Personalized Insights")
            for insight in insights:
                st.info(insight)


def process_uploaded_file(uploaded_file, history: pd.DataFrame) -> None:
    st.markdown("<div class='soft-panel'>", unsafe_allow_html=True)
    st.subheader(uploaded_file.name)
    try:
        saved_path = save_uploaded_file(uploaded_file)
        images = load_uploaded_file_as_images(uploaded_file)
        preview_col, result_col = st.columns([0.9, 1.1])
        with preview_col:
            st.caption("Bill preview")
            st.image(images[0], use_container_width=True)
            if len(images) > 1:
                st.caption(f"{len(images)} PDF pages detected. OCR will process all pages.")

        with st.spinner("Reading bill with PaddleOCR..."):
            ocr_result = run_ocr_on_images(images)
        extracted = extract_bill_data(ocr_result["raw_text"]).to_dict()
        category, scores = categorize_expense(extracted["vendor"], ocr_result["raw_text"], history)

        with result_col:
            render_extracted_highlights(extracted, category, ocr_result["confidence"])
            if extracted.get("validation_warnings"):
                with st.expander("Validation warnings", expanded=True):
                    for warning in extracted["validation_warnings"]:
                        st.warning(warning)

        with st.expander("Raw OCR text", expanded=False):
            st.text_area("OCR output", ocr_result["raw_text"], height=220, key=f"raw_{saved_path.name}")

        with st.expander("Manual correction and save", expanded=True):
            with st.form(f"confirm_{saved_path.name}"):
                f1, f2, f3 = st.columns(3)
                vendor = f1.text_input("Vendor / Store Name", value=extracted["vendor"])
                amount = f2.number_input("Total Amount", min_value=0.0, value=float(extracted["amount"] or 0), step=1.0)
                tax = f3.number_input("Tax Amount", min_value=0.0, value=float(extracted["tax"] or 0), step=1.0)
                f4, f5, f6 = st.columns(3)
                bill_date = f4.date_input("Bill Date", value=parse_date(extracted["date"]) or date.today())
                selected_category = f5.selectbox("Category", CATEGORIES, index=CATEGORIES.index(category) if category in CATEGORIES else CATEGORIES.index("Other"))
                invoice_number = f6.text_input("Invoice Number", value=extracted.get("invoice_number") or "")
                payment_method = st.text_input("Payment Method", value=extracted.get("payment_method") or "")
                submitted = st.form_submit_button("Save Scanned Bill", type="primary", use_container_width=True)
                if submitted:
                    bill_id = add_bill(
                        vendor=vendor,
                        amount=float(amount),
                        tax=float(tax),
                        date=bill_date.isoformat(),
                        category=selected_category,
                        invoice_number=invoice_number or None,
                        image_path=str(saved_path),
                        raw_text=ocr_result["raw_text"],
                        ocr_confidence=float(ocr_result["confidence"]),
                        payment_method=payment_method or None,
                        extraction_json=json.dumps({"extracted": extracted, "category_scores": scores, "ocr_items": ocr_result["items"]}),
                    )
                    st.success(f"Saved bill #{bill_id}.")
    except Exception as exc:
        st.error(f"Could not process {uploaded_file.name}: {exc}")
    st.markdown("</div>", unsafe_allow_html=True)


def upload_page() -> None:
    page_header("Upload Bills", "Drag and drop JPG, JPEG, PNG, or PDF bills for OCR extraction.")
    history = get_bills()
    uploaded_files = st.file_uploader(
        "Upload one or more bills",
        type=["jpg", "jpeg", "png", "pdf"],
        accept_multiple_files=True,
        help="Images are previewed directly. PDF pages are rendered before OCR.",
    )
    if not uploaded_files:
        st.info("Drop bill files here to extract vendor, date, total, tax, invoice number, and payment method.")
        return
    for uploaded_file in uploaded_files:
        process_uploaded_file(uploaded_file, history)


def bill_history_page() -> None:
    page_header("Bill History", "Search, filter, edit, and delete scanned bills.")
    all_bills = get_bills()
    f1, f2, f3, f4 = st.columns([1.4, 1, 1, 1])
    search = f1.text_input("Search bills", placeholder="Vendor, invoice, or OCR text")
    category = f2.selectbox("Category", ["All"] + CATEGORIES)
    date_filter = f3.selectbox("Date filter", ["All dates", "This month", "Custom range"])
    start = end = None
    if date_filter == "This month":
        today = date.today()
        start = today.replace(day=1)
        end = today
        f4.write(f"{start.isoformat()} to {end.isoformat()}")
    elif date_filter == "Custom range":
        selected_range = f4.date_input("Date range", value=(date.today().replace(day=1), date.today()))
        if isinstance(selected_range, tuple) and len(selected_range) == 2:
            start, end = selected_range
    bills = get_bills(search=search, category=category, start_date=start.isoformat() if start else None, end_date=end.isoformat() if end else None)

    if bills.empty:
        st.info("No bills match the selected filters.")
        return

    visible_columns = ["id", "date", "vendor", "category", "amount", "tax", "invoice_number", "payment_method", "ocr_confidence"]
    st.dataframe(bills[visible_columns], hide_index=True, use_container_width=True)

    st.subheader("Edit Selected Bill")
    selected_id = st.selectbox("Bill ID", bills["id"].tolist())
    selected = bills[bills["id"] == selected_id].iloc[0]
    with st.form("edit_bill_form"):
        c1, c2, c3 = st.columns(3)
        vendor = c1.text_input("Vendor", value=selected["vendor"])
        amount = c2.number_input("Amount", min_value=0.0, value=float(selected["amount"]), step=1.0)
        tax = c3.number_input("Tax", min_value=0.0, value=float(selected["tax"] or 0), step=1.0)
        c4, c5, c6 = st.columns(3)
        bill_date = c4.date_input("Date", value=parse_date(selected["date"]) or date.today())
        category_value = c5.selectbox("Category", CATEGORIES, index=CATEGORIES.index(selected["category"]) if selected["category"] in CATEGORIES else 7)
        invoice = c6.text_input("Invoice Number", value=selected["invoice_number"] or "")
        payment = st.text_input("Payment Method", value=selected["payment_method"] or "")
        raw_text = st.text_area("Raw OCR Text", value=selected["raw_text"] or "", height=160)
        save, remove = st.columns(2)
        update_clicked = save.form_submit_button("Update Bill", type="primary", use_container_width=True)
        delete_clicked = remove.form_submit_button("Delete Bill", use_container_width=True)
        if update_clicked:
            update_bill(
                int(selected_id),
                {
                    "vendor": vendor,
                    "amount": amount,
                    "tax": tax,
                    "date": bill_date.isoformat(),
                    "category": category_value,
                    "invoice_number": invoice or None,
                    "payment_method": payment or None,
                    "raw_text": raw_text,
                },
            )
            st.success("Bill updated.")
            st.rerun()
        if delete_clicked:
            delete_bill(int(selected_id))
            st.success("Bill deleted.")
            st.rerun()

    with st.expander("Preview stored bill image"):
        image_path = selected["image_path"]
        if image_path and Path(image_path).exists() and Path(image_path).suffix.lower() in {".jpg", ".jpeg", ".png"}:
            st.image(Image.open(image_path), use_container_width=True)
        else:
            st.write(image_path or "No preview available.")


def reports_page() -> None:
    page_header("Reports", "Generate monthly and category reports, then export CSV or Excel files.")
    bills = get_bills()
    monthly = monthly_expense_report(bills)
    categories = category_report(bills)

    tab1, tab2, tab3 = st.tabs(["Monthly Expense Report", "Category Report", "Exports"])
    with tab1:
        st.dataframe(monthly, hide_index=True, use_container_width=True)
    with tab2:
        st.dataframe(categories, hide_index=True, use_container_width=True)
    with tab3:
        export_df = bills.drop(columns=["raw_text"], errors="ignore")
        st.download_button("Download All Bills CSV", data=to_csv_bytes(export_df), file_name="smart_bill_ocr_bills.csv", mime="text/csv")
        excel_bytes = to_excel_bytes({"Bills": export_df, "Monthly Report": monthly, "Category Report": categories})
        st.download_button(
            "Download Excel Workbook",
            data=excel_bytes,
            file_name="smart_bill_ocr_reports.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with st.expander("Database schema"):
        st.markdown(f"<pre class='schema-block'>{database_schema()}</pre>", unsafe_allow_html=True)


def about_page() -> None:
    page_header("Project Guide", "Installation, folder structure, and implementation notes.")
    st.subheader("Installation")
    st.code(
        """python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py""",
        language="powershell",
    )
    st.subheader("Folder Structure")
    st.code(
        """E:\\fintec
|-- app.py
|-- requirements.txt
|-- modules
|   |-- ocr_engine.py
|   |-- data_extractor.py
|   |-- categorizer.py
|   |-- database.py
|   |-- reports.py
|   `-- dashboard.py
|-- data
|   `-- bills.db
`-- uploads""",
        language="text",
    )
    st.subheader("Database Schema")
    st.code(database_schema(), language="sql")


def sidebar_nav() -> str:
    with st.sidebar:
        st.title(APP_TITLE)
        st.caption("Student financial management")
        return st.radio("Navigation", ["Dashboard", "Upload", "Bill History", "Reports", "Project Guide"], label_visibility="collapsed")


def main() -> None:
    init_db()
    inject_css()
    page = sidebar_nav()
    pages = {
        "Dashboard": dashboard_page,
        "Upload": upload_page,
        "Bill History": bill_history_page,
        "Reports": reports_page,
        "Project Guide": about_page,
    }
    pages[page]()


if __name__ == "__main__":
    main()
