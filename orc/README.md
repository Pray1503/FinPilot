# Smart Bill OCR Scanner

Production-ready Streamlit application for scanning student expense bills with PaddleOCR, automatic data extraction, categorization, SQLite storage, dashboards, reports, and financial health insights.

## Installation

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Folder Structure

```text
E:\fintec
|-- app.py
|-- requirements.txt
|-- README.md
|-- modules
|   |-- ocr_engine.py
|   |-- data_extractor.py
|   |-- categorizer.py
|   |-- database.py
|   |-- reports.py
|   `-- dashboard.py
|-- data
|   `-- bills.db
`-- uploads
```

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor TEXT NOT NULL DEFAULT 'Unknown',
    amount REAL NOT NULL DEFAULT 0,
    tax REAL DEFAULT 0,
    date TEXT,
    category TEXT NOT NULL DEFAULT 'Other',
    invoice_number TEXT,
    image_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expense_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL,
    raw_text TEXT,
    ocr_confidence REAL DEFAULT 0,
    payment_method TEXT,
    extraction_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
);
```

## Features

- Multiple JPG, JPEG, PNG, and PDF bill uploads
- PaddleOCR text extraction with average confidence score
- Regex and validation-based extraction for vendor, date, total, tax, invoice number, and payment method
- Smart categorization with manual correction
- SQLite database created automatically in `data/bills.db`
- Dashboard with metrics, category pie chart, monthly trend, top categories, spending insights, and financial health score
- Bill history with search, category/date filters, edit, and delete
- Monthly and category reports with CSV and Excel export

