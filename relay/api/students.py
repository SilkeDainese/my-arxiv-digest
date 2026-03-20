"""Central student subscription management API for AU student digests."""

from __future__ import annotations

import base64
import html
import json
import os
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from http.server import BaseHTTPRequestHandler
from typing import Any

import importlib.util
from pathlib import Path

_reg_path = Path(__file__).with_name("_registry.py")
_spec = importlib.util.spec_from_file_location("_registry", _reg_path)
_registry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_registry)

DEFAULT_MAX_PAPERS = _registry.DEFAULT_MAX_PAPERS
build_student_record = _registry.build_student_record
clamp_max_papers = _registry.clamp_max_papers
now_iso = _registry.now_iso
normalise_email = _registry.normalise_email
normalise_package_ids = _registry.normalise_package_ids
package_labels = _registry.package_labels
public_record = _registry.public_record
verify_password = _registry.verify_password

GITHUB_API = "https://api.github.com"
STORAGE_GITHUB_TOKEN = os.environ.get("STUDENT_STORAGE_GITHUB_TOKEN", "").strip()
STORAGE_REPO = os.environ.get("STUDENT_STORAGE_REPO", "").strip()
STORAGE_PATH = os.environ.get("STUDENT_STORAGE_PATH", "students/subscriptions.json").strip()
STORAGE_BRANCH = os.environ.get("STUDENT_STORAGE_BRANCH", "main").strip()
STUDENT_ADMIN_TOKEN = os.environ.get("STUDENT_ADMIN_TOKEN", "").strip()
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
PUBLIC_STUDENT_MANAGE_URL = os.environ.get(
    "PUBLIC_STUDENT_MANAGE_URL",
    "https://arxiv-digest-relay.vercel.app/api/students",
).strip()


def _github_request(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send a GitHub API request and decode the JSON response."""
    if not STORAGE_GITHUB_TOKEN or not STORAGE_REPO:
        raise RuntimeError(
            "Student registry storage is not configured. "
            "Set STUDENT_STORAGE_GITHUB_TOKEN and STUDENT_STORAGE_REPO."
        )
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {STORAGE_GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_registry() -> tuple[dict[str, Any], str | None]:
    """Load the student registry JSON file from the private GitHub repo."""
    url = (
        f"{GITHUB_API}/repos/{STORAGE_REPO}/contents/"
        f"{urllib.parse.quote(STORAGE_PATH)}?ref={urllib.parse.quote(STORAGE_BRANCH)}"
    )
    try:
        data = _github_request("GET", url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"students": {}}, None
        raise

    content = base64.b64decode(data["content"]).decode("utf-8")
    registry = json.loads(content) if content.strip() else {}
    if not isinstance(registry, dict):
        registry = {}
    registry.setdefault("students", {})
    return registry, data.get("sha")


def _save_registry(registry: dict[str, Any], sha: str | None, message: str) -> None:
    """Persist the registry JSON file back to GitHub."""
    content = json.dumps(registry, indent=2, sort_keys=True).encode("utf-8")
    payload: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": STORAGE_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    url = f"{GITHUB_API}/repos/{STORAGE_REPO}/contents/{urllib.parse.quote(STORAGE_PATH)}"
    _github_request("PUT", url, payload)


def _require_admin_token(token: str) -> None:
    """Validate the admin token used by the batch sender."""
    if not STUDENT_ADMIN_TOKEN or token != STUDENT_ADMIN_TOKEN:
        raise PermissionError("Invalid admin token.")


def _build_manage_url(email: str) -> str:
    """Return the public manage-page URL for a student subscription."""
    return (
        f"{PUBLIC_STUDENT_MANAGE_URL.rstrip('?')}"
        f"?{urllib.parse.urlencode({'email': email})}"
    )


def _send_subscription_confirmation(
    subscription: dict[str, Any],
    *,
    event: str,
) -> tuple[bool, str | None]:
    """Send an immediate confirmation email for a new or reactivated subscription."""
    if not SMTP_USER or not SMTP_PASSWORD:
        return False, "confirmation mail is not configured on the relay"

    email = subscription["email"]
    package_text = ", ".join(package_labels()[package_id] for package_id in subscription["package_ids"])
    manage_url = _build_manage_url(email)
    action_text = (
        "Your AU student digest subscription is active again."
        if event == "resubscribed"
        else "Your AU student digest subscription is active."
    )
    subject = "AU student digest subscription confirmed"
    plain_text = (
        f"{action_text}\n\n"
        f"Email: {email}\n"
        f"Packages: {package_text}\n"
        f"Max papers per week: {subscription['max_papers_per_week']}\n\n"
        f"Manage your subscription: {manage_url}\n"
    )
    html_body = f"""<!doctype html>
<html lang="en">
  <body style="font-family:Arial,sans-serif;color:#1f2933;line-height:1.6">
    <h2 style="margin:0 0 12px">AU student digest subscription confirmed</h2>
    <p>{html.escape(action_text)}</p>
    <p><strong>Email:</strong> {html.escape(email)}<br>
       <strong>Packages:</strong> {html.escape(package_text)}<br>
       <strong>Max papers per week:</strong> {subscription['max_papers_per_week']}</p>
    <p><a href="{html.escape(manage_url)}">Manage your subscription</a></p>
  </body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"arXiv Digest <{SMTP_USER}>"
    msg["To"] = email
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [email], msg.as_bytes())
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, "relay SMTP authentication failed"
    except Exception as exc:
        return False, str(exc)


def _handle_upsert(body: dict[str, Any]) -> dict[str, Any]:
    email = normalise_email(body.get("email", ""))
    registry, sha = _load_registry()
    existing = registry["students"].get(email)
    is_reactivation = bool(existing) and not bool(existing.get("active", True))
    is_new_subscription = existing is None
    record = build_student_record(
        email=email,
        password=str(body.get("password", "")),
        new_password=str(body.get("new_password", "")),
        package_ids=body.get("package_ids", []),
        max_papers_per_week=body.get("max_papers_per_week", DEFAULT_MAX_PAPERS),
        existing=existing,
    )
    registry["students"][email] = record
    _save_registry(registry, sha, f"Update student subscription for {email}")
    subscription = public_record(record)

    confirmation_sent = False
    confirmation_error: str | None = None
    subscription_event = "created" if is_new_subscription else "updated"
    if is_reactivation:
        subscription_event = "resubscribed"

    if is_new_subscription or is_reactivation:
        confirmation_sent, confirmation_error = _send_subscription_confirmation(
            subscription,
            event=subscription_event,
        )

    return {
        "ok": True,
        "subscription": subscription,
        "package_labels": package_labels(),
        "subscription_event": subscription_event,
        "confirmation_email_sent": confirmation_sent,
        "confirmation_email_error": confirmation_error,
    }


def _handle_get(body: dict[str, Any]) -> dict[str, Any]:
    email = normalise_email(body.get("email", ""))
    registry, _ = _load_registry()
    record = registry["students"].get(email)
    if not record:
        raise FileNotFoundError("Subscription not found.")
    if not verify_password(str(body.get("password", "")), record.get("password_salt", ""), record.get("password_hash", "")):
        raise PermissionError("Incorrect password.")
    return {"ok": True, "subscription": public_record(record), "package_labels": package_labels()}


def _handle_unsubscribe(body: dict[str, Any]) -> dict[str, Any]:
    email = normalise_email(body.get("email", ""))
    registry, sha = _load_registry()
    record = registry["students"].get(email)
    if not record:
        raise FileNotFoundError("Subscription not found.")
    if not verify_password(str(body.get("password", "")), record.get("password_salt", ""), record.get("password_hash", "")):
        raise PermissionError("Incorrect password.")
    record = dict(record)
    record["active"] = False
    record["updated_at"] = now_iso()
    registry["students"][email] = record
    _save_registry(registry, sha, f"Unsubscribe student {email}")
    return {"ok": True, "subscription": public_record(record), "package_labels": package_labels()}


def _handle_admin_list(body: dict[str, Any]) -> dict[str, Any]:
    _require_admin_token(str(body.get("admin_token", "")))
    include_inactive = bool(body.get("include_inactive", False))
    registry, _ = _load_registry()
    students = [
        public_record(record)
        for _, record in sorted(registry["students"].items())
        if include_inactive or record.get("active", True)
    ]
    return {"ok": True, "subscriptions": students, "package_labels": package_labels()}


def _handle_resend_confirmation(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Re-send the confirmation email for an existing subscription."""
    email = normalise_email(body.get("email", ""))
    registry, _ = _load_registry()
    record = registry["students"].get(email)
    if not record:
        return 404, {"error": "Subscription not found."}
    if not verify_password(str(body.get("password", "")), record.get("password_salt", ""), record.get("password_hash", "")):
        return 403, {"error": "Incorrect password."}
    if not record.get("active", True):
        return 400, {"error": "Subscription is inactive. Re-subscribe first."}
    sent, err = _send_subscription_confirmation(record, event="resent")
    return 200, {
        "ok": True,
        "confirmation_email_sent": sent,
        "confirmation_email_error": err,
    }


def _dispatch(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    action = str(body.get("action", "")).strip().lower()
    if action == "upsert":
        return 200, _handle_upsert(body)
    if action == "get":
        return 200, _handle_get(body)
    if action == "unsubscribe":
        return 200, _handle_unsubscribe(body)
    if action == "admin_list":
        return 200, _handle_admin_list(body)
    if action == "resend_confirmation":
        return _handle_resend_confirmation(body)
    return 400, {"error": "unknown action"}


def _manage_page(
    email: str,
    mode: str,
    package_ids: list[str] | None = None,
    max_papers_per_week: int = DEFAULT_MAX_PAPERS,
) -> str:
    """Return a simple browser-based student subscription management page."""
    safe_email = html.escape(email)
    initial_packages = json.dumps(list(package_ids or []))
    initial_max_papers = clamp_max_papers(max_papers_per_week)
    packages_markup = "\n".join(
        f"""
        <label class="package">
          <input type="checkbox" name="package_ids" value="{html.escape(package_id)}">
          <span>{html.escape(label)}</span>
        </label>
        """
        for package_id, label in package_labels().items()
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AU student digest</title>
    <style>
      :root {{
        --bg: #f6f1e8;
        --panel: #fffdf8;
        --text: #1f2933;
        --muted: #5f6c76;
        --accent: #1d5b57;
        --accent-light: rgba(29, 91, 87, 0.08);
        --danger: #8a3b12;
        --border: #d8d1c6;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        min-height: 100vh;
        background: linear-gradient(180deg, var(--bg), #efe6d7);
        color: var(--text);
        font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
        padding: 24px;
      }}
      main {{
        width: min(100%, 600px);
        margin: 0 auto;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 32px;
        box-shadow: 0 18px 48px rgba(31, 41, 51, 0.08);
      }}
      h1 {{
        margin: 0 0 6px;
        font-size: clamp(1.6rem, 4vw, 2.2rem);
        line-height: 1.1;
      }}
      h2 {{
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--muted);
        margin: 0 0 12px;
        font-weight: 600;
      }}
      p, label, button, input {{
        font-size: 0.95rem;
      }}
      .muted {{
        color: var(--muted);
        line-height: 1.5;
        margin: 0 0 20px;
        font-size: 0.9rem;
      }}
      .section {{
        margin-bottom: 24px;
      }}
      .section:last-of-type {{
        margin-bottom: 0;
      }}
      .divider {{
        border: none;
        border-top: 1px solid var(--border);
        margin: 24px 0;
      }}
      .field {{
        margin-bottom: 12px;
      }}
      .field label {{
        display: block;
        font-size: 0.82rem;
        color: var(--muted);
        margin-bottom: 4px;
        font-weight: 500;
      }}
      input[type="text"], input[type="password"], input[type="number"] {{
        width: 100%;
        padding: 10px 12px;
        border-radius: 8px;
        border: 1px solid var(--border);
        background: white;
        font-size: 0.95rem;
      }}
      input:focus {{
        outline: 2px solid var(--accent);
        outline-offset: -1px;
        border-color: var(--accent);
      }}
      .email-row {{
        display: flex;
        align-items: center;
        background: white;
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
      }}
      .email-row:focus-within {{
        outline: 2px solid var(--accent);
        outline-offset: -1px;
        border-color: var(--accent);
      }}
      .email-affix {{
        padding: 10px 0 10px 12px;
        font-size: 0.9rem;
        color: var(--muted);
        font-family: "IBM Plex Mono", monospace;
        white-space: nowrap;
        user-select: none;
        line-height: 1;
      }}
      .email-affix:last-child {{
        padding: 10px 12px 10px 0;
      }}
      .email-row input {{
        border: none;
        border-radius: 0;
        width: 72px;
        padding: 10px 2px;
        text-align: center;
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.9rem;
        outline: none;
        background: transparent;
      }}
      .packages {{
        display: grid;
        gap: 8px;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      }}
      .package {{
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 12px;
        border: 1px solid var(--border);
        border-radius: 10px;
        background: white;
        cursor: pointer;
        transition: border-color 0.15s;
      }}
      .package:has(input:checked) {{
        border-color: var(--accent);
        background: var(--accent-light);
      }}
      .package input[type="checkbox"] {{
        accent-color: var(--accent);
      }}
      button {{
        border: 0;
        border-radius: 10px;
        padding: 11px 20px;
        background: var(--accent);
        color: white;
        cursor: pointer;
        font-weight: 600;
        font-size: 0.95rem;
        transition: opacity 0.15s;
        width: 100%;
      }}
      button:hover {{
        opacity: 0.9;
      }}
      button.secondary {{
        background: white;
        color: var(--accent);
        border: 1px solid var(--accent);
      }}
      .btn-row {{
        display: flex;
        gap: 10px;
      }}
      .btn-row button {{
        flex: 1;
      }}
      .text-link {{
        background: none;
        border: 0;
        padding: 0;
        color: var(--muted);
        font-size: 0.82rem;
        cursor: pointer;
        text-decoration: underline;
        text-underline-offset: 2px;
        width: auto;
        font-weight: 400;
      }}
      .text-link:hover {{
        color: var(--text);
      }}
      .footer-links {{
        display: flex;
        gap: 16px;
        justify-content: center;
        margin-top: 20px;
      }}
      .status {{
        margin-top: 16px;
        padding: 12px 14px;
        border-radius: 10px;
        background: var(--accent-light);
        color: var(--accent);
        min-height: 44px;
        font-size: 0.9rem;
        line-height: 1.4;
      }}
      .status:empty {{
        display: none;
      }}
      .settings-section {{
        display: none;
      }}
      .settings-section.visible {{
        display: block;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>AU student digest</h1>
      <p class="muted">Weekly arXiv picks, scored for your interests.</p>

      <!-- ── Section 1: Identity + Load ── -->
      <div class="section">
        <h2>Sign in</h2>
        <div class="field">
          <label for="email-digits">AU student ID</label>
          <div class="email-row">
            <span class="email-affix">au</span>
            <input id="email-digits" type="text" inputmode="numeric" pattern="\\d{{6}}" maxlength="6" value="{safe_email.replace('au','').replace('@uni.au.dk','')}" placeholder="612345">
            <span class="email-affix">@uni.au.dk</span>
          </div>
        </div>
        <div class="field">
          <label for="password">Password</label>
          <input id="password" type="password" placeholder="Choose a password (new) or enter yours (returning)">
        </div>
        <button class="secondary" type="button" onclick="loadCurrent()">Load my settings</button>
      </div>

      <hr class="divider">

      <!-- ── Section 2: Settings (always visible, populated on load) ── -->
      <div class="section" id="settings-section">
        <h2>Your packages</h2>
        <div class="packages" style="margin-bottom: 14px;">
          {packages_markup}
        </div>
        <div class="field">
          <label for="max_papers">Max papers per week</label>
          <input id="max_papers" type="number" min="1" max="20" value="{DEFAULT_MAX_PAPERS}">
        </div>
        <div class="field">
          <label for="new_password">New password (optional)</label>
          <input id="new_password" type="password" placeholder="Leave blank to keep current">
        </div>
      </div>

      <hr class="divider">

      <!-- ── Section 3: Actions ── -->
      <div class="section">
        <div class="btn-row">
          <button id="save-btn" type="button" onclick="saveSubscription()">Subscribe</button>
        </div>
      </div>

      <div id="status" class="status"></div>

      <!-- ── Footer: rare actions as text links ── -->
      <div class="footer-links">
        <button class="text-link" type="button" onclick="resendConfirmation()">Resend confirmation email</button>
        <button class="text-link" type="button" onclick="handleUnsubscribe()" style="color: var(--danger);">Unsubscribe</button>
      </div>
    </main>
    <script>
      const mode = new URLSearchParams(window.location.search).get("mode") || "";
      const initialPackages = {initial_packages};
      const initialMaxPapers = {initial_max_papers};
      const statusEl = document.getElementById("status");

      function selectedPackages() {{
        return Array.from(document.querySelectorAll('input[name="package_ids"]:checked'))
          .map((input) => input.value);
      }}

      function setPackages(packageIds) {{
        const wanted = new Set(packageIds || []);
        document.querySelectorAll('input[name="package_ids"]').forEach((input) => {{
          input.checked = wanted.has(input.value);
        }});
      }}

      function setStatus(message, isError = false) {{
        statusEl.textContent = message;
        statusEl.style.background = isError ? "rgba(138, 59, 18, 0.08)" : "rgba(29, 91, 87, 0.08)";
        statusEl.style.color = isError ? "var(--danger)" : "var(--accent)";
        statusEl.style.display = message ? "block" : "none";
      }}

      function getEmail() {{
        const digits = document.getElementById("email-digits").value.trim();
        if (!/^\d{{6}}$/.test(digits)) {{
          throw new Error("Enter your 6-digit AU student ID.");
        }}
        return "au" + digits + "@uni.au.dk";
      }}

      async function callApi(action) {{
        const payload = {{
          action,
          email: getEmail(),
          password: document.getElementById("password").value,
          new_password: document.getElementById("new_password").value,
          max_papers_per_week: Number(document.getElementById("max_papers").value || "{DEFAULT_MAX_PAPERS}"),
          package_ids: selectedPackages(),
        }};
        const response = await fetch(window.location.pathname, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        const data = await response.json();
        if (!response.ok || !data.ok) {{
          throw new Error(data.error || "Request failed");
        }}
        return data;
      }}

      async function loadCurrent() {{
        setStatus("Loading...");
        try {{
          const data = await callApi("get");
          document.getElementById("max_papers").value = data.subscription.max_papers_per_week;
          setPackages(data.subscription.package_ids);
          document.getElementById("save-btn").textContent = "Save changes";
          setStatus("Settings loaded. Edit below and save.");
        }} catch (error) {{
          setStatus(error.message, true);
        }}
      }}

      async function saveSubscription() {{
        setStatus("Saving...");
        try {{
          const data = await callApi("upsert");
          setPackages(data.subscription.package_ids);
          document.getElementById("max_papers").value = data.subscription.max_papers_per_week;
          document.getElementById("new_password").value = "";
          document.getElementById("save-btn").textContent = "Save changes";
          const msg = "Saved. First digest arrives next Monday at 07:00 UTC.";
          if (data.confirmation_email_sent) {{
            setStatus(msg + " Confirmation email sent.");
          }} else if (data.confirmation_email_error) {{
            setStatus(msg + " Confirmation email failed: " + data.confirmation_email_error, true);
          }} else {{
            setStatus(msg);
          }}
        }} catch (error) {{
          setStatus(error.message, true);
        }}
      }}

      async function resendConfirmation() {{
        setStatus("Sending confirmation email...");
        try {{
          const data = await callApi("resend_confirmation");
          if (data.confirmation_email_sent) {{
            setStatus("Confirmation email sent. Check your inbox and spam folder.");
          }} else {{
            setStatus("Could not send: " + (data.confirmation_email_error || "unknown error"), true);
          }}
        }} catch (error) {{
          setStatus(error.message, true);
        }}
      }}

      async function handleUnsubscribe() {{
        if (!confirm("Stop receiving the AU student digest at this email?")) {{
          return;
        }}
        setStatus("Unsubscribing...");
        try {{
          await callApi("unsubscribe");
          setStatus("Unsubscribed. You can re-subscribe any time.");
        }} catch (error) {{
          setStatus(error.message, true);
        }}
      }}

      // Initialise
      document.getElementById("max_papers").value = initialMaxPapers;
      setPackages(initialPackages);
      if (mode === "unsubscribe") {{
        setStatus("Enter your password, then click Unsubscribe below.");
      }}
    </script>
  </body>
</html>"""


class handler(BaseHTTPRequestHandler):
    """Vercel Python serverless handler."""

    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        email = query.get("email", [""])[0]
        mode = query.get("mode", [""])[0]
        raw_packages = query.get("packages", [""])[0]
        package_ids: list[str]
        if raw_packages.strip():
            try:
                package_ids = normalise_package_ids(raw_packages.split(","))
            except ValueError:
                package_ids = []
        else:
            package_ids = []
        max_papers = clamp_max_papers(query.get("max_papers", [DEFAULT_MAX_PAPERS])[0])
        page = _manage_page(email, mode, package_ids, max_papers)
        payload = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, ValueError):
            self._respond(400, {"error": "invalid JSON"})
            return

        try:
            status, payload = _dispatch(body)
            self._respond(status, payload)
        except PermissionError as exc:
            self._respond(403, {"error": str(exc)})
        except FileNotFoundError as exc:
            self._respond(404, {"error": str(exc)})
        except ValueError as exc:
            self._respond(400, {"error": str(exc)})
        except Exception as exc:
            self._respond(500, {"error": str(exc)})

    def _respond(self, status: int, body: dict[str, Any]):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        """Suppress default stderr logging."""
        pass
