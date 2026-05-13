from retrieval_core import RelatedContext
from shared.db import get_db_connection


def retrieve_related_context(companies: list[str]) -> RelatedContext:
    """Retrieve related companies and persons for the given scope companies.

    Args:
        companies: List of company names to fetch related data for.

    Returns:
        RelatedContext containing related companies and persons tuples.
    """
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT related_to, company_name, company_url, description, status, roles
                    FROM northdata_related_companies
                    WHERE related_to = ANY(%s)
                    ORDER BY related_to, company_name
                """, (companies,))
                related_companies = cur.fetchall()

                cur.execute("""
                    SELECT related_to, full_name, description, roles
                    FROM northdata_related_persons
                    WHERE related_to = ANY(%s)
                    ORDER BY related_to, full_name
                """, (companies,))
                related_persons = cur.fetchall()

            return RelatedContext(
                related_companies=related_companies or [],
                related_persons=related_persons or []
            )
        finally:
            conn.close()
    except Exception:
        return RelatedContext(related_companies=[], related_persons=[])
