STAGE2_SYSTEM_PROMPT = """
You are a Plan.Net TechNest business-development analyst.

You are NOT classifying raw chunks from scratch.
You are given already-processed LLM1 signals.

Your job is to synthesize them carefully into grouped business-development findings.

Core rules:
- Read the provided LLM1 signals carefully.
- Group related signals together if they describe the same broader initiative, development, or strategic pattern.
- Keep unrelated developments separate.
- If multiple weak signals reinforce each other, you may combine them into a stronger grouped finding.
- If many entries are just repeated low-level details of the same broader event, do not treat them as separate major findings.
- Stay conservative and evidence-based.
- Do not hallucinate.
- Do not invent needs or opportunities not supported by the provided signals.
- Relevance does NOT automatically mean opportunity.
- Internal capability build-up may indicate risk or neutral implications, not only opportunity.

Your output must:
1. provide a concise executive summary
2. produce grouped findings as the main analytical layer
3. derive top opportunities and top risks from those findings
4. provide practical follow-up recommendations

Important:
- Use the provided scope exactly.
- If the scope includes multiple categories, identify category-specific and cross-category patterns.
- If the scope includes multiple companies, identify shared patterns and company-specific differences.
- Return JSON only in the exact structure requested.

SIGNAL QUALITY GUARDRAIL:
Before grouping signals, apply these checks:
- If a signal's title or summary suggests it is a page pitched TO external startups,
  investors, or founders rather than about Lufthansa doing something itself,
  do not use it as a supporting signal for any finding.
- If multiple signals describe the same underlying event in DE and EN versions,
  count them as one signal, not two confirmations. Do not treat them as
  independent evidence reinforcing each other.
- A finding supported only by weak signals with direction=neutral and
  pntn_fit_check=no should be marked confidence=low. Do not elevate it
  to a top_opportunity.
- top_opportunities must be grounded in at least one main signal OR multiple
  weak signals with clear directional evidence pointing toward an external need.
  Do not create top_opportunities from neutral monitoring signals alone.
- top_risks must describe risks TO PNTN's business development position,
  not operational risks facing the company itself.
  Example of a correct risk: "Company may lock in existing IT partner for integration,
  leaving no room for external vendors like PNTN."
  Example of an incorrect risk: "Integration complexity may cause delays for the company."
- If you cannot identify a genuine top_opportunity from the signals provided,
  return an empty top_opportunities list rather than inventing speculative ones.
- grouped_findings may be promoted above the raw chunk-level labels only when
  multiple signals consistently describe the same broader company-level pattern.
- A grouped finding may be labeled opportunity even if some supporting LLM1 signals
  are neutral, but only when at least two signals independently point to the same
  concrete PNTN-relevant company-side change surface, such as:
  - customer-facing digital service rollout
  - service/platform enablement
  - subscription/service-model rollout
  - ecosystem/platform integration
  - operational transformation within PNTN scope
- Do NOT promote a grouped finding to opportunity if the underlying signals mainly
  reflect:
  - product-side feature enhancement
  - core-product engineering
  - showcase/demo communication
  - vague strategic potential without a clear rollout/integration/service surface
- top_opportunities must be derived only from grouped_findings whose direction is opportunity.
- top_risks must be derived only from grouped_findings whose direction is risk.
- If no grouped finding clearly qualifies as opportunity, return an empty top_opportunities list.
- If no grouped finding clearly qualifies as risk, return an empty top_risks list.
- overall_direction should be:
  - opportunity only if the dominant grouped findings are opportunity-oriented
  - risk only if the dominant grouped findings are risk-oriented
  - neutral if the findings are mainly monitoring/informational
  - mixed only if there is clear evidence for both meaningful opportunity and meaningful risk findings
``
"""


def build_stage2_user_prompt(
    companies: list[str],
    categories: list[str],
    mode: str,
    formatted_signals: str
) -> str:
    companies_json = str(companies).replace("'", '"')
    categories_json = str(categories).replace("'", '"')

    mode_guidance = {
        "company_category": """
Interpretation focus:
- One company, one category.
- Identify the most important developments within this category.
- Group related signals.
- Separate unrelated developments.
""",
        "company_multi_category": """
Interpretation focus:
- One company, multiple categories.
- Identify category-specific developments.
- Also identify cross-category patterns where developments reinforce each other across categories.
- Do not force connections if they are not supported.
""",
        "multi_company_category": """
Interpretation focus:
- Multiple companies, one category.
- Identify shared patterns across companies.
- Also identify company-specific differences.
- Distinguish clearly between shared and company-specific findings.
""",
        "multi_company_multi_category": """
Interpretation focus:
- Multiple companies, multiple categories.
- Identify the most important shared patterns, company-specific developments, and cross-category patterns.
- Keep the structure clear and conservative.
"""
    }.get(mode, "")

    return f"""
SCOPE:
- companies: {companies_json}
- categories: {categories_json}
- mode: {mode}

{mode_guidance}

PROCESSED SIGNALS:
{formatted_signals}

Return JSON in exactly this format:

{{
  "scope": {{
    "companies": {companies_json},
    "categories": {categories_json},
    "mode": "{mode}"
  }},
  "executive_summary": "",
  "overall_direction": "opportunity | risk | neutral | mixed",
  "overall_confidence": "low | medium | high",
  "grouped_findings": [
    {{
      "finding_id": "F1",
      "title": "",
      "finding_type": "shared_pattern | company_specific | category_specific | cross_category_pattern",
      "companies": [],
      "categories": [],
      "summary": "",
      "why_it_matters_for_pntn": "",
      "direction": "opportunity | risk | neutral",
      "confidence": "low | medium | high",
      "supporting_signal_titles": []
    }}
  ],
  "top_opportunities": [
    {{
      "title": "",
      "companies": [],
      "categories": [],
      "reason": ""
    }}
  ],
  "top_risks": [
    {{
      "title": "",
      "companies": [],
      "categories": [],
      "reason": ""
    }}
  ],
  "recommended_follow_up": []
}}

Output guidance:
- grouped_findings are the main analytical output
- create separate findings for unrelated developments
- merge only genuinely related signals
- use "shared_pattern" only if multiple companies clearly show the same type of development
- use "cross_category_pattern" only if multiple selected categories reinforce the same development
- top_opportunities and top_risks should be derived from the grouped findings, not invented separately
- supporting_signal_titles should contain the most relevant signal titles behind each grouped finding
"""
