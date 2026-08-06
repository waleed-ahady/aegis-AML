from __future__ import annotations

from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd


def build_graph_risk_report(frame: pd.DataFrame, output: str | Path | None = None) -> pd.DataFrame:
    """Rank accounts using network centrality, flow, reciprocity, and known-label exposure.

    This report is for investigation and feature research. Labels are included only in
    the offline report and are never used as online model inputs.
    """
    grouped = (
        frame.groupby(["from_account", "to_account"], observed=True)
        .agg(
            transaction_count=("amount_paid", "size"),
            total_amount=("amount_paid", "sum"),
            laundering_count=("is_laundering", "sum"),
        )
        .reset_index()
    )
    graph = nx.DiGraph()
    for row in grouped.itertuples(index=False):
        graph.add_edge(
            str(row.from_account),
            str(row.to_account),
            weight=float(row.total_amount),
            transaction_count=int(row.transaction_count),
            laundering_count=int(row.laundering_count),
        )

    if not graph:
        return pd.DataFrame()

    pagerank = nx.pagerank(graph, weight="weight")
    rows: list[dict[str, float | int | str]] = []
    for node in graph.nodes:
        outgoing = graph.out_edges(node, data=True)
        incoming = graph.in_edges(node, data=True)
        out_amount = sum(float(data["weight"]) for _, _, data in outgoing)
        in_amount = sum(float(data["weight"]) for _, _, data in incoming)
        out_count = sum(int(data["transaction_count"]) for _, _, data in outgoing)
        in_count = sum(int(data["transaction_count"]) for _, _, data in incoming)
        labelled = sum(
            int(data["laundering_count"])
            for _, _, data in list(graph.in_edges(node, data=True))
            + list(graph.out_edges(node, data=True))
        )
        reciprocal = sum(1 for target in graph.successors(node) if graph.has_edge(target, node))
        rows.append(
            {
                "account": node,
                "in_degree": graph.in_degree(node),
                "out_degree": graph.out_degree(node),
                "in_amount": in_amount,
                "out_amount": out_amount,
                "in_transaction_count": in_count,
                "out_transaction_count": out_count,
                "pagerank": pagerank.get(node, 0.0),
                "reciprocal_counterparties": reciprocal,
                "known_laundering_edges": labelled,
            }
        )

    report = pd.DataFrame(rows)
    score_columns = [
        "in_degree",
        "out_degree",
        "in_amount",
        "out_amount",
        "pagerank",
        "reciprocal_counterparties",
    ]
    for column in score_columns:
        values = (
            np.log1p(report[column].astype(float))
            if "amount" in column
            else report[column].astype(float)
        )
        std = values.std(ddof=0)
        report[f"z_{column}"] = (values - values.mean()) / std if std else 0.0
    report["network_risk_score"] = report[[f"z_{column}" for column in score_columns]].mean(axis=1)
    report = report.sort_values("network_risk_score", ascending=False).reset_index(drop=True)

    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(destination, index=False)
    return report
