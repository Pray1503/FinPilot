from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .categorizer import CATEGORIES, most_common_category


COLOR_SEQUENCE = ["#0EA5E9", "#22C55E", "#F59E0B", "#F43F5E", "#A855F7", "#14B8A6", "#84CC16", "#FB7185"]


def empty_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text="No bills scanned yet", x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="#0EA5E9"))
    fig.update_layout(
        title=title,
        height=340,
        margin=dict(l=16, r=16, t=48, b=24),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def dashboard_metrics(bills: pd.DataFrame) -> dict[str, float]:
    if bills.empty:
        return {"total": 0.0, "count": 0, "average": 0.0, "highest": 0.0}
    return {
        "total": float(bills["amount"].sum()),
        "count": int(len(bills)),
        "average": float(bills["amount"].mean()),
        "highest": float(bills["amount"].max()),
    }


def category_pie_chart(bills: pd.DataFrame) -> go.Figure:
    if bills.empty:
        return empty_figure("Category Split")
    grouped = bills.groupby("category", as_index=False)["amount"].sum()
    fig = px.pie(grouped, names="category", values="amount", hole=0.48, color_discrete_sequence=COLOR_SEQUENCE)
    fig.update_layout(title="Pie Chart of Categories", height=360, margin=dict(l=16, r=16, t=56, b=16))
    return fig


def monthly_trend_chart(bills: pd.DataFrame) -> go.Figure:
    if bills.empty:
        return empty_figure("Monthly Expense Trend")
    df = bills.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return empty_figure("Monthly Expense Trend")
    monthly = df.assign(month=df["date"].dt.to_period("M").dt.to_timestamp()).groupby("month", as_index=False)["amount"].sum()
    fig = px.line(monthly, x="month", y="amount", markers=True, color_discrete_sequence=["#0EA5E9"])
    fig.update_traces(line=dict(width=3))
    fig.update_layout(title="Monthly Expense Trend", height=360, margin=dict(l=16, r=16, t=56, b=16), yaxis_title="Amount")
    return fig


def top_categories_chart(bills: pd.DataFrame) -> go.Figure:
    if bills.empty:
        return empty_figure("Top Spending Categories")
    grouped = bills.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=True).tail(6)
    fig = px.bar(grouped, x="amount", y="category", orientation="h", color="category", color_discrete_sequence=COLOR_SEQUENCE)
    fig.update_layout(title="Top Spending Categories", height=360, margin=dict(l=16, r=16, t=56, b=16), showlegend=False)
    return fig


def spending_pattern_analysis(bills: pd.DataFrame) -> dict[str, object]:
    if bills.empty:
        return {
            "frequent_vendors": [],
            "predicted_category": "Other",
            "monthly_change_pct": 0.0,
            "trend_direction": "stable",
        }
    vendors = Counter(bills["vendor"].dropna().tolist()).most_common(5)
    predicted = most_common_category(bills)
    df = bills.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    monthly = df.dropna(subset=["date"]).assign(month=lambda data: data["date"].dt.to_period("M")).groupby("month")["amount"].sum()
    change_pct = 0.0
    direction = "stable"
    if len(monthly) >= 2 and monthly.iloc[-2] > 0:
        change_pct = ((monthly.iloc[-1] - monthly.iloc[-2]) / monthly.iloc[-2]) * 100
        direction = "increasing" if change_pct > 5 else "decreasing" if change_pct < -5 else "stable"
    return {
        "frequent_vendors": vendors,
        "predicted_category": predicted,
        "monthly_change_pct": round(float(change_pct), 2),
        "trend_direction": direction,
    }


def financial_health_score(bills: pd.DataFrame) -> tuple[int, list[str]]:
    if bills.empty:
        return 70, ["Scan a few bills to personalize your financial health score."]

    df = bills.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    monthly = df.dropna(subset=["date"]).assign(month=lambda data: data["date"].dt.to_period("M")).groupby("month")["amount"].sum()
    total = df["amount"].sum()
    category_share = df.groupby("category")["amount"].sum() / total if total else pd.Series(dtype=float)

    consistency_score = 30
    if len(monthly) >= 2 and monthly.mean() > 0:
        volatility = monthly.std(ddof=0) / monthly.mean()
        consistency_score = int(np.clip(35 - volatility * 35, 5, 35))

    diversity_score = int(np.clip(len(category_share) / len(CATEGORIES) * 25, 6, 25))
    concentration_penalty = int(np.clip((category_share.max() if not category_share.empty else 0) * 20, 0, 20))

    trend_score = 30
    if len(monthly) >= 2 and monthly.iloc[-2] > 0:
        change = (monthly.iloc[-1] - monthly.iloc[-2]) / monthly.iloc[-2]
        trend_score = int(np.clip(30 - max(change, 0) * 40, 5, 30))

    score = int(np.clip(consistency_score + diversity_score + trend_score + 10 - concentration_penalty, 0, 100))
    insights = generate_personalized_insights(df)
    return score, insights


def generate_personalized_insights(bills: pd.DataFrame) -> list[str]:
    if bills.empty:
        return ["No spending patterns are available yet."]
    insights: list[str] = []
    df = bills.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    dated = df.dropna(subset=["date"])
    if not dated.empty:
        monthly_category = (
            dated.assign(month=lambda data: data["date"].dt.to_period("M"))
            .groupby(["month", "category"])["amount"]
            .sum()
            .reset_index()
            .sort_values("month")
        )
        for category in CATEGORIES:
            category_rows = monthly_category[monthly_category["category"] == category]
            if len(category_rows) >= 2 and category_rows.iloc[-2]["amount"] > 0:
                change = ((category_rows.iloc[-1]["amount"] - category_rows.iloc[-2]["amount"]) / category_rows.iloc[-2]["amount"]) * 100
                if abs(change) >= 10:
                    direction = "increased" if change > 0 else "decreased"
                    insights.append(f"{category} expenses {direction} by {abs(change):.0f}% this month.")

    category_totals = df.groupby("category")["amount"].sum().sort_values(ascending=False)
    if not category_totals.empty:
        top_category = category_totals.index[0]
        top_share = category_totals.iloc[0] / max(category_totals.sum(), 1) * 100
        if top_category == "Shopping" and top_share > 25:
            insights.append("Shopping expenses exceed a recommended student budget share.")
        elif top_share > 45:
            insights.append(f"{top_category} is taking {top_share:.0f}% of scanned expenses; review recurring purchases.")

    if not insights:
        insights.append("Your scanned expenses look balanced across categories.")
    return insights[:5]
