"""BarrierLens dashboard: literature map and performance data of bio-based paper barrier coatings."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).parent / "data"

st.set_page_config(page_title="BarrierLens", page_icon="📄", layout="wide")


@st.cache_data
def load_data():
    papers = pd.read_csv(DATA / "papers_clustered.csv")
    perf = pd.read_csv(DATA / "performance_data.csv")
    return papers, perf


papers, perf = load_data()

st.title("BarrierLens")
st.markdown(
    "**A literature and data map of bio-based barrier coatings for paper packaging.** "
    "Which material and method best meet a given set of requirements, "
    "and which candidates are worth testing in the lab?"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Papers mapped", len(papers))
c2.metric("Research clusters", papers["cluster_name"].nunique())
c3.metric("Samples with performance data", len(perf))
c4.metric("Papers with extracted data", perf["doi"].nunique())

tab_map, tab_perf, tab_find, tab_about = st.tabs(
    ["Research landscape", "Performance data", "Candidate finder", "Method & limitations"]
)

# ---------------------------------------------------------------- landscape
with tab_map:
    st.subheader("Research landscape")
    st.caption(
        "Each point is a paper. Positions come from sentence embeddings of title + abstract, "
        "reduced to 2D with PCA (~15% of variance); clusters from K-Means (k = 5). "
        "The map shows broad research directions, not exact similarity."
    )
    clusters = sorted(papers["cluster_name"].unique())
    chosen = st.multiselect("Clusters", clusters, default=clusters)
    sub = papers[papers["cluster_name"].isin(chosen)]

    fig = px.scatter(
        sub, x="pc1", y="pc2", color="cluster_name",
        hover_name="title", hover_data={"year": True, "journal": True, "pc1": False, "pc2": False},
        labels={"cluster_name": "Cluster"}, height=550,
    )
    fig.update_traces(marker=dict(size=8, opacity=0.75))
    fig.update_layout(xaxis_title="PC1", yaxis_title="PC2", legend_title_text="")
    st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    with left:
        counts = sub["cluster_name"].value_counts().reset_index()
        counts.columns = ["Cluster", "Papers"]
        st.plotly_chart(
            px.bar(counts, x="Papers", y="Cluster", orientation="h", title="Papers per cluster"),
            width="stretch",
        )
    with right:
        yearly = sub.dropna(subset=["year"]).groupby(["year", "cluster_name"]).size().reset_index(name="Papers")
        yearly = yearly[yearly["year"] >= 2005]
        st.plotly_chart(
            px.line(yearly, x="year", y="Papers", color="cluster_name", markers=True,
                    title="Papers per year (since 2005)", labels={"cluster_name": "", "year": "Year"}),
            width="stretch",
        )

    with st.expander("Browse papers"):
        st.dataframe(
            sub[["year", "title", "journal", "cluster_name", "cited_by", "doi"]]
            .sort_values("cited_by", ascending=False),
            width="stretch", hide_index=True,
            column_config={"doi": st.column_config.LinkColumn("DOI")},
        )

# ---------------------------------------------------------------- performance
with tab_perf:
    st.subheader("Performance data from published studies")
    st.caption(
        "Values extracted from open-access papers; every value is linked to its table or figure "
        "(`source_location`). Values read from figures are approximate (see notes)."
    )
    f1, f2 = st.columns(2)
    sel_papers = f1.multiselect("Papers", sorted(perf["paper_short"].unique()),
                                default=sorted(perf["paper_short"].unique()))
    show_controls = f2.checkbox("Show uncoated controls", value=True)
    p = perf[perf["paper_short"].isin(sel_papers)]
    if not show_controls:
        p = p[p["bio_based"] != "control"]

    left, right = st.columns(2)
    with left:
        kit = p.dropna(subset=["kit", "coating_weight_gsm"])
        fig = px.scatter(
            kit, x="coating_weight_gsm", y="kit", color="paper_short",
            hover_name="sample_id", hover_data=["base_material", "additive"],
            labels={"coating_weight_gsm": "Coat weight (g/m²)", "kit": "KIT rating (higher = better)",
                    "paper_short": ""},
            title="Grease resistance vs coat weight",
        )
        fig.update_traces(marker=dict(size=11, opacity=0.8))
        fig.update_layout(legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig, width="stretch")
    with right:
        conds = sorted(p["wvtr_conditions"].dropna().unique())
        if conds:
            cond = st.selectbox("WVTR test condition (only compare within one condition)", conds)
            w = p[(p["wvtr_conditions"] == cond) & p["wvtr"].notna()].copy()
            w["label"] = w["sample_id"] + " · " + w["paper_short"].str.split(" \\(").str[0]
            fig = px.bar(
                w.sort_values("wvtr"), x="wvtr", y="label", orientation="h",
                color="base_material", hover_data=["additive", "coating_weight_gsm"],
                labels={"wvtr": "WVTR (g/m²·day, lower = better)", "label": "", "base_material": ""},
                title="Water vapour transmission rate",
            )
            fig.update_layout(legend=dict(orientation="h", y=-0.3), height=500)
            st.plotly_chart(fig, width="stretch")

    st.dataframe(p, width="stretch", hide_index=True)
    st.download_button("Download performance data (CSV)", perf.to_csv(index=False),
                       "performance_data.csv", "text/csv")

# ---------------------------------------------------------------- candidate finder
with tab_find:
    st.subheader("Candidate finder")
    st.markdown(
        "Set your requirements. Each sample is checked against every requirement: "
        "**met**, **failed**, or **unknown** (no data reported). "
        "Unknown is not treated as failed. Ranking: fewest failed → most met → lowest coat weight."
    )
    r1, r2, r3, r4 = st.columns(4)
    kit_min = r1.slider("Min. KIT rating", 0, 12, 8)
    ca_min = r2.slider("Min. water contact angle (°)", 0, 120, 90)
    cw_max = r3.slider("Max. coat weight (g/m²)", 1, 25, 10)
    wvtr_max = r4.slider("Max. WVTR (g/m²·day)", 10, 1500, 100, step=10)
    s1, s2 = st.columns(2)
    cond_options = sorted(perf["wvtr_conditions"].dropna().str.split(" \\(").str[0].unique())
    default_cond = cond_options.index("23 C, 50% RH") if "23 C, 50% RH" in cond_options else 0
    wvtr_cond = s1.selectbox("WVTR condition", cond_options, index=default_cond)
    allow_partial = s2.checkbox("Include partially bio-based coatings", value=True)

    bio = ("yes", "partial") if allow_partial else ("yes",)
    cand = perf[perf["bio_based"].str.startswith(bio)].copy()

    def check(value, op, limit):
        if pd.isna(value):
            return None
        return bool(value >= limit) if op == ">=" else bool(value <= limit)

    def evaluate(row):
        wvtr_ok = None
        if str(row["wvtr_conditions"]).startswith(wvtr_cond):
            wvtr_ok = check(row["wvtr"], "<=", wvtr_max)
        return pd.Series({
            "KIT": check(row["kit"], ">=", kit_min),
            "WVTR": wvtr_ok,
            "Contact angle": check(row["water_contact_angle_deg"], ">=", ca_min),
            "Coat weight": check(row["coating_weight_gsm"], "<=", cw_max),
        })

    checks = cand.apply(evaluate, axis=1)
    ok_cols = list(checks.columns)
    cand = pd.concat([cand, checks], axis=1)
    cand["met"] = (cand[ok_cols] == True).sum(axis=1)  # noqa: E712
    cand["failed"] = (cand[ok_cols] == False).sum(axis=1)  # noqa: E712
    cand["unknown"] = cand[ok_cols].isna().sum(axis=1)
    ranked = cand.sort_values(["failed", "met", "coating_weight_gsm"], ascending=[True, False, True])

    symbol = {True: "✅", False: "❌", None: "❔"}
    view = ranked.copy()
    for c in ok_cols:
        view[c] = view[c].map(lambda v: symbol.get(v, "❔"))
    full = ranked[(ranked["failed"] == 0) & (ranked["unknown"] == 0)]
    if len(full):
        st.success(f"{len(full)} sample(s) meet all requirements with complete data: "
                   + ", ".join(full["sample_id"] + " (" + full["paper_short"] + ")"))
    else:
        st.warning("No sample meets all requirements with complete data. Try relaxing a requirement.")

    st.dataframe(
        view[["paper_short", "sample_id", "base_material", "additive", *ok_cols,
              "kit", "wvtr", "water_contact_angle_deg", "coating_weight_gsm", "met", "failed", "unknown"]],
        width="stretch", hide_index=True,
    )
    st.caption("A candidate is a sample worth testing in the lab, not a proven best material.")

# ---------------------------------------------------------------- about
with tab_about:
    st.subheader("Method")
    st.markdown(
        """
1. **Collect:** OpenAlex API, 7 material-specific queries (chitosan, starch, alginate, proteins,
   nanocellulose, wax, lignin/hemicellulose), top 100 results each → 566 unique papers.
2. **Screen:** title + abstract must mention *paper*, *coating* and a *barrier property*
   (relaxed rule for papers without abstract); 2 manual exclusions → 191 papers.
3. **Map:** `all-MiniLM-L6-v2` embeddings, K-Means (k = 5, chosen by silhouette score and
   interpretability), PCA for the 2D view.
4. **Extract:** performance values from open-access full texts, each linked to its table or figure.
"""
    )
    st.subheader("Limitations")
    st.markdown(
        """
- Test conditions differ between papers (WVTR at 23 °C / 50% RH vs 38 °C / 90% RH; Cobb at 60, 120 or 1800 s).
  Compare values only within one condition.
- Some values were read from figures and are approximate.
- OpenAlex open-access flags were not always accurate; paywalled papers were replaced.
- Clusters overlap (silhouette ≈ 0.05); labels are approximate.
- Data extraction was AI-assisted and manually spot-checked against the source PDFs.
"""
    )
    st.markdown(
        "Code and data: [github.com/nazrin-shahpalang/BarrierLens]"
        "(https://github.com/nazrin-shahpalang/BarrierLens) · "
        "Author: [Nazrin Shahpalangova](https://www.linkedin.com/in/nazrin-shahpalangova-72834a396)"
    )