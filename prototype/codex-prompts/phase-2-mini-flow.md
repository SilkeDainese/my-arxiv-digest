# Phase 2 — Update Mini Flow (chips-first keywords)

## Context
`setup/app.py` has a function `render_mini_setup()` that renders the Mini setup flow. Currently it shows a keyword weight table directly (with 0-10 weight arrows and "Always" checkboxes). The Researcher flow was restructured (Phase 1) to show keywords as simple `st.multiselect` chips by default, with the weight table hidden behind an `st.expander("Advanced keyword settings")`.

The Mini flow should follow the same pattern — it's for simpler users who need the simpler interface even more.

## Task
In `render_mini_setup()`:

1. **Replace the keyword table with `st.multiselect` chips** as the default view:
   - Use `st.multiselect("Keywords", options=[], default=[], ...)` or similar chip-like input
   - All keywords get a default weight of 7
   - Show a text input + "Add" button to add custom keywords

2. **Move the weight table into an expander:**
   ```python
   with st.expander("Advanced keyword settings"):
       # existing weight table code goes here
   ```

3. **Sync chips and table:** When a keyword is added via chips, it should appear in the Advanced table with weight 7. When removed from chips, remove from table.

4. **Fix the Clear button for colleagues (Step 2):** Only show it when colleagues have been added. Check `st.session_state` for the colleagues list and conditionally render the button.

## Reference
Look at how the Researcher flow Step 2 handles keywords after Phase 1 is complete — match that pattern exactly.

## Constraints
- Do NOT change the config output — Mini must still produce the same `keywords: {term: weight}` dict
- Do NOT change Steps 2 (Colleagues) or 3 (Schedule) logic, only the keyword display pattern and the Clear button visibility
- Keep the "After setup" instructions unchanged
