# New file: financial_retrieval.py
from streamlit import logger

from .retrieval_models import FinancialContext, PatentEntry, PatentsContext, TrademarksContext, TrademarkEntry
from shared.db import get_db_connection


def retrieve_patent_context(companies: list[str]) -> PatentsContext:
    """Retrieve patent data for the given companies from northdata_events."""

    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT company_name, description, date
                    FROM northdata_events
                    WHERE company_name = ANY(%s)
                    AND type = 'Patent'
                    ORDER BY company_name
                """, (companies,))
                patents = cur.fetchall()

            return PatentsContext(patents=[PatentEntry(*patent) for patent in patents])
        finally:
            conn.close()
    except Exception:
        return PatentsContext(patents=[])

def retrieve_trademark_context(companies: list[str]) -> TrademarksContext:
    """Retrieve trademark data for the given companies from northdata_events."""

    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT company_name, description, date
                    FROM northdata_events
                    WHERE company_name = ANY(%s)
                    AND type = 'Trademark'
                    ORDER BY company_name
                """, (companies,))
                trademarks = cur.fetchall()

            return TrademarksContext(trademarks=[TrademarkEntry(*trademark) for trademark in trademarks])
        finally:
            conn.close()
    except Exception:
        return TrademarksContext(trademarks=[])
