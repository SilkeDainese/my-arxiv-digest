# Phase 0c — Create `setup/validators.py` with tests

## Context
The arXiv Digest setup wizard has an AU Student flow where students sign up with their Aarhus University email. The email must be in the format `au` + 6 digits + `@uni.au.dk` (e.g. `au612345@uni.au.dk`). Students also set a password (not their AU login, just a digest-specific password) and select interest packages.

## Task
Create `setup/validators.py` with these pure functions (no Streamlit dependencies):

### `validate_au_email(value: str) -> tuple[bool, str]`
- Input: the part before `@uni.au.dk` (e.g. `"au612345"`)
- Valid: starts with `au`, followed by exactly 6 digits
- Case-insensitive
- Strip whitespace
- Returns `(True, "au612345@uni.au.dk")` on success
- Returns `(False, "Must be au + 6 digits")` on failure
- Returns `(False, "")` if empty (no error message, just not valid)

### `validate_password(password: str, confirm: str) -> tuple[bool, str]`
- Returns `(False, "")` if password is empty
- Returns `(False, "Too short")` if password < 4 chars
- Returns `(False, "Passwords don't match")` if password != confirm
- Returns `(True, "OK")` if 4-7 chars
- Returns `(True, "Strong")` if 8+ chars

### `validate_package_selection(selected: list[str]) -> tuple[bool, str]`
- Returns `(False, "Select at least one topic")` if empty list
- Returns `(True, f"{len(selected)} selected")` otherwise

### `validate_keyword_weight(weight: int) -> tuple[bool, str]`
- Returns `(False, "Weight must be 0-10")` if outside range
- Returns `(True, weight_label)` where label is:
  - 0-2: "loosely follow"
  - 3-5: "interested"
  - 6-8: "main interest"
  - 9-10: "everything"

## Tests
Create `tests/test_validators.py` with pytest:

```python
# Test cases to cover:

# validate_au_email
# - "au612345" -> (True, "au612345@uni.au.dk")
# - "AU612345" -> (True, "au612345@uni.au.dk")  # case insensitive
# - " au612345 " -> (True, "au612345@uni.au.dk")  # strips whitespace
# - "au12345" -> (False, ...)  # too few digits
# - "au1234567" -> (False, ...)  # too many digits
# - "xx612345" -> (False, ...)  # wrong prefix
# - "au61234x" -> (False, ...)  # non-digit
# - "" -> (False, "")  # empty

# validate_password
# - ("", "") -> (False, "")
# - ("abc", "abc") -> (False, "Too short")
# - ("abcd", "abcx") -> (False, "Passwords don't match")
# - ("abcd", "abcd") -> (True, "OK")
# - ("abcdefgh", "abcdefgh") -> (True, "Strong")

# validate_package_selection
# - [] -> (False, "Select at least one topic")
# - ["Stars"] -> (True, "1 selected")
# - ["Stars", "Exoplanets"] -> (True, "2 selected")

# validate_keyword_weight
# - -1 -> (False, ...)
# - 11 -> (False, ...)
# - 0 -> (True, "loosely follow")
# - 5 -> (True, "interested")
# - 7 -> (True, "main interest")
# - 10 -> (True, "everything")
```

## Constraints
- Pure Python, no external dependencies
- `from __future__ import annotations` at top
- Type hints on all functions
- One-line docstrings
- Run tests with: `cd /Users/au617716/Projects/arxiv-digest && pytest tests/test_validators.py -v`
