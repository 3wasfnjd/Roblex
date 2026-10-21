#!/usr/bin/env python3
"""Bundle the shared modules with tools/test_rules.lua and run it with the luau CLI (path in $LUAU or on PATH)."""
import os, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def module(rel):
    src = open(os.path.join(ROOT, "src", rel), encoding="utf-8").read()
    return "(function()\n" + src + "\nend)()"
bundle = ("Config = " + module("ReplicatedStorage/IslandRace/Config.lua") + "\n" +
          "Rules = " + module("ReplicatedStorage/IslandRace/Rules.lua") + "\n" +
          open(os.path.join(ROOT, "tools", "test_rules.lua"), encoding="utf-8").read())
luau = os.environ.get("LUAU") or shutil.which("luau")
if not luau:
    print("luau CLI not found (set $LUAU)"); sys.exit(2)
with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as f:
    f.write(bundle); path = f.name
try:
    sys.exit(subprocess.call([luau, path]))
finally:
    os.unlink(path)
