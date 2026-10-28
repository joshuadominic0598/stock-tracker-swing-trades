"""Map API requests to application operations without transport or SQL concerns."""

import threading
from urllib.parse import parse_qs

from swing_signal import workspace
from swing_signal.ai import intelligence, providers, settings
from swing_signal.data import attention, market, storage

def get(path, query=""):
    if path == "/api/health":
        return dict(ok=True, app="signaldesk", version="2.1.0"), 200
    if path == "/api/overview":
        overview = market.overview()
        overview["connections"] = settings.public()
        return overview, 200
    if path == "/api/connections":
        return settings.public(), 200
    if path == "/api/catalog":
        search = parse_qs(query).get("q", [""])[0].strip().upper()
        return market.search_catalog(search), 200
    if path == "/api/models":
        return intelligence.models(), 200
    if path == "/api/backup":
        return workspace.export(), 200
    parts = path.strip("/").split("/")
    if len(parts) == 3 and parts[:2] in (["api", "assets"], ["api", "research"]):
        asset = storage.asset(parts[2])
        if not asset:
            return dict(error="Unknown asset"), 404
        if parts[1] == "research":
            return market.research(asset), 200
        timeframe = parse_qs(query).get("timeframe", ["1d"])[0]
        if timeframe not in ("1d", "1w"):
            raise ValueError("Use daily or weekly timeframe")
        return market.asset_detail(asset, timeframe), 200
    if path.startswith("/api/"):
        return dict(error="Unknown endpoint"), 404
    return None

def post(path, body):
    if path == "/api/connections/check":
        return providers.check_connection(
            str(body.get("provider", "")), str(body.get("model", ""))
        ), 200
    if path == "/api/connections":
        settings.update(body)
        return settings.public(), 200
    if path == "/api/refresh-quotes":
        threading.Thread(target=market.refresh_quotes, kwargs={"force": True}, daemon=True).start()
        return dict(started=True), 200
    if path == "/api/refresh":
        return dict(started=market.refresh(), refresh=market.get_state()), 200
    if path == "/api/assets":
        return workspace.add_asset(body), 200
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "assets"]:
        return dict(error="Unknown endpoint"), 404
    asset = storage.asset(parts[2])
    if not asset:
        return dict(error="Unknown asset"), 404
    return asset_action(asset, parts[3], body)

def asset_action(asset, action, body):
    edits = {
        "zone": workspace.save_zone,
        "delete-zone": workspace.delete_zone,
        "position": workspace.save_position,
        "journal": workspace.save_journal,
    }
    if action in edits:
        edits[action](asset, body)
        return dict(ok=True), 200
    if action == "trends-import":
        return attention.import_trends(asset, body.get("csv", "")), 200
    if action == "ai-brief":
        timeframe = body.get("timeframe", "1d")
        if timeframe not in ("1d", "1w"):
            raise ValueError("Choose daily or weekly timeframe")
        return intelligence.generate(
            asset, str(body.get("model", "")), timeframe, str(body.get("provider", "local"))
        ), 200
    return dict(error="Unknown action"), 404
