from __future__ import annotations

import io

import pandas as pd


def monthly_expense_report(bills: pd.DataFrame) -> pd.DataFrame:
    if bills.empty:
        return pd.DataFrame(columns=["month", "total_amount", "bill_count", "average_amount"])
    df = bills.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return pd.DataFrame(columns=["month", "total_amount", "bill_count", "average_amount"])
    report = (
        df.assign(month=df["date"].dt.to_period("M").astype(str))
        .groupby("month", as_index=False)
        .agg(total_amount=("amount", "sum"), bill_count=("id", "count"), average_amount=("amount", "mean"))
        .sort_values("month", ascending=False)
    )
    return report.round(2)


def category_report(bills: pd.DataFrame) -> pd.DataFrame:
    if bills.empty:
        return pd.DataFrame(columns=["category", "total_amount", "bill_count", "average_amount", "share_percent"])
    total = bills["amount"].sum()
    report = (
        bills.groupby("category", as_index=False)
        .agg(total_amount=("amount", "sum"), bill_count=("id", "count"), average_amount=("amount", "mean"))
        .sort_values("total_amount", ascending=False)
    )
    report["share_percent"] = (report["total_amount"] / total * 100).fillna(0) if total else 0
    return report.round(2)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            safe_name = sheet_name[:31] or "Sheet1"
            df.to_excel(writer, sheet_name=safe_name, index=False)
    output.seek(0)
    return output.getvalue()

