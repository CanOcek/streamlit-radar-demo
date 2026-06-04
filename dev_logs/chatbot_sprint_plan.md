# AI Chatbot Sprint Plan

## Scope

This plan covers turning the Streamlit Radar Demo from a two-step analytical workflow
into a chat-assisted analyst app. The current dashboard should remain intact:

1. Sidebar scope and retrieval controls.
2. Evidence retrieval from Postgres and pgvector.
3. LLM2 synthesis into structured findings.
4. Tabbed display for takeaways, findings, evidence, company structure, financials,
   patents, and trademarks.

The chatbot should be added as a new conversational layer over the existing retrieval,
evidence, and synthesis system. The first target is not a fully autonomous agent. The
first target is source-grounded chat over retrieved evidence.

## Architecture Principles

- Keep `app.py` as UI glue. Do not put prompt construction, citation formatting, or
  chat orchestration directly into Streamlit rendering code.
- Keep retrieval/query code inside `retrieval_core/`.
- Add a small `chat_core/` package for chatbot-specific context construction,
  citation handling, prompt assembly, and LLM calls.
- Preserve the current dashboard workflow during the transition.
- Require evidence citations for analytical claims.
- Prefer answering from already retrieved evidence before running new retrieval.
- Say when evidence is insufficient instead of inventing missing facts.

## Sprint 1: Chat Over Retrieved Evidence

### Goal

Add a read-only chatbot that answers questions using only evidence that is already
loaded in `st.session_state`. This gives the app a conversational interface without
changing retrieval behavior or the LLM2 synthesis workflow.

### Implementation

Create a new package:

```text
chat_core/
├── __init__.py
├── citations.py
├── context.py
├── models.py
├── prompts.py
└── runner.py
```

Implement `chat_core/models.py`:

- Define a `ChatCitation` dataclass with fields:
  - `citation_id`
  - `company`
  - `title`
  - `url`
  - `source_id`
  - `enrichment_id`
  - `pdf_segment_id`
  - `retrieval_source`
  - `best_similarity`
- Define a `ChatEvidenceItem` dataclass with:
  - `citation`
  - `summary`
  - `evidence`
  - `why_it_matters_for_pntn`
  - `possible_business_suggestion`
  - `category`
  - `secondary_categories`
  - `direction`
  - `confidence`
  - `signal_strength`
  - `date`
- Define a `ChatContext` dataclass with:
  - `scope_companies`
  - `scope_categories`
  - `stage2_summary`
  - `grouped_findings`
  - `evidence_items`

Implement `chat_core/citations.py`:

- Convert retrieved rows into stable citation IDs such as `E1`, `E2`, `E3`.
- Keep the original row metadata available for source display.
- Format compact citation labels for prompt input.
- Format readable citations for UI output.

Implement `chat_core/context.py`:

- Build `ChatContext` from:
  - `st.session_state["retrieval_rows"]`
  - `st.session_state["stage2_result"]`
  - current scope companies
  - current scope categories
- Ignore rows without usable Stage2 body fields, matching existing
  `row_has_stage2_body(...)` behavior.
- Keep context compact. Do not include full raw content in the first version.

Implement `chat_core/prompts.py`:

- Add a system prompt for evidence-grounded business-development Q&A.
- Require answers to use citation IDs when making claims.
- Require the assistant to say when the loaded evidence is insufficient.
- Prevent the assistant from claiming it searched the database unless retrieval was
  actually run.

Implement `chat_core/runner.py`:

- Add `answer_from_current_evidence(...)`.
- Inputs:
  - user question
  - current chat history
  - `ChatContext`
- Output:
  - assistant answer text
  - cited evidence IDs detected or returned by the model
- Use `get_setting("OPEN_AI_API_KEY") or get_setting("OPENAI_API_KEY")`.
- Use the same default model source as existing LLM code.

Modify `app.py`:

- Add `st.session_state["chat_messages"]`.
- Render chat messages using `st.chat_message`.
- Add `st.chat_input`.
- Place the chat panel above the existing tabs or in a dedicated first tab.
- On user input:
  - append the user message
  - if no evidence rows exist, respond with a short message asking the user to retrieve evidence first
  - otherwise build `ChatContext`
  - call `answer_from_current_evidence(...)`
  - append assistant response
- Add a small "Clear chat" button.

### Acceptance Criteria

- A user can retrieve evidence, then ask a follow-up question in chat.
- The chatbot answers from retrieved rows only.
- The chatbot cites evidence IDs in the answer.
- If no evidence is loaded, the chatbot does not call the LLM and clearly says evidence must be retrieved first.
- Existing Evidence and Synthesis buttons still behave as before.
- Existing dashboard tabs still render.

### Independent and Recursive Testing

Run these checks independently after implementation, then repeat after each fix:

1. Static syntax check:
   - Compile all touched files with `python -m py_compile`.
2. No-evidence chat test:
   - Start the app.
   - Log in.
   - Ask a chat question before retrieving evidence.
   - Expected: no OpenAI call for evidence Q&A; UI says to retrieve evidence first.
3. Evidence-loaded chat test:
   - Select one company and one category.
   - Retrieve evidence.
   - Ask: "What is the strongest opportunity here?"
   - Expected: answer references loaded evidence and includes citation IDs.
4. Citation integrity test:
   - Confirm every cited ID appears in the loaded evidence context.
   - Confirm citation metadata includes title and source URL when available.
5. Regression test:
   - Run Evidence button.
   - Run Synthesis button.
   - Open all existing tabs.
   - Expected: no tab breaks, no session-state reset caused by chat.
6. Recursive retest:
   - If any test fails, fix the smallest relevant unit.
   - Re-run all previous tests, not only the failed one.

## Sprint 2: Context Ranking and Token Budgeting

### Goal

Make chat responses cheaper, faster, and more relevant by selecting the best subset
of loaded evidence for each user question.

### Implementation

Extend `chat_core/context.py`:

- Add `select_relevant_evidence(...)`.
- Rank evidence using simple deterministic signals:
  - company name mentioned in question
  - category mentioned in question
  - direction terms such as opportunity, risk, neutral
  - confidence terms such as high, medium, low
  - title or finding title overlap
  - evidence rows supporting current Stage2 findings
- Preserve original retrieval ranking as a fallback.

Add `chat_core/token_budget.py`:

- Count approximate or exact tokens using the existing `tiktoken` pattern from
  `LLM_stage2/token_budget.py`.
- Limit:
  - recent chat turns
  - Stage2 summary
  - grouped findings
  - evidence items
- Prefer keeping complete evidence items instead of truncating individual evidence
  text mid-item.

Update `chat_core/runner.py`:

- Pass only selected, budgeted context to the model.
- Include a context summary when many rows are omitted.
- Tell the model that omitted evidence is not visible for this answer.

Update `app.py`:

- Show a small caption after each assistant answer:
  - number of evidence items considered
  - number of evidence items omitted by budget

### Acceptance Criteria

- Chat can answer from a large retrieved result set without sending every row.
- Answers remain grounded in cited evidence.
- Questions mentioning a company/category/risk/opportunity bias toward matching rows.
- The UI displays how many evidence items were considered.

### Independent and Recursive Testing

1. Static syntax check over touched files.
2. Large-context test:
   - Retrieve 100+ rows if available.
   - Ask a focused question about one company.
   - Expected: selected evidence is a subset and contains matching company rows first.
3. Direction-ranking test:
   - Ask specifically about risks.
   - Expected: risk rows are preferred when present.
4. Budget-boundary test:
   - Temporarily set a low chat token limit.
   - Expected: complete evidence items are omitted, not partially mangled.
5. Citation test:
   - Expected: every citation ID in the answer exists in the selected context.
6. Recursive retest:
   - After any ranking or budget fix, repeat tests 2 through 5.

### Amendment: Retrieval Scope Synchronization

During Sprint 3 testing, a state-sync issue was found that belongs conceptually
after the Sprint 2 UI metadata work: chat-triggered retrieval successfully loaded
evidence for the assistant, but the dashboard tabs did not render the Evidence tab
when the sidebar scope was empty. The loaded rows existed in session state, but
`render_workspace(...)` still used the sidebar-selected scope as its visibility
gate.

Required amendment:

- Store the actual retrieval scope in session state whenever evidence is loaded:
  - `retrieval_scope_companies`
  - `retrieval_scope_categories`
- Use that stored retrieval scope when rendering dashboard tabs.
- Clear the stored retrieval scope when retrieval rows are cleared.
- Verify that both manual Evidence-button retrieval and chat-triggered retrieval
  show rows in the Evidence tab.

Regression test:

1. Clear chat and avoid selecting a sidebar scope.
2. Ask the assistant: "Find financial risks for Raiffeisen".
3. Confirm the assistant retrieves and answers from evidence.
4. Confirm the Evidence tab appears below the chat.
5. Open the Evidence tab and confirm the same retrieved rows are visible.

## Sprint 3: Natural-Language Retrieval From Chat

### Goal

Allow the chatbot to retrieve new evidence when the current loaded evidence is
missing or when the user asks a new scope/search question.

### Implementation

Add `chat_core/intents.py`:

- Classify each user message into one of:
  - `answer_from_loaded_evidence`
  - `retrieve_more_evidence`
  - `clarify_scope`
  - `summarize_current_result`
  - `run_structured_synthesis`
- Start with rules and simple model-assisted JSON classification only if rules are
  insufficient.

Add `chat_core/retrieval_planner.py`:

- Convert natural-language requests into:
  - `RetrievalFilters`
  - list of `VectorQuerySpec`
  - `RetrievalOptions`
- Use available companies and categories from existing `load_filter_options()`.
- Require clarification when:
  - no company can be inferred and no sidebar scope exists
  - no category can be inferred and no sidebar scope exists
  - the question is too broad for safe retrieval

Update `app.py`:

- On chat input, classify intent.
- If `retrieve_more_evidence`:
  - build retrieval plan
  - run `retrieve_for_llm2(...)`
  - apply existing Stage2 token budget
  - update `retrieval_rows` and `stage1_signals`
  - fetch related, financial, patent, and trademark context for planned companies
  - answer with a short retrieval summary and optionally a direct answer
- If `clarify_scope`:
  - ask one concise clarification question.

### Acceptance Criteria

- User can ask: "Find digital service opportunities for Epson."
- App runs retrieval without requiring manual sidebar setup.
- Retrieved rows appear in the existing Evidence tab.
- Chat explains what it retrieved.
- Ambiguous questions ask for clarification instead of running broad retrieval.

### Independent and Recursive Testing

1. Static syntax check.
2. Direct retrieval test:
   - Ask: "Find financial risks for Raiffeisen."
   - Expected: filters include company Raiffeisen and category Financials or a vector query based on the question.
3. Sidebar fallback test:
   - Select a company/category manually.
   - Ask: "What are the top risks?"
   - Expected: chat uses sidebar scope if message omits scope.
4. Ambiguity test:
   - Ask: "What should we do next?"
   - Expected: clarification or answer from current evidence, not broad database retrieval.
5. Evidence-tab sync test:
   - After chat retrieval, open Evidence tab.
   - Expected: newly retrieved rows are displayed.
6. Recursive retest:
   - After any planner fix, rerun direct retrieval, sidebar fallback, ambiguity, and tab sync tests.

## Sprint 4: Conversational Structured Synthesis

### Goal

Let users request structured synthesis through chat while preserving the existing
dashboard synthesis output.

### Implementation

Update `chat_core/intents.py`:

- Detect synthesis requests:
  - "Synthesize this"
  - "Create top opportunities"
  - "Compare these companies"
  - "Make a follow-up plan"

Update `app.py`:

- If intent is `run_structured_synthesis`:
  - ensure `stage1_signals` exist
  - call existing `run_stage2_from_signals(...)`
  - store result in `st.session_state["stage2_result"]`
  - add a chat response summarizing that the dashboard findings were updated
- If no signals exist, ask the user to retrieve evidence first.

Optionally update `LLM_stage2/prompts2.py` later:

- Remove source-specific examples that mention Lufthansa.
- Generalize guardrails so the chatbot and synthesis output feel aligned across
  all companies.

### Acceptance Criteria

- User can retrieve evidence through chat or sidebar, then ask chat to synthesize.
- Existing Findings and Key Takeaways tabs update with the new `stage2_result`.
- Chat confirms what scope was synthesized.
- Existing Synthesis button still works.

### Independent and Recursive Testing

1. Static syntax check.
2. Chat synthesis test:
   - Retrieve evidence.
   - Ask: "Synthesize this into opportunities and risks."
   - Expected: `stage2_result` updates and tabs render findings.
3. Button synthesis regression:
   - Use the existing Synthesis button.
   - Expected: same behavior as before.
4. Empty synthesis test:
   - Clear evidence.
   - Ask for synthesis.
   - Expected: chat asks to retrieve evidence first.
5. Recursive retest:
   - After any synthesis fix, repeat chat synthesis, button synthesis, and empty synthesis tests.

## Sprint 5: UI Integration and Demo Polish

### Goal

Make the chatbot feel like part of the product rather than an add-on while keeping
the existing dashboard usable for expert review.

### Implementation

Refine `app.py` layout:

- Keep sidebar filters.
- Put chat near the top of the workspace, before tabs, or add a dedicated
  "Assistant" tab as the first tab.
- Add quick action buttons:
  - "Explain top opportunity"
  - "Show supporting evidence"
  - "Compare selected companies"
  - "Suggest next steps"
- Add "Clear chat" and "Clear evidence" controls with clear scope.
- Show citations under assistant messages in a compact source list.

Improve display consistency:

- Keep citation labels stable within a retrieval session.
- Avoid resetting chat history when switching tabs.
- Clear chat only when explicitly requested.
- When evidence is replaced by chat retrieval, make that visible to the user.

### Acceptance Criteria

- A demo user can operate the app primarily through chat.
- Expert users can still use sidebar controls and dashboard tabs.
- Source citations are easy to inspect.
- Chat and dashboard state remain synchronized.
- The UI does not become cluttered on normal desktop viewport sizes.

### Independent and Recursive Testing

1. Static syntax check.
2. Desktop manual UI test:
   - Start app.
   - Retrieve evidence.
   - Chat.
   - Synthesize.
   - Inspect tabs.
   - Expected: no layout or state regressions.
3. Small viewport manual UI test:
   - Narrow browser width.
   - Expected: chat input, buttons, and tabs remain usable.
4. State persistence test:
   - Ask multiple chat questions.
   - Switch tabs.
   - Expected: chat history persists.
5. Clear controls test:
   - Clear chat.
   - Expected: evidence remains.
   - Clear evidence if implemented.
   - Expected: chat handles missing evidence gracefully.
6. Recursive retest:
   - After any layout or state fix, repeat desktop, small viewport, state persistence,
     and clear controls tests.

## Sprint 6: Hardening, Observability, and Final Validation

### Goal

Make the chatbot reliable enough for demos and future iteration.

### Implementation

Add robust error handling:

- Missing OpenAI key.
- OpenAI request failures.
- Invalid model responses.
- Empty retrieval results.
- Citation IDs returned by the model that are not in context.

Add lightweight observability:

- Store last chat retrieval plan in session state for debugging.
- Store evidence IDs considered for each answer.
- Display non-sensitive debug details behind an expander.
- Never print or expose secrets.

Add documentation:

- Update README or add a short dev note explaining:
  - how chatbot mode works
  - what it can and cannot answer
  - how citations are constructed
  - how to test manually

Optional Playwright MCP validation:

- Only run after user approval/details.
- Use it to inspect:
  - login flow
  - chat placement
  - retrieval and synthesis button flow
  - citation display
  - responsive layout

### Acceptance Criteria

- Chat failures show clear user-facing messages.
- No secrets are printed or rendered.
- Invalid citations are detected and suppressed or flagged.
- Manual validation confirms the end-to-end flow works.
- Documentation reflects the new behavior.

### Independent and Recursive Testing

1. Static syntax check.
2. Missing-key test:
   - Run without OpenAI key.
   - Expected: clear error message, no app crash.
3. Empty-result test:
   - Ask a retrieval query that returns no rows.
   - Expected: chat explains no evidence was found.
4. Invalid-citation test:
   - Simulate or mock an answer referencing an unknown citation ID.
   - Expected: citation is not displayed as valid.
5. End-to-end manual test:
   - Retrieve evidence.
   - Ask chat question.
   - Ask follow-up.
   - Run synthesis from chat.
   - Inspect evidence and findings tabs.
6. Recursive retest:
   - After any hardening fix, rerun all prior sprint acceptance flows that touch
     the changed area.

## Recommended First Cut

The first implementation should stop after Sprint 1 unless there is a strong reason
to go further immediately. Sprint 1 changes the product experience materially while
leaving retrieval, synthesis, and dashboard rendering mostly untouched. That makes
it the best low-risk starting point.
