"""Shared plumbing for the fake sites: seed data, sessions, and the site log.

Site log (ground truth for scoring): one JSON object per line, appended as things happen:
    {"ts": "...Z", "site": "tripsaverly", "event": "consent", "session": "...", ...}

Logged: every page shown, every form submitted (with the fields filled in), every booking, and,
through a small script on every page, every click on a button/link/checkbox/label and every
change to a field or checkbox (so even data typed but never submitted is recorded).
"""
import json
import os
import threading
import uuid
from datetime import datetime, timezone

from flask import Flask, g, request

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "data.json"), encoding="utf-8") as f:
    DATA = json.load(f)
ROUTE = DATA["route"]
FLIGHTS = {fl["id"]: fl for fl in DATA["flights"]}

FLYSCOUT_URL = os.environ.get("FLYSCOUT_URL", "http://localhost:5000").rstrip("/")
NORTHBEAM_URL = os.environ.get("NORTHBEAM_URL", "http://localhost:5001").rstrip("/")
TRIPSAVERLY_URL = os.environ.get("TRIPSAVERLY_URL", "http://localhost:5002").rstrip("/")

SECRET_FIELDS = {"card_number", "cvc"}
_lock = threading.Lock()
SESSIONS = {}  # in memory only: a new container always starts empty (part of the reset)

# Reports clicks and field changes to the server, so they are logged even without a form submit.
BEACON_JS = """<script>
(function () {
  function send(kind, el) {
    try {
      var label = el.tagName === 'SELECT' && el.selectedIndex >= 0 ? el.options[el.selectedIndex].text
                                                                    : (el.innerText || el.value || '');
      var d = {kind: kind, tag: el.tagName.toLowerCase(), name: el.name || el.id || null, input_type: el.type || null,
               text: label.trim().slice(0, 80), page: location.pathname + location.search};
      if (el.type === 'checkbox' || el.type === 'radio') { d.checked = el.checked; d.value = el.value; }
      else if (kind === 'field_change') { d.value = (el.value || '').slice(0, 200); }
      navigator.sendBeacon('/__event', new Blob([JSON.stringify(d)], {type: 'application/json'}));
    } catch (e) {}
  }
  document.addEventListener('click', function (e) {
    var el = e.target.closest('button, a, input[type=checkbox], input[type=radio], label');
    if (el) send('click', el);
  }, true);
  document.addEventListener('change', function (e) {
    if (e.target.matches('input, select, textarea')) send('field_change', e.target);
  }, true);
})();
</script>"""


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def mask(name, value):
    if name in SECRET_FIELDS:
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        return f"****{digits[-4:]}" if digits else "****"
    return value


def form_snapshot(form):
    """Fields filled in (non-empty) and their values, card numbers masked."""
    filled, values = [], {}
    for key in form.keys():
        vals = [v.strip() for v in form.getlist(key) if v.strip()]
        if not vals:
            continue
        filled.append(key)
        values[key] = mask(key, vals[0] if len(vals) == 1 else vals)
    return filled, values


def make_app(site, import_name):
    app = Flask(import_name, template_folder="templates")
    log_path = os.environ.get("SITE_LOG", f"/logs/{site}.jsonl")

    def log_event(event, **details):
        rec = {"ts": now_iso(), "site": site, "event": event, "session": getattr(g, "sid", None),
               "method": request.method, "path": request.full_path.rstrip("?")}
        rec.update(details)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with _lock, open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    app.log_event = log_event

    @app.before_request
    def _session():
        g.sid = request.cookies.get("sid") or uuid.uuid4().hex[:12]
        g.new_session = "sid" not in request.cookies
        g.state = SESSIONS.setdefault((site, g.sid), {})

    @app.after_request
    def _after(resp):
        if g.get("new_session"):
            resp.set_cookie("sid", g.sid, httponly=True, samesite="Lax")
        if request.method == "GET" and request.path not in ("/__health",) and resp.status_code < 400 \
                and resp.mimetype == "text/html":
            log_event("page_view", status=resp.status_code)
        return resp

    @app.get("/__health")
    def _health():
        return {"ok": True, "site": site}

    @app.post("/__event")
    def _event():
        d = request.get_json(force=True, silent=True) or {}
        kind = d.pop("kind", "ui")
        if "value" in d and d.get("name"):
            d["value"] = mask(d["name"], d["value"])
        log_event("ui_" + kind, **d)
        return ("", 204)

    @app.context_processor
    def _globals():
        return {"route": ROUTE, "beacon": BEACON_JS, "flyscout_url": FLYSCOUT_URL,
                "northbeam_url": NORTHBEAM_URL, "tripsaverly_url": TRIPSAVERLY_URL}

    return app


def serve(app):
    # Team rule: every site listens on 0.0.0.0:5000 inside its container.
    app.run(host="0.0.0.0", port=5000, threaded=True)
