"""Check only whether the existing repository key can upload Najd assets.
The key stays in the Actions environment and is never logged or returned.
"""
import json
import os
import sys
import urllib.error
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def main():
    key = os.environ.get("ROBLOX_API_KEY", "").strip()
    if not key:
        print(json.dumps({"status": "missing_repository_secret", "asset_write": False}))
        return 1
    request = urllib.request.Request(
        "https://apis.roblox.com/api-keys/v1/introspect",
        data=json.dumps({"apiKey": key}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            result = json.loads(response.read(65536))
    except urllib.error.HTTPError as error:
        print(json.dumps({"status": "introspection_http_error", "http_status": error.code}))
        return 1
    except Exception:
        print(json.dumps({"status": "introspection_unavailable"}))
        return 1
    scopes = result.get("scopes", [])
    assets = [s for s in scopes if s.get("name") in ("asset", "assets")]
    operations = {str(v).lower() for s in assets for v in s.get("operations", [])}
    # Log only the two capabilities needed for this task, never the secret, owner,
    # other resource identifiers, or the raw introspection response.
    safe = {"status": "checked", "enabled": result.get("enabled") is True,
            "expired": result.get("expired") is True,
            "asset_read": "read" in operations, "asset_write": "write" in operations}
    print(json.dumps(safe, sort_keys=True))
    return 0

if __name__ == "__main__":
    sys.exit(main())
