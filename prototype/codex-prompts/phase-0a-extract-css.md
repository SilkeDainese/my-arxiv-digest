# Phase 0a — Extract CSS into `setup/style.py`

## Context
`setup/app.py` is a 2,980-line Streamlit setup wizard. At line 82-121, it injects custom CSS via `st.markdown()` with `unsafe_allow_html=True`. The CSS uses f-string interpolation with brand colors imported from `brand.py` (line 40: `from brand import PINE, GOLD, CARD_BORDER, WARM_GREY`).

## Task
1. Create `setup/style.py` that:
   - Imports all used colors from `brand.py` (check which constants are actually referenced in the CSS)
   - Exports a single function `inject_css()` that calls `st.markdown(css_string, unsafe_allow_html=True)`
   - The CSS string should be identical to what's currently inline in app.py

2. In `setup/app.py`:
   - Replace the `st.markdown(f"""<style>...</style>""", unsafe_allow_html=True)` block (lines 82-121) with:
     ```python
     from style import inject_css
     inject_css()
     ```
   - Remove the `from brand import ...` line if no other code in app.py uses those constants directly (search first!)

## Constraints
- Do NOT change any CSS values or add new styles
- Do NOT change any other code in app.py
- The `brand.py` file at the repo root is the SSOT for colors. Available constants: PINE, GOLD, UMBER, ASH_WHITE, ASH_BLACK, CARD_BORDER, WARM_GREY, PINE_WASH, PINE_LIGHT, GOLD_LIGHT, GOLD_WASH, ALERT_RED, ALERT_RED_WASH, CATALOG_PURPLE, CATALOG_WASH, FONT_HEADING, FONT_BODY, FONT_MONO
- Keep the brand import in app.py if other code uses those constants (grep for usage first)

## Verification
- Run `cd /Users/au617716/Projects/arxiv-digest && python -c "from setup.style import inject_css; print('OK')"` to check import works
- The app should look identical after this change
