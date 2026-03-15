# Phase 3 — Update Student Flow (validation + copy)

## Context
`setup/app.py` has a function `render_au_student_setup()` for the AU Student flow. Phase 0c created `setup/validators.py` with pure validation functions. This phase wires them into the Streamlit flow.

## Task

### 1. Import and wire validators
```python
from validators import validate_au_email, validate_password, validate_package_selection
```

### 2. Step 1 (AU Account) — validation guard
Before the Continue/Next action in Step 1:
- Call `validate_au_email()` on the email input value
- Call `validate_password()` on password + confirm inputs
- If either fails, show `st.error(message)` and do NOT advance to Step 2
- If both pass, advance normally

### 3. Step 2 (Interests) — validation guard
Before the Continue/Next action in Step 2:
- Call `validate_package_selection()` on the list of selected packages
- If fails, show `st.error("Select at least one topic")` and do NOT advance
- If passes, advance normally

### 4. Update banner text
Find the student flow header/banner text. Change:
- FROM: any text containing "provided by your instructor" or similar
- TO: `"AI scoring and email relay provided courtesy. You just need an AU email and to set a password."`

### 5. Subscribe feedback
After the subscribe button is clicked and succeeds, show a clean confirmation:
```python
st.success("Confirmation email sent to {email}@uni.au.dk")
with st.expander("View API response"):
    st.json({"ok": True, "subscription": {"package_ids": [...], "max_papers_per_week": 6}, "confirmation_email_sent": True})
```

## Constraints
- Do NOT change the API call logic if one exists — only add validation before form submission
- Do NOT change the package grid UI (the cards/checkboxes) — only add the validation check
- Import validators with a relative import: `from validators import ...` (same directory)
- The relay endpoint is `https://arxiv-digest-relay.vercel.app/api/students` — reference it in the API response display if simulating

## Verification
- Try submitting Step 1 with empty email → should show error
- Try submitting Step 1 with `au123` (too short) → should show error
- Try submitting Step 1 with valid email but mismatched passwords → should show error
- Try submitting Step 2 with no packages selected → should show error
- Happy path should work unchanged
