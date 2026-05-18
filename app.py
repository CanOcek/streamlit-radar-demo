from __future__ import annotations

import base64
import sys
from pathlib import Path
from typing import Any

import streamlit as st

from retrieval_core.financial_retrieval import get_indicator

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ASSETS_DIR = PROJECT_ROOT / "ui" / "assets"
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
    retrieve_related_context,
    retrieve_financial_context
)
from retrieval_core.retrieval_utils import get_db_connection  # noqa: E402
from shared.settings import get_setting  # noqa: E402
from ui_presets import PRESET_CATEGORIES, PRESET_COMPANIES  # noqa: E402


DEFAULT_CATEGORY_OPTIONS = [
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
SOURCE_TYPE_OPTIONS = [
    "webpages",
    "pdfs",
    "northdata_publications",
    "northdata_events",
]
DIRECTION_OPTIONS = ["opportunity", "neutral", "risk"]
CONFIDENCE_OPTIONS = ["high", "medium", "low"]
SIGNAL_STRENGTH_OPTIONS = ["strong", "medium", ""]
CHUNK_SCOPE_OPTIONS = ["webpage_chunk", "pdf_chunk"]


st.set_page_config(page_title="Business Development Radar", layout="wide")


def _img_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()

def inject_button_styles() -> None:
    st.markdown(
        """
        <style>
        div.stButton > button {
            padding: 0.12rem 0.65rem !important;
            font-size: 0.80rem !important;
            border-radius: 8px !important;
            min-height: 2.10rem !important;
            line-height: 1.0 !important;
            white-space: nowrap !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_sidebar_branding() -> None:
    pntn_html = ""
    tum_html = ""

    if PNTN_LOGO.exists():
        pntn_b64 = _img_to_base64(PNTN_LOGO)
        pntn_html = f'<img src="data:image/png;base64,{pntn_b64}" style="width:60px; display:block;">'

    if TUM_LOGO.exists():
        tum_b64 = _img_to_base64(TUM_LOGO)
        tum_html = f'<img src="data:image/png;base64,{tum_b64}" style="width:80px; display:block;">'

    st.markdown(
        f"""
        <div style="
            display:flex;
            align-items:flex-start;
            gap:4px;
            margin-top:-10px;
            margin-bottom:0px;
        ">
            {pntn_html}
            {tum_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    if not require_password():
        return
    inject_button_styles()
    st.title("Business Development Radar")
    st.caption("Choose companies and categories from the sidebar, retrieve evidence, and generate a synthesis.")

    db_options, db_error = load_filter_options()
    if db_error:
        st.warning(f"Could not load live filter options from Postgres: {db_error}")

    with st.sidebar:
        render_sidebar_branding()

        st.header("Selection")
        scope_companies, scope_categories = render_scope_controls(db_options)
        effective_companies, effective_categories = effective_scope_values(
            scope_companies=scope_companies,
            scope_categories=scope_categories,
            db_options=db_options,
        )

        st.divider()

        filters = render_filter_controls(
            db_options=db_options,
            scope_companies=effective_companies,
            scope_categories=effective_categories,
        )

        include_raw_content = st.toggle(
            "Include full raw text content",
            value=False,
        )

        st.divider()

        strategy = render_strategy_control()

        evidence_limit = st.slider(
            "Evidence limit",
            min_value=1,
            max_value=300,
            value=50,
            step=1,
        )

        min_vector_similarity = st.slider(
            "Minimum vector similarity",
            min_value=0.0,
            max_value=1.0,
            value=0.25,
            step=0.01,
            disabled=strategy == "Exact metadata fetch",
        )

        options = RetrievalOptions(
            limit=evidence_limit,
            min_vector_similarity=min_vector_similarity,
            include_raw_content=include_raw_content,
        )

    vector_queries = render_vector_controls(strategy)
    if not effective_companies or not effective_categories:
        st.session_state.pop("retrieval_rows", None)
        st.session_state.pop("stage1_signals", None)
        st.session_state.pop("stage2_result", None)
        st.session_state.pop("related_companies", None)
        st.session_state.pop("related_persons", None)
        st.session_state.pop("financials", None)  # add this


    rows = st.session_state.get("retrieval_rows", [])
    signals = st.session_state.get("stage1_signals", [])
    can_synthesize = bool(signals)

    btn_col1, btn_col2, _ = st.columns([1.05, 1.20, 3.75], gap="small")

    with btn_col1:
        retrieve_clicked = st.button("Get Evidence", type="primary")

    with btn_col2:
        synthesize_clicked = st.button(
            "Run LLM2 Synthesis",
            type="primary" if can_synthesize else "secondary",
        )


    if retrieve_clicked:
        retrieve_evidence(
            filters=filters,
            vector_queries=vector_queries,
            options=options,
            scope_companies=effective_companies,
            scope_categories=effective_categories,
        )
        st.rerun()

    retrieval_status_message = st.session_state.pop("retrieval_status_message", None)
    if retrieval_status_message:
        st.success(retrieval_status_message)

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
    company_options = preset_or_database_options(
        preset_values=PRESET_COMPANIES,
        database_values=db_options.get("companies") or [],
    )
    category_options = preset_or_database_options(
        preset_values=PRESET_CATEGORIES,
        database_values=all_category_options(db_options),
    )
    companies = st.multiselect(
        "Companies",
        company_options,
        placeholder="Leave empty to use all visible companies",
    )
    categories = st.multiselect(
        "Categories",
        category_options,
        placeholder="Leave empty to use all visible categories",
    )
    return companies or [], categories


def effective_scope_values(
    scope_companies: list[str],
    scope_categories: list[str],
    db_options: dict[str, list[str]],
) -> tuple[list[str], list[str]]:
    company_options = preset_or_database_options(
        preset_values=PRESET_COMPANIES,
        database_values=db_options.get("companies") or [],
    )
    category_options = preset_or_database_options(
        preset_values=PRESET_CATEGORIES,
        database_values=all_category_options(db_options),
    )
    companies = scope_companies or company_options
    categories = scope_categories or category_options
    return companies, categories


def all_category_options(db_options: dict[str, list[str]]) -> list[str]:
    return sorted(set(DEFAULT_CATEGORY_OPTIONS + (db_options.get("categories") or [])))


def preset_or_database_options(
    preset_values: list[str],
    database_values: list[str],
) -> list[str]:
    cleaned_presets = unique_nonempty_values(preset_values)
    if cleaned_presets:
        return cleaned_presets
    return unique_nonempty_values(database_values)


def unique_nonempty_values(values: list[str]) -> list[str]:
    seen = set()
    cleaned = []
    for value in values:
        value = (value or "").strip()
        if value and value not in seen:
            cleaned.append(value)
            seen.add(value)
    return cleaned


def render_strategy_control() -> str:
    st.markdown("### Retrieval")
    return st.radio(
        "Strategy",
        [
            "Exact metadata fetch",
            "Single vector query",
            "Multi-query vector search",
        ],
        help=(
            "Exact fetch returns all matching LLM1 signals without ranking.\n\n"
            "Vector modes rank by similarity to the search query over selected fields.\n\n"
            "Vector search is most useful with a large dataset, and exact fetch with filtering."
        ),
    )


def render_filter_controls(
    db_options: dict[str, list[str]],
    scope_companies: list[str],
    scope_categories: list[str],
) -> RetrievalFilters:
    signal_strengths = st.multiselect(
        "Signal strength",
        SIGNAL_STRENGTH_OPTIONS,
        default=["strong", "medium"],
        format_func=lambda value: value or "noise",
        help="Noise signals don't have LLM1 results",
    )

    directions = st.multiselect(
        "Direction",
        DIRECTION_OPTIONS,
        default=[],
    )

    confidences = st.multiselect(
        "Confidence",
        CONFIDENCE_OPTIONS,
        default=[],
    )

    include_secondary = st.checkbox(
        "Include secondary categories",
        value=True,
        help="Turn off to only retrieve results based on the primary category",
    )

    return RetrievalFilters(
        companies=scope_companies or None,
        categories=scope_categories or None,
        include_secondary_categories=include_secondary,
        secondary_categories=None,
        page_type=None,
        signal_strength=signal_strengths or None,
        direction=directions or None,
        confidence=confidences or None,
        source_types=SOURCE_TYPE_OPTIONS,
    )


def render_vector_controls(strategy: str) -> list[VectorQuerySpec]:
    if strategy == "Exact metadata fetch":
        return []

    st.subheader("Vector Search")
    if strategy == "Single vector query":
        with st.container(border=True):
            query = st.text_input("Query", placeholder="Example: Changes in Management, AI Agent development opportunities")
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
                placeholder="Example: New business developments",
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
        related_context = retrieve_related_context(scope_companies)
        financial_context = retrieve_financial_context(scope_companies)

    st.session_state["retrieval_rows"] = rows
    st.session_state["stage1_signals"] = retrieval_rows_to_stage1_signals(rows)
    st.session_state["related_companies"] = related_context.related_companies
    st.session_state["related_persons"] = related_context.related_persons
    st.session_state["financials"] = financial_context.financials
    st.session_state.pop("stage2_result", None)
    limit_status = "Evidence limit reached." if len(rows) >= options.limit else "Evidence limit not reached."
    st.session_state["retrieval_status_message"] = (
        f"Retrieved {len(rows)} evidence row(s). {limit_status}"
    )


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


def render_workspace(
    rows: list[dict[str, Any]],
    signals,
    result: dict[str, Any] | None,
    scope_companies: list[str],
    scope_categories: list[str],
) -> None:
    if not scope_companies or not scope_categories:
        return

    related_companies = st.session_state.get("related_companies", [])
    related_persons = st.session_state.get("related_persons", [])
    financials = st.session_state.get("financials", [])

    if not rows and result is None:
        if not related_companies and not related_persons:  # add financials
            return

    tab_overview, tab_findings, tab_evidence, tab_company_info, tab_financials = st.tabs(
        ["Overview", "Findings", "Evidence", "Company Structure", "Financials"]
    )

    with tab_overview:
        render_overview(result)
        if "Legal & C-Level Updates" in scope_categories:
            render_company_structure_preview(related_companies, related_persons)
        if "Financials" in scope_categories:
            render_financial_context_preview(financials)
    with tab_findings:
        render_findings(result)
    with tab_evidence:
        render_evidence_rows(rows)
    with tab_company_info:
        render_company_info(related_companies, related_persons)
    with tab_financials:                            # new tab
        render_financial_context_preview(financials)


def _parse_roles_json(roles_data: Any) -> list[dict[str, Any]]:
    """Parse roles data which might be a string or list."""
    import json
    
    if isinstance(roles_data, str):
        try:
            return json.loads(roles_data)
        except (json.JSONDecodeError, TypeError):
            return []
    elif isinstance(roles_data, list):
        return roles_data
    return []


def _get_relationship_description(subject: str, related: str, group: str, direction: str) -> str:
    """Get human-readable description based on group and direction."""
    relationship_map = {
        ("Succession", "Source"): (related, "is the former (older) entity of", subject),
        ("Succession", "Target"): (related, "is the successor of", subject),
        ("Merger", "Source"):     (related, "is the selling entity in a merger with", subject),
        ("Merger", "Target"):     (related, "is the buying entity acquiring", subject),
        ("Control", "Source"):    (related, "controls", subject),
        ("Control", "Target"):    (subject, "controls", related),
        ("Interest", "Source"):   (subject, "owns a stake in", related),
        ("Interest", "Target"):   (related, "owns a stake in", subject),
        ("Personal", "Source"):   (subject, "holds a personal role at", related),
        ("Personal", "Target"):   (related, "holds a personal role at", subject),
    }
    parts = relationship_map.get((group, direction))
    if parts:
        a, verb, b = parts
        return f"{a} {verb} {b}"
    return f"{related} is related to {subject}"

def _render_roles_display(roles: Any, company_name: str, related_to: str) -> None:
    roles_list = _parse_roles_json(roles)

    if not roles_list:
        st.caption("No detailed role information available.")
        return

    for idx, role in enumerate(roles_list):
        if not isinstance(role, dict):
            continue

        role_name = role.get("name", "Unknown")
        role_type = role.get("type", "")
        date_val = role.get("date", "")
        shares_percent = role.get("sharesPercent")

        line_parts = [f"**{role_name}**"]
        if role_type and role_type != role_name:
            line_parts.append(f" · {role_type}")

        st.markdown("".join(line_parts))

        meta_parts = []
        if date_val:
            meta_parts.append(f"Date: {date_val}")
        if shares_percent is not None:
            meta_parts.append(f"Ownership: {shares_percent}%")

        if meta_parts:
            st.caption(" | ".join(meta_parts))

        if idx < len(roles_list) - 1:
            st.markdown("---")

def render_company_structure_preview(
    related_companies: list,
    related_persons: list,
) -> None:
    st.subheader("Company Structure Preview")

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Related Companies", len(related_companies))
    with c2:
        st.metric("Related Persons", len(related_persons))

    if related_companies:
        st.markdown("**Top related companies**")
        for related_to, company_name, company_url, description, status, roles in related_companies[:2]:
            roles_list = _parse_roles_json(roles)
            first_role = ""
            if roles_list:
                first_valid_role = next((r for r in roles_list if isinstance(r, dict)), None)
                if first_valid_role:
                    first_role = first_valid_role.get("name", "")

            with st.container(border=True):
                st.markdown(f"**{company_name}**")
                if status:
                    info_pill(status, bg="#1f6f43")
                if first_role:
                    info_pill(first_role, bg="#30363d")

    if related_persons:
        st.markdown("**Top related persons**")
        for related_to, full_name, description, roles in related_persons[:2]:
            with st.container(border=True):
                st.markdown(f"**{full_name}**")
                if description:
                    info_pill(description, bg="#30363d")

    if not related_companies and not related_persons:
        st.info("No company structure information available.")



def render_financial_context_preview(financials: list[tuple[str, Any]]) -> None:
    st.subheader("Financial Data")

    if not financials:
        st.info("No financial data available.")
        return

    # Filter out companies with no financials data
    financials_with_data = [(name, data) for name, data in financials if data is not None]

    if not financials_with_data:
        st.info("No financial data available for selected companies.")
        return

    for company_name, financials_json in financials_with_data:
        if not financials_json:
            continue

        # financials_json is a list of snapshots; take the most recent
        snapshot = financials_json[0] if isinstance(financials_json, list) and len(financials_json) > 0 else financials_json if isinstance(financials_json, dict) else None

        if not snapshot:
            continue

        items = snapshot.get("items", []) if isinstance(snapshot, dict) else []
        date = snapshot.get("date", "") if isinstance(snapshot, dict) else ""
        period = date[:4] if date else "N/A"  # e.g. "2025" from "2025-12-31"

        revenue = get_indicator(items, "Revenue")
        earnings = get_indicator(items, "Earnings")
        equity = get_indicator(items, "Equity")
        return_on_sales = get_indicator(items, "ReturnOnSales")
        employees = get_indicator(items, "Employees")

        with st.container(border=True):
            st.markdown(f"**{company_name}** · FY{period}")
            k1, k2, k3, k4, k5 = st.columns(5)
            with k1:
                st.metric("Revenue", revenue or "—")
            with k2:
                st.metric("Earnings", earnings or "—")
            with k3:
                st.metric("Equity", equity or "—")
            with k4:
                st.metric("Return on Sales", return_on_sales or "—")
            with k5:
                st.metric("Employees", employees or "—")


def is_legal_category_selected(scope_categories: list[str]) -> bool:
    normalized = {(c or "").replace("&amp;", "&").strip() for c in scope_categories}
    return "Legal & C-Level Updates" in normalized

def render_overview(result: dict[str, Any] | None) -> None:
    if not result:
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

def info_pill(text: str, bg: str = "#2f3542", color: str = "#ffffff") -> None:
    st.markdown(
        f"""
        <span style="
            display:inline-block;
            padding:4px 10px;
            border-radius:999px;
            background:{bg};
            color:{color};
            font-size:12px;
            font-weight:600;
            margin-right:6px;
            margin-bottom:6px;
        ">
            {text}
        </span>
        """,
        unsafe_allow_html=True,
    )


def render_company_info_summary(related_companies: list, related_persons: list) -> None:
    st.subheader("Company Structure Snapshot")

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Related Companies", len(related_companies))
    with c2:
        st.metric("Related Persons", len(related_persons))

def render_company_info(related_companies: list, related_persons: list) -> None:
    render_company_info_summary(related_companies, related_persons)
    st.markdown("")

    # -------------------------
    # Related Companies
    # -------------------------
    st.subheader("Related Companies")
    if not related_companies:
        st.info("No related companies found.")
    else:
        for related_to, company_name, company_url, description, status, roles in related_companies:
            roles_list = _parse_roles_json(roles)
            first_role = ""
            first_date = ""

            if roles_list:
                first_valid_role = next((r for r in roles_list if isinstance(r, dict)), None)
                if first_valid_role:
                    first_role = first_valid_role.get("name", "")
                    first_date = first_valid_role.get("date", "")

            with st.container(border=True):
                st.markdown(f"### {company_name}")
                st.caption(f"Relationship to {related_to}")

                meta_col1, meta_col2, meta_col3 = st.columns([1, 1.2, 2])

                with meta_col1:
                    if status:
                        info_pill(status, bg="#1f6f43")

                with meta_col2:
                    if first_role:
                        info_pill(first_role, bg="#30363d")

                with meta_col3:
                    if first_date:
                        st.caption(f"Date: {first_date}")

                if company_url:
                    st.markdown(f"[Open source link]({company_url})")

                if description:
                    st.markdown(f"**Description:** {description}")

                if roles_list:
                    with st.expander("Show relationship details"):
                        _render_roles_display(roles, company_name, related_to)
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    st.markdown("")

    # -------------------------
    # Related Persons
    # -------------------------
    st.subheader("Related Persons")
    if not related_persons:
        st.info("No related persons found.")
    else:
        for related_to, full_name, description, roles in related_persons:
            roles_list = _parse_roles_json(roles)
            first_date = ""

            if roles_list:
                first_valid_role = next((r for r in roles_list if isinstance(r, dict)), None)
                if first_valid_role:
                    first_date = first_valid_role.get("date", "")

            with st.container(border=True):
                st.markdown(f"### {full_name}")
                st.caption(f"Relationship to {related_to}")

                meta_col1, meta_col2 = st.columns([2, 2])

                with meta_col1:
                    if description:
                        info_pill(description, bg="#30363d")
                        st.markdown(f"**Role:** {description}")

                with meta_col2:
                    if first_date:
                        st.caption(f"Date: {first_date}")

                if roles_list:
                    with st.expander("Show role details"):
                        _render_roles_display(roles, full_name, related_to)
st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

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
            _write_text_block("Full raw content", row.get("raw_content"))


def render_category_summary(rows: list[dict[str, Any]]) -> None:
    summary_rows = build_category_summary(rows)
    if not summary_rows:
        return

    st.markdown("**Category Counts for Retrieved Results**")
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
                    UNION
                    SELECT DISTINCT COALESCE(NULLIF(source_name, ''), 'northdata_publication') AS page_type
                    FROM northdata_publications
                    UNION
                    SELECT DISTINCT COALESCE(NULLIF(type, ''), 'northdata_event') AS page_type
                    FROM northdata_events
                    ORDER BY page_type
                    """
                )
                page_types = [row[0] for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT DISTINCT unnest(secondary_categories) AS secondary_category
                    FROM source_enrichments
                    WHERE secondary_categories IS NOT NULL
                    ORDER BY secondary_category
                    """
                )
                secondary_categories = [row[0] for row in cur.fetchall() if row[0]]
            return {
                "companies": companies,
                "categories": categories,
                "page_types": page_types,
                "secondary_categories": secondary_categories,
            }, None
        finally:
            conn.close()
    except Exception as exc:
        return {
            "companies": [],
            "categories": [],
            "page_types": [],
            "secondary_categories": [],
        }, str(exc)


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


if __name__ == "__main__":
    main()
