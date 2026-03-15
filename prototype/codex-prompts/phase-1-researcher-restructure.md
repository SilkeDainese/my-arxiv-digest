# Phase 1 — Restructure Researcher Flow (10 sections → 4 steps)

## Context
`setup/app.py` is a ~2940-line Streamlit wizard. The Researcher flow currently uses 10 sections gated by `current_step` (1–10). This phase merges them into 4 steps by combining related sections and hiding power-user options behind `st.expander("Advanced ...")`.

The target UX is prototyped in `prototype/ux-lab.html` (the Researcher flow). The session state keys are documented in `setup/SESSION_STATE_MAP.md`.

**Critical contract: the config.yaml output must remain identical.** Only the UI flow changes — all the same session_state keys must still be set, and the final config dict built in Section 10 must produce the same YAML fields.

## Current Section Map (line numbers approximate)

| Old Section | Lines | Content |
|---|---|---|
| Welcome + invite + AI setup | 1102–1253 | Mode picker, invite code, AI key — **do NOT change** |
| Section 1: Profile Scan | 1254–1715 | ORCID lookup, Pure scan, preview/import, group import |
| Section 2: Your Profile | 1716–1817 | Name, institution, department, digest name, tagline, self_match |
| Section 3: Research Description | 1818–2096 | Text area, paper selector, AI suggestions for keywords/categories |
| Section 4: arXiv Categories | 2097–2209 | Hierarchical category picker |
| Section 5: Keywords | 2210–2325 | Weight table with add/remove |
| Section 6: Research Authors | 2326–2369 | Author list text area |
| Section 7: Colleagues | 2370–2502 | Colleague table, co-author suggestions, institution entry |
| Section 8: Digest Mode & Schedule | 2503–2674 | Mode, schedule, days_back, send_hour, overrides |
| Section 9: Email Provider | 2675–2716 | SMTP server, port, GitHub repo |
| Section 10: Preview & Download | 2717–2815 | Config preview, download button |

## New 4-Step Structure

### Step 1: "About You" (merge old Sections 1 + 2 + research description from Section 3)

**Default (always visible):**
- ORCID lookup (all existing ORCID/Pure logic from Section 1 — keep as-is)
- After ORCID import, show auto-filled fields:
  - `profile_name` (text input)
  - `profile_institution` (text input)
  - Research description (`_research_description_val` / `research_description`) — move the text area here from Section 3
  - Caption under description: "Auto-generated from your publications. Edit freely — the AI reads this daily to score papers."
- If no ORCID: show "No ORCID? Fill manually" link that reveals the same fields empty

**Advanced profile settings** (`st.expander("Advanced profile settings")`):
- `_s2_digest_name` — digest name text input (default "arXiv Digest")
- `profile_department` — department text input
- `self_match` — arXiv name variants (keep existing multiselect/tag input)
- `_s2_tagline` — tagline text input

**What moves:**
- Research description text area moves FROM Section 3 INTO Step 1 (below name/institution)
- Digest name, department, tagline, self_match move INTO the Advanced expander
- The `_maybe_seed_research_description()` auto-draft logic stays tied to ORCID import

**Session state keys used:** `profile_name`, `profile_institution`, `profile_department`, `profile_mode`, `research_description`, `_research_description_val`, `research_description_widget`, `self_match`, `_s2_digest_name`, `_s2_tagline`, all `_orcid_*` keys, `orcid_preview`, `pure_*` keys, `group_orcid_members`

### Step 2: "What to Follow" (merge old Sections 3 remainder + 4 + 5)

**Default (always visible):**
- "Auto-fill from publications" button (gold-wash bar) — triggers `suggest_keywords_from_context()` + `suggest_categories()` if ORCID titles exist
- arXiv categories — keep the existing hierarchical group picker from Section 4
- Keywords as `st.multiselect` chips — all keywords get default weight 7. Show text input + "Add" button to add custom keywords.

**Advanced keyword settings** (`st.expander("Advanced keyword settings")`):
- The existing weight table from Section 5 (with 0–10 arrows, "Always" checkboxes)
- Weight labels: 0–2 loosely follow, 3–5 interested, 6–8 main interest, 9–10 everything

**What moves:**
- The paper selector ("Choose which publications inform AI suggestions") stays here but is secondary — only show it if ORCID titles exist
- The AI suggestion buttons and results stay
- Research description text area has MOVED OUT to Step 1 (but the AI suggestion logic still reads `research_description` from session_state — that's fine since it's already set)
- Category picker content stays as-is
- Keyword weight table moves into Advanced expander; the default view is chips-only

**Sync chips ↔ table:** When a keyword is added via the multiselect chips, add it to `keywords` session_state with weight 7. When removed, remove from `keywords`. The Advanced table reads from the same `keywords` dict.

**Session state keys used:** `keywords`, `ai_suggested_kws`, `ai_suggested_cats`, `selected_categories`, `selected_papers`, `paper_selector_widget`, `_orcid_titles`, `_orcid_works_meta`

### Step 3: "People to Follow" (merge old Sections 6 + 7)

**Default (always visible):**
- Unified people list — combine `research_authors` and `colleagues_people` into a single add-person interface
- "Suggest from co-authors" button — uses `_orcid_coauthor_counts` / `_orcid_coauthor_map` to suggest people (existing logic from Section 7)
- Show "Clear" button only when people have been added
- Explainer text: "Everyone you add gets their own section in the digest, even if their papers are off-topic for you."

**Advanced: colleague vs. research author** (`st.expander("Advanced: colleague vs. research author")`):
- Explanation: "By default, everyone is a colleague (always shown). Reclassify as research author to give a scoring boost instead — they may be filtered if too off-topic."
- Show existing colleague vs author reclassification controls

**What changes:**
- By default, all added people go into `colleagues_people` (always-show behavior)
- The old "Research Authors" text area (Section 6) becomes a reclassification option inside Advanced
- The colleague institution entry (`colleagues_institutions`) stays in the Advanced section too

**Session state keys used:** `research_authors`, `colleagues_people`, `colleagues_institutions`, `_orcid_coauthor_counts`, `_orcid_coauthor_map`

### Step 4: "Delivery & Download" (merge old Sections 8 + 9 + 10)

**Default (always visible):**
- Schedule: show as text "Your digest arrives **Mon, Wed, Fri**." with a "Change →" link that reveals `st.radio` picker with options:
  - Mon / Wed / Fri (default) — "Best balance"
  - Every weekday — "Never miss a day"
  - Weekly (Monday) — "Monday round-up"
- Digest size: `st.radio` with two options:
  - Highlights — "Top papers only (up to 6). For busy people." (default)
  - In-depth — "Wider net (up to 15). For browsers."
- Download section: config preview + download button (from old Section 10)

**Customize card layout** (`st.expander("Customize card layout")`):
- `_s8_recipient_view_mode` — card layout preset (deep_read / skim / full)
- Card element toggle/reorder (if implemented)

**Self-hosting options** (`st.expander("Self-hosting options")`):
- Caption: "Only relevant if you're running your own email. Most users can skip this."
- Email provider (SMTP server/port from old Section 9)
- Send time UTC (`_s8_send_hour_utc`)
- Min score override, max papers override
- GitHub repo (`_s9_github_repo`)

**Schedule mapping (for config output):**
- "Mon / Wed / Fri" → `schedule: "mon_wed_fri"`, `_s8_cron_expr: "0 7 * * 1,3,5"`, `days_back: 4`
- "Every weekday" → `schedule: "weekdays"`, `_s8_cron_expr: "0 7 * * 1-5"`, `days_back: 2`
- "Weekly" → `schedule: "weekly"`, `_s8_cron_expr: "0 7 * * 1"`, `days_back: 7`

**Session state keys used:** `_s8_*` keys, `_s9_*` keys, all config-building logic from Section 10

## Implementation Instructions

### 1. Change the step gate from 10 steps to 4

Find `current_step` in session state defaults (around line 1053). Change the step tracking to work with 4 steps instead of 10. Each step's content should be gated by `if st.session_state.current_step >= N:`.

### 2. Add step headers

For each step, use:
```python
st.markdown(f'<p><span class="step-number">{N}</span> <strong>{title}</strong></p>', unsafe_allow_html=True)
```
Use titles: "About You", "What to Follow", "People to Follow", "Delivery & Download"

### 3. Move code blocks

Move the code blocks as described above. The key moves are:
- Research description text area: FROM ~line 1830-1900 TO after the name/institution fields in Step 1
- Digest name, department, tagline, self_match: INTO `with st.expander("Advanced profile settings"):`
- Keyword weight table: INTO `with st.expander("Advanced keyword settings"):`
- Research authors section: INTO `with st.expander("Advanced: colleague vs. research author"):`
- Email provider (Section 9): INTO `with st.expander("Self-hosting options"):`
- Card customization controls: INTO `with st.expander("Customize card layout"):`

### 4. Add multiselect chips for keywords (Step 2)

Before the Advanced keyword expander, add:
```python
# Keyword chips (simple view — all get weight 7)
current_kw_list = list(st.session_state.keywords.keys())
selected_kws = st.multiselect("Keywords", options=current_kw_list, default=current_kw_list)

# Sync: remove deselected, keep weights for existing
new_keywords = {}
for kw in selected_kws:
    new_keywords[kw] = st.session_state.keywords.get(kw, 7)
st.session_state.keywords = new_keywords

# Add custom keyword
new_kw = st.text_input("Add a keyword", key="new_kw_input")
if st.button("Add", key="add_kw_btn") and new_kw.strip():
    st.session_state.keywords[new_kw.strip()] = 7
    st.rerun()
```

### 5. Keep all Continue buttons

Each step still has a Continue button at the bottom that increments `current_step`. The last step (4) has the download button instead.

### 6. DO NOT change

- The Welcome section (mode picker, invite code, AI setup) — lines 1102–1253
- Mini flow (`render_mini_setup()`)
- Student flow (`render_au_student_setup()`)
- Helper functions (lines 93–950)
- `_render_repo_setup_steps()`
- The config dict construction logic in Section 10 — only move it into Step 4, don't change the dict fields
- Any session_state key names
- The profile_mode radio and its conditional logic

## Verification
After restructuring, verify:
1. All session_state keys from SESSION_STATE_MAP.md are still initialized and used
2. The config dict in the download section produces the same fields
3. The step gating logic (`current_step >= N`) works correctly for 4 steps
4. All `st.expander("Advanced ...")` sections contain the right controls
5. The research description appears in Step 1, not Step 2
