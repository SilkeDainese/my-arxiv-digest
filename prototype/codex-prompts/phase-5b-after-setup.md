# Phase 5b — Update After-Setup Instructions

## Context
`setup/app.py` has a function `_render_repo_setup_steps()` that renders the "After setup" instructions shown below the download button. These tell users how to fork, upload config, add secrets, and enable Actions.

The mockup at `prototype/ux-lab.html` has simplified versions of these instructions. This phase updates the Streamlit version to match.

## Task
In `_render_repo_setup_steps()`, update the content to match this structure:

### Step 1 — Fork the repo
- Text: "Fork the repo"
- Sub: Link to `SilkeDainese/arxiv-digest` → Fork

### Step 2 — Upload config.yaml
- Text: "Upload config.yaml"
- Sub: "Add file → Upload → drop config.yaml → Commit."

### Step 3 — Add secrets
- Text: "Add secrets"
- Sub: "Settings → Secrets → Actions"
- Show a table with these secrets:

| Secret | Value | Required |
|--------|-------|----------|
| `RECIPIENT_EMAIL` | Your email address | Yes |
| **Email delivery — pick one:** | | |
| `RELAY_TOKEN` | From access code — no email setup needed | Option A |
| `SMTP_USER` + `SMTP_PASSWORD` | Gmail/Outlook + App Password | Option B |
| **AI scoring — optional:** | | |
| `GEMINI_API_KEY` | Free key → aistudio.google.com | Free |
| `ANTHROPIC_API_KEY` | console.anthropic.com | Paid |

### Step 4 — Allow Actions & run workflow
- Text: "Allow Actions & run workflow"
- Sub: "Actions tab → Enable workflows → Run workflow."

## Constraints
- Use `st.markdown()` with the existing brand CSS classes (`.step-number`, `.brand-label`, etc.)
- Keep the function signature unchanged
- Do NOT add new dependencies
- Match the existing styling patterns used elsewhere in the file
