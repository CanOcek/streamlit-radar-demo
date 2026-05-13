from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ASSETS_DIR = PROJECT_ROOT / "assets"
PNTN_LOGO = ASSETS_DIR / "pntn_logo.png"
TUM_LOGO = ASSETS_DIR / "tum_logo.png"

from LLM_stage2 import (  # noqa: E402
    retrieval_rows_to_stage1_signals,
    run_stage2_from_signals,
)
from retrieval_core import (  # noqa: E402
    RetrievalFilters,
    RetrievalOptions,
    VectorQuerySpec,
    retrieve_for_llm2,
)
from retrieval_core.retrieval_utils import get_db_connection  # noqa: E402
from shared.settings import get_setting  # noqa: E402


CATEGORY_OPTIONS = [
    "Financials",
    "News / Products",
    "Partnerships / Acquisitions",
    "Hiring",
    "Innovative Themes",
    "Legal & C-Level Updates",
]
ENRICHMENT_FIELD_OPTIONS = {
    "all": "All enrichment fields",
    "short_summary": "Short summary",
    "evidence": "Evidence",
    "why_it_matters_for_pntn": "Why it matters",
    "possible_business_suggestion": "Business suggestion",
}
SOURCE_TYPE_OPTIONS = ["webpages", "pdfs"]
BUCKET_OPTIONS = ["main", "weak"]
DIRECTION_OPTIONS = ["opportunity", "neutral", "risk"]
CONFIDENCE_OPTIONS = ["high", "medium", "low"]
SIGNAL_STRENGTH_OPTIONS = ["strong", "medium", ""]
CHUNK_SCOPE_OPTIONS = ["webpage_chunk", "pdf_chunk"]


st.set_page_config(page_title="Business Development Radar", layout="wide")

def render_header() -> None:
    logo_col1, logo_col2, logo_col3 = st.columns([1.5, 3, 1])

    with logo_col1:
        if PNTN_LOGO.exists():
            st.image(str(PNTN_LOGO), width=180)

    with logo_col3:
        if TUM_LOGO.exists():
            st.image(str(TUM_LOGO), width=110)

def main() -> None:
    if not require_password():
        return
    render_header()
    st.title("Business Development Radar")
    st.caption("DB-backed LLM1 evidence retrieval and LLM2 synthesis")

    db_options, db_error = load_filter_options()
    if db_error:
        st.warning(f"Could not load live filter options from Postgres: {db_error}")

    with st.sidebar:
        st.header("Scope")
        scope_companies, scope_categories = render_scope_controls(db_options)
        st.divider()
        strategy = render_strategy_control()
        filters = render_filter_controls(
            db_options=db_options,
            scope_companies=scope_companies,
            scope_categories=scope_categories,
        )
        st.divider()
        options = RetrievalOptions(
            limit=st.slider("Evidence limit", min_value=1, max_value=300, value=100, step=1),
            include_raw_content=st.toggle(
                "Include raw full content in evidence rows",
                value=False,
            ),
        )

    vector_queries = render_vector_controls(strategy)
    effective_companies, effective_categories = effective_scope_values(
        scope_companies=scope_companies,
        scope_categories=scope_categories,
        db_options=db_options,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        retrieve_clicked = st.button("Retrieve Evidence", type="primary")
    with col2:
        synthesize_clicked = st.button("Run LLM2 Synthesis")

    if retrieve_clicked:
        retrieve_evidence(
            filters=filters,
            vector_queries=vector_queries,
            options=options,
            scope_companies=scope_companies,
            scope_categories=scope_categories,
        )

    rows = st.session_state.get("retrieval_rows", [])
    signals = st.session_state.get("stage1_signals", [])

    if synthesize_clicked:
        if not signals:
            st.warning("No retrieved evidence is available. Retrieve evidence first.")
        else:
            run_stage2_analysis(
                signals=signals,
                scope_companies=effective_companies,
                scope_categories=effective_categories,
                include_secondary=filters.include_secondary_categories,
            )

    result = st.session_state.get("stage2_result")
    render_workspace(
        rows=rows,
        signals=signals,
        result=result,
        scope_companies=effective_companies,
        scope_categories=effective_categories,
    )


def require_password() -> bool:
    app_password = get_setting("APP_PASSWORD")
    if not app_password:
        st.error("APP_PASSWORD is not configured for this app.")
        st.stop()

    if st.session_state.get("authenticated"):
        return True

    render_header()
    with st.form("login"):
        st.subheader("Business Development Radar")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Enter")

    if submitted:
        if password == app_password:
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Incorrect password.")

    return False


def render_scope_controls(db_options: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    companies = st.multiselect(
        "Companies",
        db_options.get("companies") or [],
        placeholder="Choose one or more companies",
    )
    categories = st.multiselect(
        "Categories",
        sorted(set(CATEGORY_OPTIONS + db_options.get("categories", []))),
        placeholder="Choose one or more categories",
    )
    return companies or [], categories


def effective_scope_values(
    scope_companies: list[str],
    scope_categories: list[str],
    db_options: dict[str, list[str]],
) -> tuple[list[str], list[str]]:
    companies = scope_companies or db_options.get("companies") or []
    categories = scope_categories or sorted(set(CATEGORY_OPTIONS + db_options.get("categories", [])))
    return companies, categories


def render_strategy_control() -> str:
    st.header("Retrieval")
    return st.radio(
        "Strategy",
        [
            "Exact metadata fetch",
            "Single vector query",
            "Multi-query vector search",
        ],
        help=(
            "Exact fetch returns matching LLM1 signals without embeddings. "
            "Vector modes rank by similarity and dedupe repeated source/PDF-segment hits."
        ),
    )


def render_filter_controls(
    db_options: dict[str, list[str]],
    scope_companies: list[str],
    scope_categories: list[str],
) -> RetrievalFilters:
    st.subheader("Metadata Filters")
    include_secondary = st.checkbox(
        "Match selected categories against secondary categories",
        value=False,
    )
    source_types = st.multiselect(
        "Source types",
        SOURCE_TYPE_OPTIONS,
        default=SOURCE_TYPE_OPTIONS,
    )
    page_types = st.multiselect(
        "Page types",
        db_options.get("page_types") or [],
        placeholder="Leave empty for all page types",
    )

    st.subheader("LLM1 Result Filters")
    buckets = st.multiselect("Buckets", BUCKET_OPTIONS, default=BUCKET_OPTIONS)
    relevance_choice = st.selectbox(
        "Relevance",
        ["Relevant only", "Relevant and non-relevant", "Non-relevant only"],
        index=0,
    )
    directions = st.multiselect("Direction", DIRECTION_OPTIONS, default=[])
    confidences = st.multiselect("Confidence", CONFIDENCE_OPTIONS, default=[])
    signal_strengths = st.multiselect(
        "Signal strength",
        SIGNAL_STRENGTH_OPTIONS,
        default=[],
        format_func=lambda value: value or "weak",
    )
    secondary_categories = st.text_input(
        "Additional secondary category filter",
        placeholder="Comma-separated secondary categories",
    )

    return RetrievalFilters(
        companies=scope_companies or None,
        categories=scope_categories or None,
        include_secondary_categories=include_secondary,
        secondary_categories=_csv(secondary_categories),
        page_type=page_types or None,
        buckets=buckets or None,
        is_relevant=_relevance_value(relevance_choice),
        signal_strength=signal_strengths or None,
        direction=directions or None,
        confidence=confidences or None,
        source_types=source_types or None,
    )


def render_vector_controls(strategy: str) -> list[VectorQuerySpec]:
    st.subheader("Vector Search")
    if strategy == "Exact metadata fetch":
        st.info("This strategy skips embeddings and retrieves filtered LLM1 signals.")
        return []

    if strategy == "Single vector query":
        with st.container(border=True):
            query = st.text_input("Query", placeholder="Example: new platform rollout")
            return [_render_vector_spec(query=query, key_prefix="single")]

    st.caption("Each query can target different enrichment fields and chunk embeddings.")
    spec_count = st.number_input("Query count", min_value=2, max_value=5, value=2, step=1)
    specs = []
    for idx in range(int(spec_count)):
        with st.container(border=True):
            st.markdown(f"**Query {idx + 1}**")
            query = st.text_input(
                "Query text",
                key=f"multi_query_{idx}",
                placeholder="Example: new business development",
            )
            specs.append(_render_vector_spec(query=query, key_prefix=f"multi_{idx}"))
    return specs


def _render_vector_spec(query: str, key_prefix: str) -> VectorQuerySpec:
    fields = st.multiselect(
        "LLM1 vector fields",
        list(ENRICHMENT_FIELD_OPTIONS.keys()),
        default=list(ENRICHMENT_FIELD_OPTIONS.keys()),
        format_func=lambda value: ENRICHMENT_FIELD_OPTIONS[value],
        key=f"{key_prefix}_fields",
    )
    include_chunks = st.checkbox(
        "Search by Raw Text Embeddings",
        value=False,
        key=f"{key_prefix}_chunks",
    )

    chunk_scopes = CHUNK_SCOPE_OPTIONS
    include_noise = False
    require_chunk_enrichment = True
    if include_chunks:
        chunk_scopes = st.multiselect(
            "Chunk scopes",
            CHUNK_SCOPE_OPTIONS,
            default=CHUNK_SCOPE_OPTIONS,
            key=f"{key_prefix}_chunk_scopes",
        )
        include_noise = st.checkbox(
            "Include noise chunk results",
            value=False,
            key=f"{key_prefix}_noise",
        )

    return VectorQuerySpec(
        query=query,
        enrichment_fields=fields,
        include_chunk_embeddings=include_chunks,
        include_normal=bool(fields or include_chunks),
        include_noise=include_noise,
        chunk_scopes=chunk_scopes or CHUNK_SCOPE_OPTIONS,
        require_chunk_enrichment=require_chunk_enrichment,
    )


def retrieve_evidence(
    filters: RetrievalFilters,
    vector_queries: list[VectorQuerySpec],
    options: RetrievalOptions,
    scope_companies: list[str],
    scope_categories: list[str],
) -> None:
    with st.spinner("Retrieving LLM1 evidence from Postgres..."):
        rows = retrieve_for_llm2(
            filters=filters,
            vector_queries=vector_queries,
            options=options,
        )

    st.session_state["retrieval_rows"] = rows
    st.session_state["stage1_signals"] = retrieval_rows_to_stage1_signals(rows)
    st.session_state.pop("stage2_result", None)
    limit_status = "Evidence limit reached." if len(rows) >= options.limit else "Evidence limit not reached."
    st.success(f"Retrieved {len(rows)} evidence row(s). {limit_status}")


def run_stage2_analysis(
    signals,
    scope_companies: list[str],
    scope_categories: list[str],
    include_secondary: bool,
) -> None:
    with st.spinner("Running LLM2 synthesis..."):
        result = run_stage2_from_signals(
            signals=signals,
            companies=scope_companies,
            categories=scope_categories,
            include_secondary=include_secondary,
        )
    st.session_state["stage2_result"] = result
    st.success("LLM2 synthesis complete.")


def render_workspace(
    rows: list[dict[str, Any]],
    signals,
    result: dict[str, Any] | None,
    scope_companies: list[str],
    scope_categories: list[str],
) -> None:
    if not rows and result is None:
        st.info("Choose a scope, retrieve evidence, then run LLM2 synthesis.")
        return

    tab_overview, tab_findings, tab_evidence = st.tabs(
        ["Overview", "Findings", "Evidence"]
    )

    with tab_overview:
        render_overview(result)
    with tab_findings:
        render_findings(result)
    with tab_evidence:
        render_evidence_rows(rows)


def render_overview(result: dict[str, Any] | None) -> None:
    if not result:
        st.info("Run LLM2 synthesis to see the overview.")
        return

    st.subheader("Executive Summary")
    st.write(result.get("executive_summary", ""))

    col1, col2, col3 = st.columns(3)
    col1.metric("Overall Direction", result.get("overall_direction", "-"))
    col2.metric("Overall Confidence", result.get("overall_confidence", "-"))
    col3.metric("Signal Count", result.get("_meta", {}).get("signal_count", "-"))

    st.subheader("Recommended Follow-Up")
    follow_up = result.get("recommended_follow_up", [])
    if follow_up:
        for item in follow_up:
            st.markdown(f"- {item}")
    else:
        st.info("No follow-up recommendations available.")


def render_findings(result: dict[str, Any] | None) -> None:
    if not result:
        st.info("Run LLM2 synthesis to see grouped findings.")
        return

    st.subheader("Grouped Findings")
    render_grouped_findings(result.get("grouped_findings", []))

    col1, col2 = st.columns(2)
    with col1:
        render_list_block("Top Opportunities", result.get("top_opportunities", []))
    with col2:
        render_list_block("Top Risks", result.get("top_risks", []))


def render_evidence_rows(rows: list[dict[str, Any]]) -> None:
    st.subheader("Underlying LLM1 Evidence")
    if not rows:
        st.info("No retrieved evidence available.")
        return

    render_category_summary(rows)
    st.markdown("**All Fetched Results**")
    st.dataframe(
        format_table_columns([_table_row(row) for row in rows]),
        use_container_width=True,
        hide_index=True,
    )
    for row in rows:
        title = row.get("title") or row.get("heading") or "Untitled"
        with st.expander(f"{row.get('company') or '-'} - {title}"):
            col1, col2, col3 = st.columns([1, 1, 3])
            with col1:
                badge(row.get("bucket") or "-", bucket_color(row.get("bucket") or ""))
            with col2:
                badge(row.get("direction") or "-", direction_color(row.get("direction") or ""))
            with col3:
                st.markdown(f"**Category:** {row.get('category') or '-'}")

            st.markdown(f"**Date:** {row.get('date') or '-'}")
            st.markdown(f"**Source:** {row.get('raw_url') or '-'}")
            st.caption(
                " | ".join(
                    [
                        f"source_id={row.get('source_id') or '-'}",
                        f"enrichment_id={row.get('enrichment_id') or '-'}",
                        f"pdf_segment_id={row.get('pdf_segment_id') or '-'}",
                        f"retrieval_source={row.get('retrieval_source') or '-'}",
                    ]
                )
            )
            _write_text_block("Short summary", row.get("short_summary"))
            _write_text_block("Evidence", row.get("evidence"))
            _write_text_block("Why it matters for PNTN", row.get("why_it_matters_for_pntn"))
            _write_text_block("Possible business suggestion", row.get("possible_business_suggestion"))


def render_category_summary(rows: list[dict[str, Any]]) -> None:
    summary_rows = build_category_summary(rows)
    if not summary_rows:
        return

    st.markdown("**Category Counts**")
    st.dataframe(
        format_table_columns(summary_rows),
        use_container_width=True,
        hide_index=True,
        height=240,
    )


def build_category_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        company = row.get("company") or ""
        primary_category = row.get("category") or ""
        secondary_categories = row.get("secondary_categories") or []

        categories = []
        if primary_category:
            categories.append(primary_category)
        for category in secondary_categories:
            if category and category not in categories:
                categories.append(category)

        for category in categories:
            key = (company, category)
            item = summary.setdefault(
                key,
                {
                    "company name": company,
                    "category": category,
                    "primary_count": 0,
                    "total_count": 0,
                },
            )
            item["total_count"] += 1
            if category == primary_category:
                item["primary_count"] += 1

    return sorted(
        summary.values(),
        key=lambda item: (
            item["company name"].lower(),
            item["category"].lower(),
        ),
    )


def format_table_columns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {_readable_column_name(key): value for key, value in row.items()}
        for row in rows
    ]


def _readable_column_name(name: str) -> str:
    readable = name.replace("_", " ")
    return readable[:1].upper() + readable[1:]


def render_grouped_findings(findings: list[dict[str, Any]]) -> None:
    if not findings:
        st.info("No grouped findings available.")
        return

    for finding in findings:
        with st.expander(f"{finding.get('finding_id', '')} - {finding.get('title', 'Untitled')}"):
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                badge(finding.get("direction", "-"), direction_color(finding.get("direction", "")))
            with col2:
                st.markdown(f"**Confidence:** {finding.get('confidence', '-')}")
            with col3:
                st.markdown(f"**Categories:** {', '.join(finding.get('categories', []))}")
            st.markdown("**Summary**")
            st.write(finding.get("summary", ""))
            st.markdown("**Why it matters for PNTN**")
            st.write(finding.get("why_it_matters_for_pntn", ""))
            titles = finding.get("supporting_signal_titles", [])
            if titles:
                st.markdown("**Supporting signals**")
                for title in titles:
                    st.markdown(f"- {title}")


def render_list_block(title: str, items: list[dict[str, Any]]) -> None:
    st.subheader(title)
    if not items:
        st.info(f"No {title.lower()} available.")
        return
    for item in items:
        st.markdown(f"**{item.get('title', 'Untitled')}**")
        if item.get("reason"):
            st.write(item["reason"])
        st.markdown("---")


def badge(text: str, bg_color: str) -> None:
    st.markdown(
        f"""
        <span style="
            background-color:{bg_color};
            color:white;
            padding:4px 10px;
            border-radius:12px;
            font-size:12px;
            font-weight:600;
            display:inline-block;
            margin-right:6px;
            margin-bottom:4px;
        ">
            {text}
        </span>
        """,
        unsafe_allow_html=True,
    )


def direction_color(direction: str) -> str:
    value = (direction or "").strip().lower()
    if value == "opportunity":
        return "#2E8B57"
    if value == "risk":
        return "#B22222"
    return "#6c757d"


def bucket_color(bucket: str) -> str:
    if bucket == "main":
        return "#1f77b4"
    if bucket == "weak":
        return "#ff9800"
    return "#6c757d"


@st.cache_data(ttl=60)
def load_filter_options() -> tuple[dict[str, list[str]], str | None]:
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT company
                    FROM (
                        SELECT company FROM webpages
                        UNION
                        SELECT company FROM pdfs
                    ) companies
                    WHERE company IS NOT NULL AND company <> ''
                    ORDER BY company
                    """
                )
                companies = [row[0] for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT DISTINCT category
                    FROM source_enrichments
                    WHERE category IS NOT NULL AND category <> ''
                    ORDER BY category
                    """
                )
                categories = [row[0] for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT DISTINCT page_type
                    FROM webpages
                    WHERE page_type IS NOT NULL AND page_type <> ''
                    ORDER BY page_type
                    """
                )
                page_types = [row[0] for row in cur.fetchall()]
            return {
                "companies": companies,
                "categories": categories,
                "page_types": page_types,
            }, None
        finally:
            conn.close()
    except Exception as exc:
        return {"companies": [], "categories": [], "page_types": []}, str(exc)


def _table_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "company": row.get("company"),
        "title": row.get("title") or row.get("heading"),
        "date": row.get("date"),
        "bucket": row.get("bucket"),
        "category": row.get("category"),
        "direction": row.get("direction"),
        "confidence": row.get("confidence"),
        "similarity": row.get("best_similarity"),
        "matched_with": matched_with(row),
        "source_type": row.get("source_type"),
        "page_type": row.get("page_type"),
        "url": row.get("raw_url"),
        "source_id": row.get("source_id"),
        "enrichment_id": row.get("enrichment_id"),
        "pdf_segment_id": row.get("pdf_segment_id"),
    }


def matched_with(row: dict[str, Any]) -> str | None:
    matched_fields = row.get("matched_fields") or []
    if not matched_fields:
        return None

    best_match = matched_fields[0]
    return best_match.get("field_name") or best_match.get("retrieval_source")


def _write_text_block(title: str, value: str | None) -> None:
    if not value:
        return
    st.markdown(f"**{title}**")
    st.write(value)


def _csv(value: str) -> list[str] | None:
    values = [item.strip() for item in value.split(",") if item.strip()]
    return values or None


def _relevance_value(choice: str) -> bool | None:
    if choice == "Relevant only":
        return True
    if choice == "Non-relevant only":
        return False
    return None


if __name__ == "__main__":
    main()
