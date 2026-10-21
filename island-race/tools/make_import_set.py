#!/usr/bin/env python3
"""Select the Kenney models Island Race uses, bake their colours (glb_bake) and zip them for a one-shot Studio import.
Output: island-race/import/<kit>/*.glb, README.md and Island-Race-Import.zip"""
import glob, os, re, shutil, sys, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_bake

SELECT = {
 "kenney-racing-kit": ["raceCarRed","raceCarGreen","raceCarOrange","raceCarWhite","roadStart","roadStartPositions","flagCheckers","flagCheckersSmall","flagRed","flagGreen","barrierRed","barrierWhite","barrierWall","overhead","overheadLights","overheadRound","grandStand","grandStandAwning","lightPostModern","lightRed","ramp","roadRamp","roadRampLong","roadStraight","roadStraightLong","roadStraightArrow","roadCurved","roadCornerLarge","roadCornerSmall","roadStraightBridge","roadBump","billboard","pylon","tent","bannerTowerRed","bannerTowerGreen","pitsGarage","treeLarge","treeSmall","fenceStraight","fenceCurved"],
 "kenney-platformer-kit": ["block-grass","block-grass-large","block-grass-low","block-grass-long","block-grass-large-slope","block-grass-large-slope-steep","block-grass-curve","block-grass-corner","block-grass-hexagon","block-grass-overhang-large","block-moving","block-moving-blue","block-moving-large","block-snow","block-snow-large","block-snow-low","block-snow-long","block-snow-large-slope","block-snow-curve","block-snow-hexagon","coin-gold","coin-silver","coin-bronze","star","heart","jewel","spring","arrow","arrows","flag","platform","platform-ramp","platform-overhang","conveyor-belt","button-round","chest","crate","crate-strong","ladder","ladder-long","sign","tree","tree-pine","tree-pine-small","tree-pine-snow","tree-snow","flowers","flowers-tall","rocks","stones","mushrooms","hedge","fence-straight","fence-corner","fence-rope","saw","trap-spikes","pipe","barrel","poles"],
 "kenney-mini-arena": ["trophy","banner","statue","column","wall-gate","wall","stairs","floor","tree"],
}
PATTERNS = {
 "kenney-nature-kit": r"^(tree_(default|oak|pineDefault|pineRound|palm|thin|blocks|cone|fat|tall)[A-Z]?|cliff_(block|cornerLarge|top|half)[A-Z]?|rock_(small|large|tall)[A-Z]?|stone_(small|large|tall)[A-Z]?|bridge_(wood|stone|side)[A-Za-z]*|campfire_(stones|logs)|statue_(head|column|obelisk)|path_(stone|wood)[A-Za-z]*|platform_(grass|stone)|log(_stack)?|mushroom_(red|tan)|flower_(red|purple|yellow)[A-Z]?|ground_grass|ground_pathTile|hanging_moss|fence_(simple|planks)|sign|tent_(detailed)?(Closed|Open)?|canoe|stump_(round|square)(Detailed)?)$",
 "kenney-space-kit": r"^(platform_(center|low|large|straight|corner|end|side)|rock(s)?(_crystals)?[A-Z]?|rock_largeA|meteor(_half|_detailed)?|satelliteDish(_large|_detailed)?|rocket_(baseA|fuelA|finsA|topA|sidesA)|craft_(speederA|speederB|speederC|speederD|racer|miner|cargoA)|gate_(simple|complex)|terrain(_side|_ramp|_dirt|_roadStraight|_roadCorner|_roadRamp)?[A-Z]?|turret_(single|double)|structure(_closed|_diagonal|_detailed)?|monorail_track(Straight|Corner|Slope|Support)[A-Za-z]*|barrel(s)?(_rail)?|astronautA|rover|crater(Large)?|supports_(low|high)|stairs(_short|_corner)?|pipe_(straight|corner|ring|cornerRound|end)[A-Za-z]*)$",
}

def main():
    out = os.path.join(ROOT, "import")
    for kit in list(SELECT) + list(PATTERNS):
        d = os.path.join(out, kit)
        if os.path.isdir(d): shutil.rmtree(d)
    chosen = {}
    for kit in list(SELECT) + list(PATTERNS):
        files = glob.glob(os.path.join(REPO, "models", kit, "**", "*.glb"), recursive=True)
        byname = {os.path.splitext(os.path.basename(f))[0]: f for f in files}
        if kit in SELECT:
            picked = [n for n in SELECT[kit] if n in byname]
            missing = [n for n in SELECT[kit] if n not in byname]
            if missing: print(kit, "missing:", missing)
        else:
            rx = re.compile(PATTERNS[kit]); picked = [n for n in sorted(byname) if rx.match(n)]
        d = os.path.join(out, kit); os.makedirs(d, exist_ok=True)
        for n in picked:
            glb_bake.bake(byname[n], os.path.join(d, n + ".glb"))
        chosen[kit] = picked
        print(f"{kit}: {len(picked)} models baked")
    with open(os.path.join(out, "README.md"), "w", encoding="utf-8") as f:
        f.write("# موديلات المرحلة الأولى للاستيراد في Studio\n\nملفات GLB من حزم Kenney (رخصة CC0) **مع الألوان مدمجة داخل كل ملف** (الأداة `tools/glb_bake.py`)، فتظهر ملوّنة بعد الاستيراد.\n\n"
                "الاستيراد: Studio → File → **Import 3D** (أو Asset Manager → Bulk Import) → اختر ملفات مجلد كامل → Import. كرّر لكل مجلد. ثم احفظ المكان كملف `.rbxlx` وارفعه.\n\n")
        for kit, picked in chosen.items():
            f.write(f"## {kit} ({len(picked)})\n\n" + " • ".join(picked) + "\n\n")
    z = os.path.join(out, "Island-Race-Import.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(out):
            for fn in files:
                if fn.endswith(".zip"): continue
                p = os.path.join(root, fn); zf.write(p, os.path.relpath(p, out))
    print("zip bytes:", os.path.getsize(z), "total models:", sum(len(v) for v in chosen.values()))

if __name__ == "__main__":
    main()
