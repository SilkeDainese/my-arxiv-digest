# 🔭 arXiv Digest

**Your personal arXiv paper curator** — fetches new papers, scores them with AI, and delivers a beautiful HTML digest to your inbox.

Created by [Silke S. Dainese](https://silkedainese.github.io) · [dainese@phys.au.dk](mailto:dainese@phys.au.dk) · [ORCID](https://orcid.org/0009-0001-7885-2439)

I built this for myself. I am a PhD student in astronomy at Aarhus University — not a software developer — and I wanted a smarter way to stay on top of new arXiv papers without spending an hour every morning. Other people in my department found it useful, so I cleaned it up and made it public. It is primarily aimed at people in physics and astronomy, but it will work for anyone on arXiv.

If you have suggestions, open an issue or [email me](mailto:dainese@phys.au.dk). I cannot promise to implement them — my research comes first.

> **For students:** The setup wizard has a guided track for **astronomy students** with pre-built keyword sets, AU faculty tracking, and telescope presets. If you are from another field and would like something similar for your speciality, [write me](mailto:dainese@phys.au.dk) and I will set it up.

*Built with the help of Claude Opus and Sonnet 4.6.*

---

## Quick Start

Three steps. No API keys, no passwords, no terminal.

### 1. Generate your config

**[Open the setup wizard →](https://arxiv-digest-setup.streamlit.app)**

Fill in your name, research description, keywords, and the email address where you want your digest. The wizard generates a `config.yaml` file — download it.

> **Students:** Choose the "AU Astronomy Student" track for a pre-filled config with your department's faculty, telescopes, and keywords. You can customise it later.

### 2. Fork this repo

**[Fork arXiv Digest →](https://github.com/SilkeDainese/arxiv-digest/fork)**

This creates your own copy. Everything runs in your fork — nothing is shared back.

### 3. Upload your config and run

In your fork: **[Add file](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository) → Upload files** → drag in `config.yaml` → **Commit changes**.

Then go to **Actions → arXiv Digest → Run workflow → Run workflow**.

You should get your first digest email within a few minutes. If something is wrong, the workflow log tells you exactly what to fix.

**That's it.** Your digest now runs automatically **Mon/Wed/Fri at 9am Danish time**. Papers show up in your inbox — no further action needed.

---

## Optional Upgrades

None of these are required. Everything works without them.

| Upgrade | What it does | How to set it up |
|---------|--------------|------------------|
| **Your own AI key** | Faster, more reliable scoring | Add `GEMINI_API_KEY` ([free →](https://aistudio.google.com/apikey)) or `ANTHROPIC_API_KEY` ([→](https://console.anthropic.com/)) as a [repo secret](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions). Set `own_api_key: true` in config.yaml |
| **Feedback arrows** | ↑/↓ buttons on each paper to improve future scoring | Set `github_repo: "yourusername/arxiv-digest"` in config.yaml |
| **Keyword tracking** | Track which keywords match papers over time | **Settings → Actions → General → Workflow permissions** → "Read and write" |
| **Own email sender** | Send from your own Gmail/Outlook instead of the shared sender | Add `SMTP_USER` and `SMTP_PASSWORD` as [repo secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions) ([Gmail App Password →](https://myaccount.google.com/apppasswords)) |

---

## How It Works

Your fork comes with a shared Gemini API key and a shared email relay, so everything works from the first run. The digest automatically uses the best AI available and falls back gracefully:

| Tier | Provider | Quality | What happens |
|------|----------|---------|--------------|
| 1 | **Claude** (Anthropic) | Best | Used if you add an `ANTHROPIC_API_KEY` |
| 2 | **Gemini 2.0 Flash** (Google) | Good | Used by default (shared key included) |
| 3 | **Keyword fallback** | Basic | Automatic fallback if AI is unavailable |

If one tier fails, it cascades to the next. You always get a digest. No money goes to the creator of this tool — API costs go directly to Anthropic/Google.

### Scoring details

1. **Keyword matching** — your keywords are checked against each paper's title and abstract, weighted by the importance you assigned (1–10). The matcher is fuzzy on purpose: plurals, hyphenation, and close variants like `planet` / `planetary` are treated as related.
2. **AI re-ranking** — the AI reads your `research_context` and re-ranks papers using that description. The more specific your research context, the better the scoring.
3. **Author boost** — papers by your `research_authors` get a relevance bump. Papers you authored yourself get a celebration section.

---

## Config Reference

See [`config.example.yaml`](config.example.yaml) for all options with inline comments.

| Field | Description |
|-------|-------------|
| `research_context` | Free-text description of your research (used by AI scoring) — the more specific, the better |
| `keywords` | Dictionary of `keyword: weight` pairs (1–10) |
| `keyword_aliases` | Optional `keyword: [similar phrases]` overrides for brittle terminology |
| `categories` | arXiv categories to monitor |
| `self_match` | How your name appears in arXiv author lists — triggers a celebration section when you publish |
| `research_authors` | Authors whose papers get a relevance boost |
| `colleagues` | People/institutions whose papers always show; people can carry an optional `note` shown in the digest |
| `digest_mode` | `highlights` (fewer, higher-quality picks) or `in_depth` (wider net, more papers) |
| `recipient_view_mode` | `deep_read` (full cards) or `5_min_skim` (top 3 one-line summaries) |
| `github_repo` | Your fork's path, e.g. `janedoe/arxiv-digest` — enables self-service links and feedback arrows |

---

## Managing Your Digest

Every digest email includes self-service links at the bottom:

- **Edit interests** → opens `config.yaml` in GitHub's web editor
- **Pause** → links to the Actions tab (disable the workflow)
- **Re-run setup** → opens the setup wizard
- **Delete** → links to repo Settings (Danger Zone → Delete repository)

Each paper card also includes quick feedback arrows when `github_repo` is set:

- **↑** = relevant (more like this)
- **↓** = not relevant (less like this)

These create labeled GitHub issues (`digest-feedback`) that are automatically ingested to nudge future ranking.

### How to Unsubscribe

1. **Pause**: Go to your repo → Actions → arXiv Digest → click ⋯ → Disable workflow
2. **Delete**: Go to your repo → Settings → scroll to Danger Zone → Delete this repository

---

## Email Setup

By default, digest emails are sent via a shared relay from `arxivdigestau@gmail.com`. No email setup needed.

If you prefer to send from your own email, add `SMTP_USER` and `SMTP_PASSWORD` as [repo secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions):

### Gmail

1. Enable [2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification)
2. Generate an [App Password](https://myaccount.google.com/apppasswords) — select "Mail" as the app
3. Add `SMTP_USER` (your Gmail address) and `SMTP_PASSWORD` (the App Password) as repo secrets

### Outlook / Office 365

1. Set up an [App Password](https://account.microsoft.com/security) in your Microsoft account
2. Add `SMTP_USER` and `SMTP_PASSWORD` as repo secrets
3. Update your `config.yaml`:

```yaml
smtp_server: "smtp.office365.com"
smtp_port: 587
```

---

## Development

### Run locally

```bash
pip install -r requirements.txt
export RECIPIENT_EMAIL="you@example.com"
export SMTP_USER="you@gmail.com"        # optional — uses relay without this
export SMTP_PASSWORD="your-app-password" # optional — uses relay without this
python digest.py
```

To preview the digest in your browser without sending an email:

```bash
python digest.py --preview
```

### Run the setup wizard locally

```bash
cd setup
pip install -r requirements.txt
streamlit run app.py
```

---

## License

MIT — see [LICENSE](LICENSE).

**Created by [Silke S. Dainese](https://silkedainese.github.io)** · Aarhus University · Dept. of Physics & Astronomy
