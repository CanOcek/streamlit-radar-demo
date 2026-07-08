# New file: financial_retrieval.py

import logging

from .retrieval_models import FinancialContext
from shared.db import get_db_connection

log = logging.getLogger(__name__)


def retrieve_financial_context(companies: list[str]) -> FinancialContext:
    """Retrieve financial data for the given companies from northdata_companies.

    Fetches the financials JSONB column which contains a list of financial
    snapshots, each with a date, top-level items, and historical entries.

    Args:
        companies: List of company names to fetch financial data for.

    Returns:
        FinancialContext containing (company_name, financials) tuples.
    """
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT company_name, financials
                    FROM northdata_companies
                    WHERE company_name = ANY(%s)
                      AND financials IS NOT NULL
                    ORDER BY company_name
                """, (companies,))
                financials = cur.fetchall()

            return FinancialContext(financials=financials or [])
        finally:
            conn.close()
    except Exception:
        log.exception("Failed to retrieve North Data financial context")
        return FinancialContext(financials=[])


def get_indicator(items: list[dict], indicator_id: str) -> str | None:
    """Extract a formattedValue from a financials items list by indicator id."""
    return next(
        (item["formattedValue"] for item in items if item["id"] == indicator_id),
        None
    )
