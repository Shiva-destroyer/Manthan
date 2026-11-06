"""Streamlit dashboard — one multi-page app for all three modules (PRD §6.4).

Single dashboard tech for everything (the blueprint's Textual/FastAPI/Streamlit
split is collapsed to one). Launched via ``manthan dashboard``; needs the
``[dashboard]`` extra. Kept import-light so the package imports without Streamlit.
"""

from __future__ import annotations

import os
from pathlib import Path


def _default_db() -> str:
    return os.environ.get("MANTHAN_RESULTS_DB", "data/results/manthan.db")


def main() -> None:  # pragma: no cover - requires streamlit + a populated DB
    import streamlit as st

    from manthan.core.report.heatmap import render_heatmap
    from manthan.core.store.db import Store

    st.set_page_config(page_title="Manthan", layout="wide")
    st.title("Manthan — churn · measure · harden")
    st.caption("Runtime cost: ₹0 / $0 — fully local, offline, CPU-only.")

    db = st.sidebar.text_input("Results DB", _default_db())
    if not Path(db).exists():
        st.warning(f"No results DB at {db}. Run `manthan run all --smoke` first.")
        return
    store = Store(db)
    campaigns = store.campaigns()
    if not campaigns:
        st.info("No campaigns yet.")
        return
    labels = {f"{c['label'] or c['id'][:8]} ({c['domain']})": c["id"] for c in campaigns}
    choice = st.sidebar.selectbox("Campaign", list(labels))
    cid = labels[choice]

    tab_overview, tab_prompt, tab_agent, tab_rag, tab_cross = st.tabs(
        ["Overview", "Prompt", "Agent", "RAG", "Cross-domain"]
    )
    metrics = store.metrics_for_campaign(cid)
    with tab_overview:
        st.subheader("Findings")
        findings = store.findings_for_campaign(cid)
        st.metric("Findings", len(findings))
        st.metric("Successes", sum(1 for f in findings if f["success"]))
    for tab, dom in ((tab_prompt, "prompt"), (tab_agent, "agent"), (tab_rag, "rag")):
        with tab:
            rows = [m for m in metrics if (m["run_domain"] or "") == dom]
            for m in rows:
                st.write(f"**{m['name']}** = {m['value']:.3f}")
    with tab_cross:
        st.subheader("OWASP × ATLAS coverage")
        st.iframe(render_heatmap(store.heatmap_counts(cid)), height=520)


if __name__ == "__main__":  # pragma: no cover
    main()
