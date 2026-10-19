#!/usr/bin/env python3
"""Validate a saved Roblox place, or publish it through Roblox Open Cloud."""

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MAX_SIZE = 100 * 1024 * 1024
# Includes the subclasses of PartOperation and BaseWrap.
STUDIO_ONLY = {
    "EditableImage", "EditableMesh", "PartOperation", "UnionOperation",
    "NegateOperation", "IntersectOperation", "SurfaceAppearance",
    "BaseWrap", "WrapLayer", "WrapTarget",
}


class PublishError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward an API key to a redirected destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def inspect_place(filename):
    path = (ROOT / filename).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise PublishError("Map must be an existing file inside this repository.")
    compressed = path.suffix.lower() == ".gz"
    extension = path.with_suffix("").suffix.lower() if compressed else path.suffix.lower()
    if extension not in {".rbxlx", ".rbxl"}:
        raise PublishError("Select a .rbxlx or .rbxl place, optionally gzip-compressed.")
    if not 0 < path.stat().st_size <= MAX_SIZE:
        raise PublishError("Map must be non-empty and no larger than 100 MiB.")
    data = path.read_bytes()
    if compressed:
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as archive:
                data = archive.read(MAX_SIZE + 1)
        except (OSError, EOFError):
            raise PublishError("Invalid gzip map archive.") from None
    if not 0 < len(data) <= MAX_SIZE:
        raise PublishError("Decompressed map must be non-empty and no larger than 100 MiB.")
    info = {
        "file": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if extension == ".rbxlx":
        if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
            raise PublishError("XML DTDs and entity declarations are not supported.")
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise PublishError("Map is not valid XML.") from exc
        if root.tag != "roblox" or root.get("version") != "4":
            raise PublishError("Expected a Roblox version 4 XML place.")
        classes = [item.get("class") for item in root.iter("Item")]
        if "Workspace" not in classes:
            raise PublishError("This file does not contain a Workspace.")
        unsupported = STUDIO_ONLY.intersection(classes)
        if unsupported:
            raise PublishError(
                "Publish from Roblox Studio: Open Cloud cannot update these saved "
                "instance types: " + ", ".join(sorted(unsupported))
            )
        info["instances"] = len(classes)
        content_type = "application/xml"
    else:
        if not data.startswith(b"<roblox!\x89\xff\r\n\x1a\n"):
            raise PublishError("Invalid binary Roblox place header.")
        info["note"] = "Binary header checked; instance types require Studio review."
        content_type = "application/octet-stream"
    return data, content_type, info


def positive_id(value, name):
    value = value.strip()
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise PublishError(f"{name} must be a positive numeric ID.")
    return value


def publish(data, content_type, universe_id, place_id, api_key):
    universe_id = positive_id(universe_id, "Universe ID")
    place_id = positive_id(place_id, "Place ID")
    if not api_key.strip():
        raise PublishError("Missing repository secret ROBLOX_API_KEY.")
    if "\n" in api_key.strip() or "\r" in api_key.strip():
        raise PublishError("ROBLOX_API_KEY contains an unexpected line break.")
    url = (
        f"https://apis.roblox.com/universes/v1/{universe_id}"
        f"/places/{place_id}/versions?versionType=Published"
    )
    request = urllib.request.Request(
        url, data=data, method="POST",
        headers={"x-api-key": api_key.strip(), "Content-Type": content_type},
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=180) as response:
            if not 200 <= response.status < 300:
                raise PublishError("Roblox returned an unexpected HTTP status.")
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        # Do not print request headers or the untrusted response body.
        hints = {
            400: "Check that Place ID belongs to Universe ID and the file is a saved place.",
            401: "Check ROBLOX_API_KEY and its expiration date.",
            403: "Check universe-places Write access and the key's allowed IP ranges.",
            404: "Check Universe ID, Place ID, and API key access to this experience.",
            413: "The place file is too large.",
            429: "Roblox rate limit reached. Check the dashboard before retrying.",
        }
        raise PublishError(
            f"Roblox HTTP {exc.code}. " + hints.get(exc.code, "Check the Creator Dashboard before retrying.")
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise PublishError(
            "Network failure. Publication status is unknown; check the Creator Dashboard before retrying."
        ) from None
    except (ValueError, UnicodeError):
        raise PublishError("Invalid Roblox response; check the Creator Dashboard before retrying.") from None
    version = result.get("versionNumber") if isinstance(result, dict) else None
    if type(version) is not int or version < 1:
        raise PublishError("Roblox did not return a valid versionNumber; check the Creator Dashboard.")
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "publish"])
    parser.add_argument("file", nargs="?", default="maps/Boulevard-Jood.rbxlx.gz")
    args = parser.parse_args()
    data, content_type, info = inspect_place(args.file)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    if args.command == "validate":
        return
    universe_id = positive_id(os.environ.get("ROBLOX_UNIVERSE_ID", ""), "Universe ID")
    place_id = positive_id(os.environ.get("ROBLOX_PLACE_ID", ""), "Place ID")
    version = publish(data, content_type, universe_id, place_id, os.environ.get("ROBLOX_API_KEY", ""))
    print(f"Published successfully. Roblox version: {version}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as output:
            output.write(
                f"## تم رفع الماب بنجاح\n\n"
                f"- Universe ID: `{universe_id}`\n"
                f"- Place ID: `{place_id}`\n"
                f"- Roblox version: `{version}`\n"
                f"- SHA-256: `{info['sha256']}`\n"
                f"- [فتح الماب](https://www.roblox.com/games/{place_id})\n"
            )


if __name__ == "__main__":
    try:
        main()
    except PublishError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
