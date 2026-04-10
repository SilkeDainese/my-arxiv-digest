# TECH-DEBT.md — arxiv-digest-weekly

Last updated: 2026-04-10

## Open items

### TD-001 — SRI hashes on Firebase CDN scripts
**File:** `infra/signup.html`
**Issue:** Firebase JS SDK loaded from `www.gstatic.com` without real SRI hashes.
Placeholders are in place (`sha384-placeholder-...`). WEB-2 compliance requires
actual hashes before the page goes to `silkedainese.github.io`.
**Fix:** Run `openssl dgst -sha384 -binary firebase-app-compat.js | openssl base64 -A`
against the downloaded files, replace the placeholder strings.
**Priority:** Medium — before signup page goes live.

### ~~TD-002 — AI scoring not yet wired~~ CLOSED 2026-04-10
`shared/ai_scorer.py` implements the full Claude → Vertex Gemini → Gemini API → keyword
cascade. Every paper gets `plain_summary`, `highlight_phrase`, `score_tier`.
Secrets needed: `anthropic-api-key`, `gemini-api-key` in Secret Manager.
Currently running on keyword fallback until Silke populates those secrets.

### TD-003 — No duplicate subscriber guard
**File:** `firestore.rules`, `infra/signup.html`
**Issue:** Firestore rules allow create but don't check for existing email.
A student could sign up twice with the same email and get two digests.
**Fix:** Either: (a) add a signup Cloud Function that checks before writing,
or (b) use email as the Firestore doc ID (requires restructuring the collection).
Option (b) is cleaner but requires a migration for any existing docs.
**Priority:** Low — minor annoyance, not a data leak.

### TD-004 — CET/CEST timezone handling in Cloud Scheduler
**File:** `deploy.sh`
**Issue:** Scheduler is set to UTC times. Saturday 19:00 UTC = 20:00 CET (winter)
but 21:00 CEST (summer), which is an hour late. Monday 06:00 UTC = 07:00 CET (winter)
but 08:00 CEST (summer), which is an hour late.
**Fix:** Set scheduler timezone to `Europe/Copenhagen` directly. gcloud scheduler
supports IANA timezones. Current UTC workaround means summer digests arrive late.
**Priority:** Medium — not wrong, just slightly off in summer.

### TD-005 — No rate limiting on signup endpoint
**File:** `infra/signup.html`, `firestore.rules`
**Issue:** Firestore rules allow unlimited creates from any origin. A spammer
could fill the subscribers collection.
**Fix:** Either: (a) add Cloud Armor policy, or (b) use a signup Cloud Function
with IP-based rate limiting (e.g. via Firebase App Check).
**Priority:** Low — student audience, low abuse risk.

### TD-006 — Signup page Firebase config uses placeholder values
**File:** `infra/signup.html`
**Issue:** `FIREBASE_CONFIG` object contains placeholder strings. Must be filled
in before deployment.
**Fix:** Silke needs to copy real values from Firebase Console → Project Settings.
**Priority:** Blocker for signup page deployment.

## Closed items

### TD-002 — AI scoring (closed 2026-04-10)
Full Claude → Vertex Gemini → Gemini API → keyword cascade in `shared/ai_scorer.py`.

---

## New items from this sprint (2026-04-10)

### TD-007 — anthropic-api-key and gemini-api-key not yet populated in Secret Manager
**Issue:** AI scorer falls through to keyword fallback until these secrets exist.
Preview email is sending keyword-scored summaries (first 250 chars of abstract).
**Fix:** Silke adds secrets:
  `gcloud secrets create anthropic-api-key --replication-policy=automatic`
  `echo -n "sk-ant-..." | gcloud secrets versions add anthropic-api-key --data-file=-`
  Same for `gemini-api-key`.
**Priority:** High — AI summaries are the whole point of this sprint.

### TD-008 — myfork remote hook fires on arxiv-digest-weekly (no fork exists)
**Issue:** Pre-push hook `arxiv-dual-push.js` requires `git push myfork` but this
repo has only one remote (`origin`). Push to origin succeeds; hook error is noise.
**Fix:** Update hook to skip the dual-push check for repos without a `myfork` remote,
or add an exception for the `arxiv-digest-weekly` repo.
**Priority:** Low — push succeeds, just noisy.

### TD-009 — pkg_resources deprecation warning in Cloud Functions logs
**Issue:** `google` package imports `pkg_resources` (deprecated in Setuptools 81+).
Generates UserWarning noise in every Cloud Function cold start.
**Fix:** Pin `setuptools<81` in requirements or wait for upstream fix in google packages.
**Priority:** Low — cosmetic only.
