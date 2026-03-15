# Phase 0b — Document session_state keys

## Context
`setup/app.py` (2,980 lines) is a Streamlit app that uses `st.session_state` extensively to persist form values. The form data eventually gets assembled into a config dict (around line 2766-2800) and exported as YAML via `st.download_button`.

The config schema has these top-level fields (from `config.example.yaml` / `load_config()` in `digest.py`):
- `digest_name`, `researcher_name`, `research_context`
- `categories` (list), `keywords` (dict), `keyword_aliases` (dict)
- `research_authors` (list), `self_match` (list)
- `colleagues.people` (list of dicts), `colleagues.institutions` (list)
- `digest_mode`, `recipient_view_mode`, `days_back`, `max_papers`, `min_score`
- `recipient_email`, `smtp_server`, `smtp_port`
- `institution`, `department`, `tagline`
- `github_repo`, `setup_url`
- `schedule`, `send_hour_utc`

## Task
1. Read `setup/app.py` completely
2. Find every instance of `st.session_state` (both reads and writes)
3. Create a reference document listing each key with:
   - Key name (e.g. `"keywords"`)
   - Python type (e.g. `dict[str, int]`)
   - Default value (what it's initialized to)
   - Which config.yaml field it maps to (or "internal" if it's UI-only state)
   - Which step/section sets it (e.g. "Section 3: Keywords")
   - Whether it's used in the Researcher flow, Mini flow, Student flow, or all

4. Write output to `setup/SESSION_STATE_MAP.md`

## Format
Use a markdown table:
```markdown
| session_state key | Type | Default | Config field | Set by section | Flows |
|---|---|---|---|---|---|
| `keywords` | `dict[str,int]` | `{}` | `keywords` | Section 3 | Researcher, Mini |
```

## Constraints
- This is a reference doc only — do NOT modify any code
- Be thorough — every `st.session_state` access must be catalogued
- Include UI-only state (like `ai_toggle`, `current_step`) that doesn't map to config fields
- Note any session_state keys that are set conditionally (e.g. only after ORCID import)
