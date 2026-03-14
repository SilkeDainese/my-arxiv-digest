import relay.api.send as relay_send
from pathlib import Path
import json


class _FakeHandler:
    def __init__(self):
        self.response = None

    def _respond(self, status, body):
        self.response = (status, body)


def test_relay_get_only_returns_health_status():
    fake = _FakeHandler()

    relay_send.handler.do_GET(fake)

    assert fake.response == (
        200,
        {"status": "arXiv Digest relay is running"},
    )


def test_relay_root_health_page_exists():
    root_page = Path(__file__).resolve().parents[1] / "relay" / "index.html"
    html = root_page.read_text()

    assert "arXiv Digest relay is running" in html
    assert "GET /api/send" in html
    assert "POST /api/send" in html


def test_relay_vercel_config_rewrites_root_to_health_page():
    config_path = Path(__file__).resolve().parents[1] / "relay" / "vercel.json"
    config = json.loads(config_path.read_text())

    assert {"source": "/", "destination": "/index.html"} in config["rewrites"]
