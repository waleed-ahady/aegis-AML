from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine

from aegis_aml.analytics.dashboard_data import (
    alert_summary,
    flatten_alerts,
    load_alerts,
    load_csv_report,
    load_json_report,
    parse_prometheus_metrics,
    reason_counts,
)

st.set_page_config(page_title="AegisAML Operations", page_icon="🛡️", layout="wide")

DATABASE_URL = os.getenv("AEGIS_DATABASE_URL", "sqlite:///./aegis_alerts.db")
API_URL = os.getenv("AEGIS_API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("AEGIS_API_KEY")
EVALUATION_REPORT = os.getenv("AEGIS_EVALUATION_REPORT", "reports/ibm_hi_small_evaluation.json")
DRIFT_REPORT = os.getenv("AEGIS_DRIFT_REPORT", "reports/drift.json")
GRAPH_REPORT = os.getenv("AEGIS_GRAPH_REPORT", "reports/graph_risk.csv")


@st.cache_resource
def database_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


@st.cache_data(ttl=10)
def get_alert_data(limit: int) -> tuple[pd.DataFrame, int]:
    return load_alerts(database_engine(), limit)


@st.cache_data(ttl=10)
def get_api_health(api_url: str) -> tuple[dict[str, Any] | None, str | None, float | None]:
    started = datetime.now(UTC)
    try:
        response = httpx.get(f"{api_url}/health", timeout=2.5)
        response.raise_for_status()
        latency_ms = (datetime.now(UTC) - started).total_seconds() * 1000
        return response.json(), None, latency_ms
    except (httpx.HTTPError, ValueError) as exc:
        return None, str(exc), None


@st.cache_data(ttl=10)
def get_prometheus(api_url: str) -> dict[str, float]:
    try:
        response = httpx.get(f"{api_url}/metrics", timeout=2.5)
        response.raise_for_status()
        return parse_prometheus_metrics(response.text)
    except httpx.HTTPError:
        return {}


def metric_sum(metrics: dict[str, float], prefix: str) -> float:
    return sum(value for name, value in metrics.items() if name.startswith(prefix))


def format_percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.2%}"


OUTCOME_LABELS = {
    "needs_review": "Needs more investigation",
    "false_positive": "False positive",
    "confirmed_laundering": "Confirmed laundering",
}


def submit_feedback(alert_id: str, outcome: str, notes: str) -> tuple[bool, str]:
    headers = {"X-API-Key": API_KEY} if API_KEY else None
    try:
        response = httpx.post(
            f"{API_URL}/v1/alerts/{alert_id}/feedback",
            json={"outcome": outcome, "notes": notes.strip() or None},
            headers=headers,
            timeout=5,
        )
        response.raise_for_status()
        return True, f"Review saved as: {OUTCOME_LABELS[outcome]}."
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or str(exc)
        return False, f"Feedback failed ({exc.response.status_code}): {detail}"
    except httpx.HTTPError as exc:
        return False, f"Feedback failed: {exc}"


st.title("AegisAML Operations Console")
st.caption("Alert operations, investigation, model performance, service health, and risk analytics")

with st.sidebar:
    st.header("Controls")
    row_limit = st.select_slider("Alerts to load", options=[100, 500, 1000, 5000, 10000], value=5000)
    auto_refresh = st.toggle("Auto-refresh every 15 seconds", value=False)
    st.caption(f"Database: `{DATABASE_URL}`")
    st.caption(f"API: `{API_URL}`")
    if st.button("Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if auto_refresh:
        st.caption("Auto-refresh is enabled.")
        st.markdown("<meta http-equiv='refresh' content='15'>", unsafe_allow_html=True)

try:
    alerts_raw, total_alerts = get_alert_data(row_limit)
except Exception as exc:
    st.error(f"Could not query the alert database: {exc}")
    alerts_raw, total_alerts = pd.DataFrame(), 0
alerts = flatten_alerts(alerts_raw)
summary = alert_summary(alerts_raw, total_alerts)
health, health_error, health_latency = get_api_health(API_URL)
prometheus = get_prometheus(API_URL)
evaluation = load_json_report(EVALUATION_REPORT)
drift = load_json_report(DRIFT_REPORT)
graph = load_csv_report(GRAPH_REPORT)

status_label = "Healthy" if health and health.get("model_ready") else "Unavailable"
model_version = health.get("model_version") if health else None

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("Stored alerts", f"{int(summary['total_alerts']):,}")
kpi2.metric("Loaded for analysis", f"{int(summary['loaded_alerts']):,}")
kpi3.metric("Average alert risk", f"{float(summary['average_risk']):.3f}")
kpi4.metric("Reviewed", f"{int(summary['reviewed']):,}", format_percent(float(summary["review_rate"])))
kpi5.metric("API / model", status_label, model_version or "No model version")

if health_error:
    st.warning(f"API health is unavailable: {health_error}")
if total_alerts > len(alerts_raw):
    st.info(f"Analytics use the latest {len(alerts_raw):,} of {total_alerts:,} stored alerts.")

overview_tab, alerts_tab, investigation_tab, model_tab, operations_tab, risk_tab = st.tabs(
    ["Overview", "Alerts", "Investigation", "Model performance", "Operations", "Graph & drift"]
)

with overview_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("Alert volume over time")
        if alerts.empty or alerts["created_at"].isna().all():
            st.info("No alert timestamps are available yet.")
        else:
            daily = (
                alerts.dropna(subset=["created_at"])
                .assign(day=lambda df: df["created_at"].dt.floor("D"))
                .groupby("day")
                .size()
                .reset_index(name="alerts")
                .sort_values("day")
            )
            st.plotly_chart(
                px.line(daily, x="day", y="alerts", markers=True, labels={"day": "Date", "alerts": "Alerts"}),
                use_container_width=True,
            )
    with right:
        st.subheader("Alert risk distribution")
        if alerts.empty:
            st.info("No alert scores are available yet.")
        else:
            st.plotly_chart(
                px.histogram(alerts, x="risk_score", nbins=20, labels={"risk_score": "Risk score"}),
                use_container_width=True,
            )

    left, right = st.columns(2)
    with left:
        st.subheader("Top reason codes")
        reasons = reason_counts(alerts_raw).head(12)
        if reasons.empty:
            st.info("No reason codes are available yet.")
        else:
            st.plotly_chart(
                px.bar(reasons.sort_values("count"), x="count", y="reason_code", orientation="h", labels={"count": "Alerts", "reason_code": "Reason"}),
                use_container_width=True,
            )
    with right:
        st.subheader("Analyst outcomes")
        if alerts.empty:
            st.info("No analyst outcomes are available yet.")
        else:
            outcomes = alerts["analyst_outcome"].fillna("unreviewed").value_counts().reset_index()
            outcomes.columns = ["outcome", "count"]
            st.plotly_chart(px.pie(outcomes, names="outcome", values="count", hole=0.45), use_container_width=True)

    st.subheader("Risk by payment format")
    if alerts.empty or alerts["payment_format"].dropna().empty:
        st.info("Payment-format analytics become available after alerts contain transaction payloads.")
    else:
        payment = (
            alerts.dropna(subset=["payment_format"])
            .groupby("payment_format")
            .agg(alerts=("alert_id", "count"), average_risk=("risk_score", "mean"))
            .reset_index()
            .sort_values("alerts", ascending=False)
        )
        st.dataframe(payment, use_container_width=True, hide_index=True)

with alerts_tab:
    st.subheader("Alert explorer")
    if alerts.empty:
        st.info("No alerts have been generated.")
    else:
        filter1, filter2, filter3, filter4 = st.columns(4)
        min_risk = filter1.slider("Minimum risk", 0.0, 1.0, float(max(0.0, alerts["risk_score"].min())), 0.01)
        outcome_options = ["All", "Unreviewed"] + sorted(alerts["analyst_outcome"].dropna().astype(str).unique().tolist())
        outcome = filter2.selectbox("Analyst outcome", outcome_options)
        bank_options = ["All"] + sorted(alerts["from_bank"].dropna().astype(str).unique().tolist())
        from_bank = filter3.selectbox("Sender bank", bank_options)
        search = filter4.text_input("Transaction or account")

        filtered = alerts[alerts["risk_score"] >= min_risk].copy()
        if outcome == "Unreviewed":
            filtered = filtered[filtered["analyst_outcome"].isna()]
        elif outcome != "All":
            filtered = filtered[filtered["analyst_outcome"] == outcome]
        if from_bank != "All":
            filtered = filtered[filtered["from_bank"].astype(str) == from_bank]
        if search:
            needle = search.lower()
            search_columns = ["transaction_id", "from_account", "to_account", "alert_id"]
            mask = pd.Series(False, index=filtered.index)
            for column in search_columns:
                mask |= filtered[column].fillna("").astype(str).str.lower().str.contains(needle, regex=False)
            filtered = filtered[mask]

        st.caption(f"Showing {len(filtered):,} matching alerts")
        display_columns = [
            "created_at", "alert_id", "transaction_id", "risk_score", "threshold", "amount_paid",
            "payment_currency", "payment_format", "from_bank", "to_bank", "reason_text", "analyst_outcome",
        ]
        st.dataframe(filtered[display_columns], use_container_width=True, hide_index=True)
        st.download_button(
            "Download filtered alerts CSV",
            data=filtered[display_columns].to_csv(index=False).encode("utf-8"),
            file_name="aegisaml_filtered_alerts.csv",
            mime="text/csv",
        )

with investigation_tab:
    st.subheader("Alert investigation")
    if alerts.empty:
        st.info("Generate an alert before using the investigation workspace.")
    else:
        alert_ids = alerts["alert_id"].astype(str).tolist()
        selected_id = st.selectbox("Select alert", alert_ids)
        selected = alerts.loc[alerts["alert_id"].astype(str) == selected_id].iloc[0]

        top1, top2, top3, top4 = st.columns(4)
        top1.metric("Risk score", f"{selected['risk_score']:.4f}")
        top2.metric("Threshold", f"{selected['threshold']:.4f}")
        top3.metric("Amount", f"{selected.get('amount_paid', 0) or 0:,.2f} {selected.get('payment_currency') or ''}")
        top4.metric("Model version", str(selected["model_version"]))

        detail_left, detail_right = st.columns(2)
        with detail_left:
            st.markdown("**Transaction route**")
            st.write(f"{selected.get('from_bank')} / {selected.get('from_account')} → {selected.get('to_bank')} / {selected.get('to_account')}")
            st.markdown("**Timestamp**")
            st.write(selected.get("timestamp") or selected.get("created_at"))
            st.markdown("**Payment format**")
            st.write(selected.get("payment_format") or "—")
        with detail_right:
            st.markdown("**Reason codes**")
            for reason in selected["reason_codes"] if isinstance(selected["reason_codes"], list) else []:
                st.code(reason)
            st.markdown("**Current outcome**")
            st.write(selected.get("analyst_outcome") or "Unreviewed")

        with st.expander("Raw transaction payload"):
            st.json(selected["payload"])

        st.markdown("### Analyst review")
        current_outcome = selected.get("analyst_outcome")
        current_label = OUTCOME_LABELS.get(current_outcome, "Unreviewed")
        st.caption(f"Current review status: **{current_label}**")

        outcome_options = list(OUTCOME_LABELS)
        default_index = outcome_options.index(current_outcome) if current_outcome in outcome_options else 0
        with st.form(f"feedback_form_{selected_id}", clear_on_submit=False):
            outcome = st.radio(
                "Investigation outcome",
                outcome_options,
                index=default_index,
                format_func=lambda value: OUTCOME_LABELS[value],
                horizontal=True,
            )
            notes = st.text_area(
                "Investigation notes",
                value=selected.get("analyst_notes") or "",
                placeholder="Record evidence reviewed, rationale, and next action.",
                max_chars=2000,
                height=140,
            )
            confirm = st.checkbox(
                "I confirm this review reflects the current investigation decision.",
                value=False,
            )
            save_review = st.form_submit_button(
                "Save analyst review",
                type="primary",
                use_container_width=True,
                disabled=not confirm,
            )

        if save_review:
            success, message = submit_feedback(selected_id, outcome, notes)
            if success:
                st.success(message)
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(message)

with model_tab:
    st.subheader("Offline model performance")
    if not evaluation:
        st.info(f"Evaluation report not found at `{EVALUATION_REPORT}`.")
    else:
        test = evaluation.get("metrics", {}).get("test", {})
        validation = evaluation.get("metrics", {}).get("validation", {})
        dataset = evaluation.get("dataset", {})
        cards = st.columns(6)
        cards[0].metric("Test PR-AUC", f"{test.get('average_precision', 0):.3f}")
        cards[1].metric("Test ROC-AUC", f"{test.get('roc_auc', 0):.3f}")
        cards[2].metric("Recall", format_percent(test.get("recall")))
        cards[3].metric("Precision", format_percent(test.get("precision")))
        cards[4].metric("Alert rate", format_percent(test.get("alert_rate")))
        cards[5].metric("Threshold", f"{test.get('threshold', 0):.4f}")

        st.caption(
            f"Model {evaluation.get('model_version', '—')} · {int(dataset.get('rows', 0)):,} rows · "
            f"laundering rate {format_percent(dataset.get('laundering_rate'))}"
        )
        comparison = pd.DataFrame(
            [
                {"split": "Validation", **{key: validation.get(key) for key in ["precision", "recall", "f1", "average_precision", "roc_auc", "alert_rate"]}},
                {"split": "Test", **{key: test.get(key) for key in ["precision", "recall", "f1", "average_precision", "roc_auc", "alert_rate"]}},
            ]
        )
        st.dataframe(comparison, use_container_width=True, hide_index=True)

        confusion = test.get("confusion_matrix", {})
        if confusion:
            st.markdown("### Test confusion matrix")
            matrix = pd.DataFrame(
                [[confusion.get("tn", 0), confusion.get("fp", 0)], [confusion.get("fn", 0), confusion.get("tp", 0)]],
                index=["Actual legitimate", "Actual laundering"],
                columns=["Predicted legitimate", "Predicted alert"],
            )
            st.dataframe(matrix, use_container_width=True)

        with st.expander("Training configuration and dataset metadata"):
            st.json(evaluation)

with operations_tab:
    st.subheader("Service health and runtime metrics")
    op1, op2, op3, op4 = st.columns(4)
    op1.metric("API health", status_label)
    op2.metric("Health latency", "—" if health_latency is None else f"{health_latency:.0f} ms")
    op3.metric("Model version", model_version or "—")
    request_count = metric_sum(prometheus, "aegis_score_requests_total")
    op4.metric("Score requests", f"{request_count:,.0f}")

    if prometheus:
        success = sum(value for name, value in prometheus.items() if name.startswith('aegis_score_requests_total') and 'status="success"' in name)
        errors = sum(value for name, value in prometheus.items() if name.startswith('aegis_score_requests_total') and 'status="error"' in name)
        feedback_total = metric_sum(prometheus, "aegis_feedback_total")
        p1, p2, p3 = st.columns(3)
        p1.metric("Successful scores", f"{success:,.0f}")
        p2.metric("Scoring errors", f"{errors:,.0f}")
        p3.metric("Feedback submissions", f"{feedback_total:,.0f}")
        with st.expander("Raw Prometheus metrics"):
            st.json(prometheus)
    else:
        st.info("Prometheus metrics are unavailable. Start the API and ensure `/metrics` is reachable.")

    st.markdown("### Configuration")
    st.code(
        f"AEGIS_DATABASE_URL={DATABASE_URL}\nAEGIS_API_URL={API_URL}\n"
        f"AEGIS_EVALUATION_REPORT={EVALUATION_REPORT}\nAEGIS_DRIFT_REPORT={DRIFT_REPORT}\n"
        f"AEGIS_GRAPH_REPORT={GRAPH_REPORT}"
    )

with risk_tab:
    graph_col, drift_col = st.columns(2)
    with graph_col:
        st.subheader("Account graph risk")
        if graph.empty:
            st.info(f"Graph report not found or empty at `{GRAPH_REPORT}`.")
        else:
            numeric_columns = graph.select_dtypes(include="number").columns.tolist()
            score_candidates = [name for name in numeric_columns if "risk" in name.lower() or "pagerank" in name.lower()]
            score_column = score_candidates[0] if score_candidates else (numeric_columns[0] if numeric_columns else None)
            if score_column:
                top_graph = graph.nlargest(20, score_column)
                st.dataframe(top_graph, use_container_width=True, hide_index=True)
            else:
                st.dataframe(graph.head(20), use_container_width=True, hide_index=True)
    with drift_col:
        st.subheader("Data drift")
        if not drift:
            st.info(f"Drift report not found at `{DRIFT_REPORT}`.")
        else:
            st.json(drift)
            st.caption("PSI ≥ 0.10 is a warning and PSI ≥ 0.25 is commonly treated as critical in this project configuration.")

st.divider()
st.caption(
    "Operational alert analytics describe only transactions that crossed the deployed threshold. "
    "Offline precision and recall come from the labeled evaluation report and should not be inferred from live alerts without analyst outcomes."
)
