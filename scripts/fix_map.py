#!/usr/bin/env python3
"""Repair known problems in the Boulevard Jood place file (.rbxlx or .rbxlx.gz).

Fixes applied (all idempotent):
  1. Double-encoded (mojibake) Arabic text in prompts and signs, e.g. "Ø§Ù†Ø¶Ù…ÙŠ" -> "انضمي".
  2. PastelServer: the trampoline and slide no longer try to set the character's velocity
     from the server (the character is simulated on the player's device, so those writes are
     ignored). The obby exit pad now also clears the player's checkpoint so the fall guard does
     not teleport her back up after she leaves.
  3. New LocalScript StarterPlayerScripts/PlaygroundBounce that performs the trampoline launch
     and the slide push on the client, the same way ObbyBounce already does for the cloud obby.

Usage:
  python3 scripts/fix_map.py maps/Boulevard-Jood.rbxlx.gz            # rewrite in place
  python3 scripts/fix_map.py in.rbxlx.gz -o out.rbxlx.gz             # write elsewhere
  python3 scripts/fix_map.py maps/Boulevard-Jood.rbxlx.gz --check    # report only, no write
"""
import argparse, gzip, re, sys
from xml.sax.saxutils import escape, unescape

NUMERIC_REF = re.compile(r"&#(x[0-9A-Fa-f]+|\d+);")

def decode_refs(text):
    """Decode XML character references exactly (html.unescape would remap &#128;-&#159; to Windows-1252)."""
    text = NUMERIC_REF.sub(lambda m: chr(int(m.group(1)[1:], 16) if m.group(1)[0] == "x" else int(m.group(1))), text)
    return unescape(text, {"&quot;": '"', "&apos;": "'"})

ARABIC = re.compile(r"[؀-ۿ]")
# <string name="X">value</string> for the text properties that scripts and prompts display
STRING_PROP = re.compile(r'(<string name="(?!Name|Source)[^"]+">)([^<]*)(</string>)')

def unmojibake(value):
    """Return the repaired text when value is UTF-8 that was decoded as Latin-1, else None.

    Such text only contains characters below U+0100 (e.g. "Ø§Ù†" or "â™¡") and re-decodes
    to real Arabic or symbols ("ان", "♡"); plain ASCII or correct Arabic is left untouched.
    """
    if not value or value.isascii() or any(ord(ch) > 0xFF for ch in value):
        return None
    try:
        fixed = value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None
    return fixed if fixed != value else None

def fix_text(xml):
    count = 0
    def repl(m):
        nonlocal count
        raw = decode_refs(m.group(2))   # values are stored as numeric character references (&#216;...)
        fixed = unmojibake(raw)
        if fixed is None:
            return m.group(0)
        count += 1
        return m.group(1) + escape(fixed) + m.group(3)
    return STRING_PROP.sub(repl, xml), count

# ---------------------------------------------------------------- PastelServer patches
SERVER_PATCHES = [
    # trampoline: server-side velocity is ignored for a player-owned character; the client does it now
    (
        "bed.Touched:Connect(function(hit)\n"
        "    local p=touchedPlayer(hit);local r=p and root(p)\n"
        "    if r and r.Position.Y>bed.Position.Y and r.AssemblyLinearVelocity.Y<4 and allow(p,\"bounce\",.7) then\n"
        "        r.AssemblyLinearVelocity=Vector3.new(r.AssemblyLinearVelocity.X,70,r.AssemblyLinearVelocity.Z)\n"
        "    end\n"
        "end)\n",
        "-- The launch itself happens on the client (StarterPlayerScripts/PlaygroundBounce): the character is\n"
        "-- simulated on the player's device, so a velocity written here would be overwritten.\n",
    ),
    # slide: keep the seated state + cooldown on the server, the push happens on the client
    (
        "        h.Sit=true;r.AssemblyLinearVelocity=down*38+Vector3.new(0,-8,0)\n",
        "        h.Sit=true   -- the push down the slope is applied on the client (PlaygroundBounce); server velocity writes are ignored\n",
    ),
    # obby exit pad: leaving the course must also clear the checkpoint, or the fall guard teleports her back up
    (
        "        if r and allow(player,\"obbyExit\",1) then r.AssemblyLinearVelocity=Vector3.zero;r.CFrame=CFrame.new(landing.Position+Vector3.new(0,3.5,0)) end\n",
        "        if r and allow(player,\"obbyExit\",1) then stage[player]=0;lastHigh[player]=nil;r.AssemblyLinearVelocity=Vector3.zero;r.CFrame=CFrame.new(landing.Position+Vector3.new(0,3.5,0)) end\n",
    ),
]

def patch_server(xml):
    applied = 0
    for old, new in SERVER_PATCHES:
        if new in xml:
            continue            # already patched
        if old not in xml:
            print("WARNING: PastelServer snippet not found, skipped:", old.strip().splitlines()[0][:80], file=sys.stderr)
            continue
        xml = xml.replace(old, new, 1)
        applied += 1
    return xml, applied

# ---------------------------------------------------------------- client script
CLIENT_NAME = "PlaygroundBounce"
CLIENT_SOURCE = r'''-- Trampoline launch and slide push, run on the client. Each player's character is simulated on her own
-- device, so (exactly like ObbyBounce) a velocity change only works when it is applied here.
local Players=game:GetService("Players")
local player=Players.LocalPlayer
local map=workspace:WaitForChild("PastelBoulevard")
local playground=map:WaitForChild("Playground",60)
if not playground then return end
local function body()
    local c=player.Character
    local r=c and c:FindFirstChild("HumanoidRootPart")
    local h=c and c:FindFirstChildOfClass("Humanoid")
    if c and r and h and h.Health>0 then return c,r,h end
end
local function launch(r,h,up)
    h:ChangeState(Enum.HumanoidStateType.Jumping)
    local v=r.AssemblyLinearVelocity
    r.AssemblyLinearVelocity=Vector3.new(v.X,up,v.Z)
    task.wait()            -- the humanoid can damp the first frame; push once more
    if r.Parent and r.AssemblyLinearVelocity.Y<up*.6 then
        v=r.AssemblyLinearVelocity
        r.AssemblyLinearVelocity=Vector3.new(v.X,up,v.Z)
    end
end
-- part may be streamed out and back in, so bind again whenever the model (re)appears
local function watch(modelName,partName,cooldown,action)
    local function bind(model)
        local part=model:WaitForChild(partName,30)
        if not part then return end
        local cool=0
        part.Touched:Connect(function(hit)
            local c,r,h=body()
            if not c or not hit:IsDescendantOf(c) or os.clock()<cool then return end
            if action(part,r,h)~=false then cool=os.clock()+cooldown end
        end)
    end
    local model=playground:FindFirstChild(modelName)
    if model then task.spawn(bind,model) end
    playground.ChildAdded:Connect(function(o) if o.Name==modelName then task.spawn(bind,o) end end)
end
-- Trampoline: bounce when landing on the bed (standing still on it does nothing)
watch("Trampoline","BounceBed",.7,function(bed,r,h)
    if r.Position.Y<=bed.Position.Y or r.AssemblyLinearVelocity.Y>=4 then return false end
    launch(r,h,70)
end)
-- Slide: sit and push down the slope, whichever way the ramp faces
watch("Slide","SlideStart",2,function(start,r,h)
    local ramp=start.Parent and start.Parent:FindFirstChild("SlideRamp")
    if not ramp then return false end
    local look=ramp.CFrame.LookVector
    local down=-Vector3.new(look.X,0,look.Z).Unit
    h.Sit=true
    r.AssemblyLinearVelocity=down*38+Vector3.new(0,-8,0)
    task.delay(1.2,function() if h.Parent then h.Sit=false end end)
end)
'''

def add_client_script(xml):
    if f'<string name="Name">{CLIENT_NAME}</string>' in xml:
        return xml, False
    anchor = '<string name="Name">ObbyBounce</string>'
    i = xml.find(anchor)
    if i < 0:
        print("WARNING: ObbyBounce LocalScript not found; PlaygroundBounce not added", file=sys.stderr)
        return xml, False
    end = xml.find("</Item>", i) + len("</Item>")
    item = (f'<Item class="LocalScript" referent="RBXJOODFIX0001"><Properties><bool name="Disabled">false</bool>'
            f'<string name="Name">{CLIENT_NAME}</string><ProtectedString name="Source"><![CDATA[{CLIENT_SOURCE}]]></ProtectedString>'
            f'<token name="RunContext">0</token></Properties></Item>')
    return xml[:end] + item + xml[end:], True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("-o", "--output")
    ap.add_argument("--check", action="store_true", help="only report what would change")
    a = ap.parse_args()
    gz = a.path.endswith(".gz")
    data = gzip.open(a.path, "rb").read() if gz else open(a.path, "rb").read()
    xml = data.decode("utf-8")
    xml, n_text = fix_text(xml)
    xml, n_patch = patch_server(xml)
    xml, added = add_client_script(xml)
    print(f"mojibake strings repaired: {n_text}")
    print(f"PastelServer patches applied: {n_patch} of {len(SERVER_PATCHES)}")
    print(f"{CLIENT_NAME} LocalScript added: {added}")
    if a.check:
        return
    out = a.output or a.path
    body = xml.encode("utf-8")
    if out.endswith(".gz"):
        with gzip.open(out, "wb", compresslevel=9) as f:
            f.write(body)
    else:
        open(out, "wb").write(body)
    print(f"written: {out} ({len(body):,} bytes uncompressed)")

if __name__ == "__main__":
    main()
