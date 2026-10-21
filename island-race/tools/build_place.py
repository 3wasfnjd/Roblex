#!/usr/bin/env python3
"""Build the Island Race place file (.rbxlx.gz) from island-race/src and generated geometry.

The geometry is a playable placeholder made of plain parts: the harbour island, the forest island,
the bridges and one race track with grid, checkpoints, boost pads, jump pads and coins. Decoration
spots are marked with invisible "MeshAnchor" parts (child StringValue "Model") so the Kenney meshes
can be dropped in later without touching the scripts.

Usage: python3 island-race/tools/build_place.py [-o island-race/build/Island-Race.rbxlx.gz]
"""
import argparse, gzip, math, os
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

# ---------------------------------------------------------------- xml helpers
_ref = 0
def ref():
    global _ref; _ref += 1
    return f"RBXIR{_ref:07d}"

MATERIAL = {"Plastic": 256, "SmoothPlastic": 272, "Neon": 288, "Wood": 512, "WoodPlanks": 528, "Slate": 800, "Concrete": 816,
            "Metal": 1088, "Grass": 1280, "Sand": 1296, "Ice": 1536, "Glass": 1568, "Fabric": 1312}
SHAPE = {"Ball": 0, "Block": 1, "Cylinder": 2}

def color_u32(r, g, b):
    return (0xFF << 24) | (r << 16) | (g << 8) | b

def cframe_xml(name, pos, rot):
    (x, y, z) = pos
    r = rot
    return (f'<CoordinateFrame name="{name}"><X>{x:.4f}</X><Y>{y:.4f}</Y><Z>{z:.4f}</Z>'
            f'<R00>{r[0][0]:.6f}</R00><R01>{r[0][1]:.6f}</R01><R02>{r[0][2]:.6f}</R02>'
            f'<R10>{r[1][0]:.6f}</R10><R11>{r[1][1]:.6f}</R11><R12>{r[1][2]:.6f}</R12>'
            f'<R20>{r[2][0]:.6f}</R20><R21>{r[2][1]:.6f}</R21><R22>{r[2][2]:.6f}</R22></CoordinateFrame>')

IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))

def norm(v):
    l = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / l for c in v)
def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def add(a, b): return tuple(x + y for x, y in zip(a, b))
def mul(a, s): return tuple(x * s for x in a)
def dist(a, b): return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

def look_rot(direction, up=(0, 1, 0)):
    """Rotation whose -Z axis points along direction (like CFrame.lookAt)."""
    z = norm(mul(norm(direction), -1))
    x = norm(cross(up, z))
    if abs(x[0]) + abs(x[1]) + abs(x[2]) < 1e-6:
        x = (1, 0, 0)
    y = cross(z, x)
    return ((x[0], y[0], z[0]), (x[1], y[1], z[1]), (x[2], y[2], z[2]))

def yaw_rot(radians):
    c, s = math.cos(radians), math.sin(radians)
    return ((c, 0, s), (0, 1, 0), (-s, 0, c))

class Node:
    def __init__(self, cls, name, props=None, children=None):
        self.cls, self.name, self.props, self.children = cls, name, props or [], children or []
    def add(self, child):
        self.children.append(child); return child
    def xml(self, depth=1):
        pad = "\t" * depth
        out = [f'{pad}<Item class="{self.cls}" referent="{ref()}">', f'{pad}\t<Properties>',
               f'{pad}\t\t<string name="Name">{escape(self.name)}</string>']
        out += [f"{pad}\t\t{p}" for p in self.props]
        out.append(f"{pad}\t</Properties>")
        out += [c.xml(depth + 1) for c in self.children]
        out.append(f"{pad}</Item>")
        return "\n".join(out)

def part(name, pos, size, color=(200, 200, 200), material="SmoothPlastic", rot=IDENTITY, anchored=True, collide=True,
         transparency=0.0, shape="Block", cls="Part", touch=None, query=None, cast_shadow=None):
    props = [f'<bool name="Anchored">{"true" if anchored else "false"}</bool>',
             f'<bool name="CanCollide">{"true" if collide else "false"}</bool>',
             cframe_xml("CFrame", pos, rot),
             f'<Color3uint8 name="Color3uint8">{color_u32(*color)}</Color3uint8>',
             f'<token name="Material">{MATERIAL[material]}</token>',
             f'<Vector3 name="size"><X>{size[0]:.4f}</X><Y>{size[1]:.4f}</Y><Z>{size[2]:.4f}</Z></Vector3>',
             f'<float name="Transparency">{transparency}</float>',
             '<token name="TopSurface">0</token>', '<token name="BottomSurface">0</token>']
    if cls == "Part":
        props.append(f'<token name="shape">{SHAPE[shape]}</token>')
    if touch is not None: props.append(f'<bool name="CanTouch">{"true" if touch else "false"}</bool>')
    if query is not None: props.append(f'<bool name="CanQuery">{"true" if query else "false"}</bool>')
    if cast_shadow is not None: props.append(f'<bool name="CastShadow">{"true" if cast_shadow else "false"}</bool>')
    return Node(cls, name, props)

def folder(name): return Node("Folder", name)
def model(name): return Node("Model", name)
def string_value(name, value): return Node("StringValue", name, [f'<string name="Value">{escape(value)}</string>'])
def prompt(name, action, obj, hold=0.0, distance=10):
    return Node("ProximityPrompt", name, [f'<string name="ActionText">{escape(action)}</string>', f'<string name="ObjectText">{escape(obj)}</string>',
                                          f'<float name="HoldDuration">{hold}</float>', f'<float name="MaxActivationDistance">{distance}</float>',
                                          '<bool name="RequiresLineOfSight">false</bool>'])
def anchor(name, pos, size, model_name, yaw=0.0):
    a = part(name, pos, size, (255, 255, 255), "SmoothPlastic", yaw_rot(yaw), collide=False, transparency=1.0, touch=False, query=False)
    a.add(string_value("Model", model_name))
    return a

def script_node(cls, name, source):
    source = source.replace("]]>", "]]]]><![CDATA[>")
    props = ['<bool name="Disabled">false</bool>', f'<ProtectedString name="Source"><![CDATA[{source}]]></ProtectedString>']
    if cls != "ModuleScript": props.append('<token name="RunContext">0</token>')
    return Node(cls, name, props)

def load_scripts(dirpath):
    """Map a src folder to script nodes: *.server.lua -> Script, *.client.lua -> LocalScript, *.lua -> ModuleScript."""
    nodes = []
    for entry in sorted(os.listdir(dirpath)):
        full = os.path.join(dirpath, entry)
        if os.path.isdir(full):
            f = folder(entry)
            for n in load_scripts(full): f.add(n)
            nodes.append(f)
        elif entry.endswith(".lua"):
            src = open(full, encoding="utf-8").read()
            if entry.endswith(".server.lua"): cls, name = "Script", entry[:-11]
            elif entry.endswith(".client.lua"): cls, name = "LocalScript", entry[:-11]
            else: cls, name = "ModuleScript", entry[:-4]
            nodes.append(script_node(cls, name, src))
    return nodes

# ---------------------------------------------------------------- world
GRASS = (96, 190, 110); SAND = (236, 214, 160); ROAD = (70, 78, 96); LINE = (245, 245, 245); RAIL = (255, 150, 40)
WOOD = (150, 105, 70); ROCK = (120, 125, 140); NAVY = (22, 30, 60); BLUE = (60, 150, 255); CLOUD = (240, 246, 255)

def island(parent, name, center, size_xz, top_y, color=GRASS, thickness=14, rim=SAND):
    cx, cz = center; w, d = size_xz
    parent.add(part(name, (cx, top_y - thickness / 2, cz), (w, thickness, d), color, "Grass"))
    parent.add(part(name + "Rim", (cx, top_y - thickness - 3, cz), (w + 6, 6, d + 6), rim, "Sand"))
    parent.add(part(name + "Base", (cx, top_y - thickness - 14, cz), (w * 0.7, 16, d * 0.7), ROCK, "Slate"))

def build_track(track, waypoints, width=14.0):
    """waypoints: list of dicts {p:(x,y,z), cp, boost, jump, gap, coins, trees}.
    Road segments join consecutive points; 'gap' leaves out the segment after that point."""
    road = track.add(folder("Road")); rails = track.add(folder("Rails"))
    cps = track.add(folder("Checkpoints")); boosts = track.add(folder("Boosts")); jumps = track.add(folder("JumpPads"))
    coins = track.add(folder("Coins")); decor = track.add(folder("Decor"))
    n = len(waypoints); cp_i = 0; coin_i = 0
    for i in range(n):
        a = waypoints[i]; b = waypoints[(i + 1) % n]
        pa, pb = a["p"], b["p"]
        direction = sub(pb, pa); length = dist(pa, pb)
        rot = look_rot(direction)
        mid = add(pa, mul(direction, 0.5))
        right = norm(cross((0, 1, 0), norm(direction)))
        if not a.get("gap"):
            road.add(part("Segment", (mid[0], mid[1] - 0.5, mid[2]), (width, 1, length + width * 0.55), ROAD, "Concrete", rot))
            for s in (-1, 1):
                off = mul(right, s * (width / 2 - 0.5))
                rails.add(part("Rail", add((mid[0], mid[1] + 0.35, mid[2]), off), (0.5, 0.7, length + width * 0.3), RAIL, "Neon", rot, collide=False, cast_shadow=False))
            if a.get("boost"):
                for k in range(2):
                    p = add(pa, mul(direction, 0.35 + k * 0.3))
                    boosts.add(part("Boost", (p[0], p[1] + 0.15, p[2]), (width - 3, 0.3, 6), (90, 230, 255), "Neon", rot, collide=False))
            cnt = a.get("coins", 0)
            for k in range(cnt):
                p = add(pa, mul(direction, (k + 1) / (cnt + 1)))
                coin_i += 1
                coins.add(part(f"Coin{coin_i}", (p[0], p[1] + 3.2, p[2]), (0.5, 0.5, 0.5), (255, 205, 60), "Neon", IDENTITY, collide=False, transparency=1.0, touch=False, query=False))
        if a.get("jump"):
            prev = sub(pa, waypoints[i - 1]["p"])
            p = sub(pa, mul(norm(prev), 5))
            jumps.add(part("JumpPad", (p[0], p[1] + 0.3, p[2]), (width - 4, 0.6, 5), (255, 120, 60), "Neon", look_rot(prev)))
        if a.get("cp"):
            cp_i += 1
            cps.add(part(f"CP{cp_i}", (pa[0], pa[1] + 7, pa[2]), (width + 6, 14, 10), (255, 255, 255), "Neon", rot, collide=False, transparency=0.94, touch=False, query=False))
            for s in (-1, 1):
                q = add(pa, mul(right, s * (width / 2 + 1)))
                rails.add(part("Pylon", (q[0], q[1] + 4, q[2]), (1.2, 8, 1.2), BLUE, "Neon", IDENTITY, collide=False))
                decor.add(anchor("FlagSpot", (q[0], q[1] + 4, q[2]), (2, 8, 2), "kenney-racing-kit/flagCheckersSmall"))
        for k in range(a.get("trees", 0)):
            p = add(pa, mul(direction, (k + 0.5) / a["trees"]))
            s = -1 if k % 2 else 1
            q = add(p, mul(right, s * (width / 2 + 7)))
            rails.add(part("Tree", (q[0], q[1] + 4, q[2]), (1.2, 8, 1.2), WOOD, "Wood", IDENTITY))
            rails.add(part("Leaves", (q[0], q[1] + 10, q[2]), (7, 8, 7), (70, 170, 90), "Grass", IDENTITY, shape="Ball"))
            decor.add(anchor("TreeSpot", (q[0], q[1] + 6, q[2]), (6, 12, 6), "kenney-nature-kit/tree_default", yaw=k * 1.3))
    return cp_i

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("-o", "--output", default=os.path.join(ROOT, "build", "Island-Race.rbxlx.gz"))
    a = ap.parse_args()

    workspace = Node("Workspace", "Workspace", ['<bool name="StreamingEnabled">false</bool>', '<float name="Gravity">196.2</float>'])
    game_model = workspace.add(model("IslandRace"))
    islands = game_model.add(folder("Islands"))
    lobby = game_model.add(model("Lobby"))
    tracks = game_model.add(folder("Tracks"))

    islands.add(part("CloudSea", (0, -60, 150), (1400, 2, 1400), CLOUD, "SmoothPlastic", collide=False, transparency=0.15, touch=False, query=False))
    for i in range(14):
        ang = i * 0.9; r = 240 + (i % 4) * 70
        islands.add(part("CloudPuff", (math.cos(ang) * r, -50 + (i % 3) * 6, 150 + math.sin(ang) * r), (60 + (i % 3) * 20, 10, 40 + (i % 2) * 20), CLOUD, "SmoothPlastic", yaw_rot(ang), collide=False, transparency=0.05, touch=False, query=False, shape="Ball"))

    island(islands, "Harbour", (0, 15), (250, 240), 0)
    island(islands, "Forest", (-5, 300), (200, 220), 0, color=(80, 160, 95))

    lobby.add(Node("SpawnLocation", "Spawn", ['<bool name="Anchored">true</bool>', '<bool name="CanCollide">true</bool>', cframe_xml("CFrame", (0, 0.5, 0), IDENTITY),
        f'<Color3uint8 name="Color3uint8">{color_u32(*BLUE)}</Color3uint8>', f'<token name="Material">{MATERIAL["SmoothPlastic"]}</token>',
        '<Vector3 name="size"><X>12</X><Y>1</Y><Z>12</Z></Vector3>', '<int name="Duration">0</int>', '<bool name="Neutral">true</bool>']))
    lobby.add(part("Plaza", (0, -0.2, 0), (60, 0.6, 60), (225, 228, 236), "Concrete"))
    jp = lobby.add(part("JoinPoint", (0, 3, -22), (2, 6, 2), (70, 210, 120), "Neon")); jp.add(prompt("Join", "انضم للسباق", "بوابة السباق"))
    lobby.add(part("JoinArch", (0, 7, -22), (14, 1.2, 1.2), (70, 210, 120), "Neon", collide=False))
    lobby.add(part("JoinPost", (-7, 3.5, -22), (1.2, 7, 1.2), (70, 210, 120), "Neon")); lobby.add(part("JoinPost", (7, 3.5, -22), (1.2, 7, 1.2), (70, 210, 120), "Neon"))
    sp = lobby.add(part("ShopPoint", (24, 3, 0), (6, 6, 6), (255, 150, 40), "SmoothPlastic")); sp.add(prompt("Shop", "افتح المتجر", "كراج المركبات"))
    lobby.add(part("ShopRoof", (24, 6.8, 0), (9, 0.8, 9), NAVY, "SmoothPlastic", collide=False))
    lobby.add(anchor("ShopDecor", (24, 3, 0), (8, 8, 8), "kenney-racing-kit/pitsGarage", yaw=math.pi / 2))
    lobby.add(part("Board", (-26, 8, 0), (0.6, 14, 30), NAVY, "SmoothPlastic", yaw_rot(-math.pi / 2)))
    lobby.add(part("BoardPost", (-26, 0.5, -14), (1, 2, 1), NAVY, "SmoothPlastic")); lobby.add(part("BoardPost", (-26, 0.5, 14), (1, 2, 1), NAVY, "SmoothPlastic"))
    lobby.add(part("Sign", (0, 9.5, -22), (16, 3.5, 0.5), NAVY, "SmoothPlastic", yaw_rot(math.pi)))
    for k in range(6):
        ang = k * math.pi / 3
        q = (math.cos(ang) * 34, 0, math.sin(ang) * 34)
        lobby.add(part("Lamp", (q[0], 5, q[2]), (0.6, 10, 0.6), ROCK, "Metal")); lobby.add(part("LampLight", (q[0], 10.3, q[2]), (1.6, 1.6, 1.6), (255, 240, 200), "Neon", shape="Ball", collide=False))
        lobby.add(anchor("LampSpot", (q[0], 5, q[2]), (2, 10, 2), "kenney-racing-kit/lightPostModern"))

    # ------------------------------------------------ track: harbour loop + two bridges + forest hill
    W = 14
    P = lambda x, y, z, **k: dict(p=(x, y, z), **k)
    waypoints = [
        P(-40, 0, -80, coins=0, trees=3),                      # start line
        P(40, 0, -80, boost=True, coins=3),
        P(90, 0, -50, cp=True, coins=3, trees=2),
        P(100, 0, 10, coins=3),
        P(70, 0, 60, cp=True, coins=2, trees=3),
        P(30, 0, 105, coins=2),
        P(30, 2, 150, jump=True, gap=True),                    # north bridge: jump pad, then a gap
        P(30, 2, 172, coins=2),                                # landing
        P(30, 1, 215, cp=True, coins=2, trees=2),
        P(60, 3, 262, coins=3, trees=3),
        P(62, 8, 330, cp=True, coins=3),                       # hill top
        P(20, 6, 380, boost=True, coins=2, trees=3),
        P(-40, 4, 382, coins=2),
        P(-70, 2, 332, cp=True, coins=3, trees=3),
        P(-62, 0, 262, coins=3),
        P(-30, 0, 215, cp=True, coins=2),
        P(-30, 0, 160, boost=True, coins=3),                   # south bridge: solid, boost pads
        P(-30, 0, 105, coins=2, trees=2),
        P(-70, 0, 60, cp=True, coins=2),
        P(-100, 0, 10, coins=3, trees=3),
        P(-90, 0, -50, cp=True, coins=2),
    ]
    track = tracks.add(model("Harbour"))
    cp_count = build_track(track, waypoints, W)
    start = waypoints[0]["p"]; direction = sub(waypoints[1]["p"], start); rot = look_rot(direction)
    right = norm(cross((0, 1, 0), norm(direction))); back = norm(mul(direction, -1))
    track.add(part("StartLine", (start[0], start[1] + 7, start[2]), (W + 6, 14, 10), LINE, "Neon", rot, collide=False, transparency=0.94, touch=False, query=False))
    track.add(part("StartStripe", (start[0], start[1] + 0.12, start[2]), (W, 0.25, 2.5), LINE, "SmoothPlastic", rot, collide=False))
    track.add(part("StartArch", (start[0], start[1] + 11, start[2]), (W + 8, 2, 2), RAIL, "Neon", rot, collide=False))
    for s in (-1, 1):
        q = add(start, mul(right, s * (W / 2 + 3)))
        track.add(part("ArchPost", (q[0], q[1] + 5.5, q[2]), (1.5, 11, 1.5), NAVY, "SmoothPlastic"))
    track.add(anchor("StartDecor", (start[0], start[1] + 6, start[2]), (W + 8, 12, 4), "kenney-racing-kit/roadStart", yaw=math.atan2(direction[0], -direction[2])))
    grid = track.add(folder("Grid"))
    for i in range(8):
        col = i % 2; row = i // 2
        q = add(add(start, mul(back, 6 + row * 7)), mul(right, (-1 if col == 0 else 1) * 3.5))
        grid.add(part(f"Slot{i + 1}", (q[0], q[1] + 0.12, q[2]), (3, 0.25, 5), LINE, "SmoothPlastic", rot, collide=False, transparency=0.4, touch=False, query=False))
    gs = add(start, mul(right, -(W / 2 + 12)))
    track.add(part("StandBase", (gs[0], gs[1] + 1.5, gs[2]), (10, 3, 40), (200, 60, 60), "SmoothPlastic", rot))
    track.add(part("StandTop", (gs[0] - 3, gs[1] + 4.5, gs[2]), (4, 3, 40), (220, 90, 90), "SmoothPlastic", rot))
    track.add(anchor("StandDecor", (gs[0], gs[1] + 3, gs[2]), (10, 6, 40), "kenney-racing-kit/grandStand", yaw=math.atan2(direction[0], -direction[2])))

    # ------------------------------------------------ services
    lighting = Node("Lighting", "Lighting", ['<float name="ClockTime">14.5</float>', '<float name="Brightness">2.2</float>', '<token name="Technology">1</token>',
        '<Color3 name="Ambient"><R>0.45</R><G>0.5</G><B>0.6</B></Color3>', '<Color3 name="OutdoorAmbient"><R>0.55</R><G>0.6</G><B>0.7</B></Color3>', '<bool name="GlobalShadows">true</bool>'])
    lighting.add(Node("Atmosphere", "Atmosphere", ['<float name="Density">0.3</float>', '<float name="Haze">1.5</float>', '<Color3 name="Color"><R>0.78</R><G>0.86</G><B>1</B></Color3>', '<Color3 name="Decay"><R>0.6</R><G>0.7</G><B>0.9</B></Color3>', '<float name="Glare">0.2</float>']))
    lighting.add(Node("BloomEffect", "Bloom", ['<float name="Intensity">0.4</float>', '<float name="Size">24</float>', '<float name="Threshold">1.5</float>']))

    rs = Node("ReplicatedStorage", "ReplicatedStorage")
    shared = rs.add(folder("IslandRace"))
    for n in load_scripts(os.path.join(SRC, "ReplicatedStorage", "IslandRace")): shared.add(n)
    remotes = shared.add(folder("Remotes"))
    for name in ("State", "Action", "Notice", "Race"): remotes.add(Node("RemoteEvent", name))

    sss = Node("ServerScriptService", "ServerScriptService")
    for n in load_scripts(os.path.join(SRC, "ServerScriptService")): sss.add(n)

    sp_ = Node("StarterPlayer", "StarterPlayer", ['<float name="CharacterWalkSpeed">22</float>', '<float name="CharacterJumpPower">50</float>', '<bool name="CharacterUseJumpPower">true</bool>', '<float name="CameraMaxZoomDistance">60</float>'])
    sps = sp_.add(Node("StarterPlayerScripts", "StarterPlayerScripts"))
    for n in load_scripts(os.path.join(SRC, "StarterPlayer", "StarterPlayerScripts")): sps.add(n)
    sp_.add(Node("StarterCharacterScripts", "StarterCharacterScripts"))

    players = Node("Players", "Players", ['<bool name="CharacterAutoLoads">true</bool>', '<float name="RespawnTime">3</float>'])
    others = [Node("StarterGui", "StarterGui"), Node("StarterPack", "StarterPack"), Node("SoundService", "SoundService"), Node("Teams", "Teams"), Node("ServerStorage", "ServerStorage")]

    items = [workspace, lighting, rs, sss, sp_, players] + others
    body = "\n".join(it.xml(1) for it in items)
    xml = ('<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">\n\t<External>null</External>\n\t<External>nil</External>\n'
           + body + "\n</roblox>\n")
    data = xml.encode("utf-8")
    os.makedirs(os.path.dirname(a.output), exist_ok=True)
    if a.output.endswith(".gz"):
        with gzip.open(a.output, "wb", compresslevel=9) as f: f.write(data)
    else:
        open(a.output, "wb").write(data)
    print(f"written {a.output}: {len(data):,} bytes xml, {_ref} instances, {cp_count} checkpoints (+ start line)")

if __name__ == "__main__":
    main()
