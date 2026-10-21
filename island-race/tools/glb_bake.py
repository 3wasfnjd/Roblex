#!/usr/bin/env python3
"""Make Kenney GLB files import into Roblox with their colours.

Roblox's 3D importer keeps one texture per mesh and ignores per-material base colours, so Kenney kits
that colour their parts with several untextured materials (Racing, Nature, Space...) come in grey.
This tool rewrites each GLB so that:
  * untextured materials are baked into one small palette PNG and the UVs point at the right cell;
  * externally referenced textures (Textures/colormap.png) are embedded in the file;
  * the result has a single material with an embedded texture, which the importer handles correctly.

Usage: python3 glb_bake.py in.glb out.glb        (or a directory in/out to convert every .glb)
"""
import json, math, os, struct, sys, zlib

def png_rgba(width, height, pixels):
    """pixels: list of (r,g,b,a) rows*cols -> PNG bytes."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixels[y * width + x])
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))

def pad4(b, fill=b"\x00"):
    return b + fill * ((4 - len(b) % 4) % 4)

def read_glb(path):
    b = open(path, "rb").read()
    magic, version, length = struct.unpack_from("<III", b, 0)
    assert magic == 0x46546C67, "not a GLB"
    off = 12; gltf = None; bin_ = b""
    while off < length:
        clen, ctype = struct.unpack_from("<II", b, off); off += 8
        data = b[off:off + clen]; off += clen
        if ctype == 0x4E4F534A: gltf = json.loads(data)
        elif ctype == 0x004E4942: bin_ = data
    return gltf, bytearray(bin_)

def write_glb(path, gltf, bin_):
    jb = pad4(json.dumps(gltf, separators=(",", ":")).encode("utf-8"), b" ")
    bb = pad4(bytes(bin_))
    total = 12 + 8 + len(jb) + 8 + len(bb)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(jb), 0x4E4F534A)); f.write(jb)
        f.write(struct.pack("<II", len(bb), 0x004E4942)); f.write(bb)

def add_buffer_view(gltf, bin_, data):
    while len(bin_) % 4: bin_.append(0)
    gltf.setdefault("bufferViews", []).append({"buffer": 0, "byteOffset": len(bin_), "byteLength": len(data)})
    bin_.extend(data)
    return len(gltf["bufferViews"]) - 1

def accessor_count(gltf, idx):
    return gltf["accessors"][idx]["count"]

def srgb_byte(c):
    # glTF base colours are linear; the texture is sRGB
    c = max(0.0, min(1.0, c))
    s = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
    return int(round(s * 255))

def read_accessor_vec2(gltf, bin_, idx):
    acc = gltf["accessors"][idx]; bv = gltf["bufferViews"][acc["bufferView"]]
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0); stride = bv.get("byteStride", 8)
    assert acc["componentType"] == 5126 and acc["type"] == "VEC2"
    return [struct.unpack_from("<2f", bin_, base + i * stride) for i in range(acc["count"])]

def image_bytes(gltf, bin_, img, src):
    if "bufferView" in img:
        bv = gltf["bufferViews"][img["bufferView"]]; o = bv.get("byteOffset", 0)
        return bytes(bin_[o:o + bv["byteLength"]])
    uri = img["uri"]
    p = os.path.join(os.path.dirname(src), uri.replace("/", os.sep))
    if not os.path.exists(p): p = os.path.join(os.path.dirname(src), os.path.basename(uri))
    return open(p, "rb").read()

def bake_mixed(src, dst, gltf, bin_):
    """Some materials use a texture, others a flat colour: compose one atlas (texture on top, colour
    cells below) and remap every primitive's UVs onto it. Needs Pillow."""
    from PIL import Image
    import io
    materials = gltf["materials"]
    tex_index = {}
    for mi, m in enumerate(materials):
        t = m.get("pbrMetallicRoughness", {}).get("baseColorTexture")
        if t: tex_index[mi] = gltf["textures"][t["index"]]["source"]
    # one source texture only (Kenney kits never use more); tiled UVs fall back to the average colour
    src_img = None; src_id = None
    for mi, ii in tex_index.items():
        src_id = ii
    img = Image.open(io.BytesIO(image_bytes(gltf, bin_, gltf["images"][src_id], src))).convert("RGBA")
    W, H = img.size
    prims = [(mesh_i, pi, p) for mesh_i, mesh in enumerate(gltf["meshes"]) for pi, p in enumerate(mesh["primitives"])]
    # tiled textures (UVs outside 0..1, e.g. the checker flags) are repeated into the atlas up to 16x16
    uvs_all = [uv for _, _, p in prims if p.get("material", 0) in tex_index
               for uv in read_accessor_vec2(gltf, bin_, p["attributes"]["TEXCOORD_0"])] or [(0.0, 0.0), (1.0, 1.0)]
    umin, umax = min(u for u, _ in uvs_all), max(u for u, _ in uvs_all)
    vmin, vmax = min(v for _, v in uvs_all), max(v for _, v in uvs_all)
    u0, v0 = math.floor(umin), math.floor(vmin)
    ru, rv = int(math.ceil(umax - u0)), int(math.ceil(vmax - v0))
    tiled = False
    if (ru, rv) != (1, 1):
        if ru <= 16 and rv <= 16:
            tiledimg = Image.new("RGBA", (W * ru, H * rv))
            for i in range(ru):
                for k in range(rv): tiledimg.paste(img, (i * W, k * H))
            img = tiledimg; W, H = img.size
        else:
            tiled = True
    colors = []
    for mi, m in enumerate(materials):
        if mi in tex_index and not tiled:
            colors.append(None)
        elif mi in tex_index:
            px = [c for c in list(img.get_flattened_data()) if c[3] > 0] or [(200, 200, 200, 255)]
            colors.append(tuple(sum(c[k] for c in px) // len(px) for k in range(3)) + (255,))
        else:
            f = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])
            colors.append(tuple(srgb_byte(x) for x in f[:3]) + (255,))
    cell = 8; n = len(colors); cols = max(1, min(n, W // cell)); rows = int(math.ceil(n / cols))
    strip = rows * cell
    atlas = Image.new("RGBA", (W, H + strip), (0, 0, 0, 255))
    if not tiled: atlas.paste(img, (0, 0))
    for i, c in enumerate(colors):
        if c is None: continue
        cx, cy = (i % cols) * cell, H + (i // cols) * cell
        atlas.paste(Image.new("RGBA", (cell, cell), c), (cx, cy))
    total = H + strip
    buf = io.BytesIO(); atlas.save(buf, "PNG"); png = buf.getvalue()
    img_view = add_buffer_view(gltf, bin_, png)
    gltf["images"] = [{"bufferView": img_view, "mimeType": "image/png"}]
    gltf["samplers"] = [{"magFilter": 9729, "minFilter": 9729, "wrapS": 33071, "wrapT": 33071}]
    gltf["textures"] = [{"source": 0, "sampler": 0}]
    gltf["materials"] = [{"name": "atlas", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0.0, "roughnessFactor": 1.0}}]
    for _, _, p in prims:
        mi = p.get("material", 0)
        count = accessor_count(gltf, p["attributes"]["POSITION"])
        if colors[mi] is None:
            uvs = [((u - u0) / ru, (v - v0) / rv * H / total) for u, v in read_accessor_vec2(gltf, bin_, p["attributes"]["TEXCOORD_0"])]
            data = struct.pack("<%df" % (count * 2), *[x for uv in uvs for x in uv])
        else:
            u = ((mi % cols) + 0.5) * cell / W; v = (H + ((mi // cols) + 0.5) * cell) / total
            data = struct.pack("<%df" % (count * 2), *([u, v] * count))
        view = add_buffer_view(gltf, bin_, data)
        gltf["accessors"].append({"bufferView": view, "componentType": 5126, "count": count, "type": "VEC2"})
        p["attributes"]["TEXCOORD_0"] = len(gltf["accessors"]) - 1
        p["attributes"].pop("COLOR_0", None); p["material"] = 0
    gltf["buffers"] = [{"byteLength": len(bin_)}]
    write_glb(dst, gltf, bin_)
    return "atlas (%s)" % ("tiled texture averaged" if tiled else "texture %dx%d repeat + %d colours" % (ru, rv, sum(1 for c in colors if c)))

def bake(src, dst):
    gltf, bin_ = read_glb(src)
    materials = gltf.get("materials", [])
    images = gltf.get("images", [])
    n_tex = sum(1 for m in materials if "baseColorTexture" in m.get("pbrMetallicRoughness", {}))
    textured = n_tex > 0
    if textured and n_tex < len(materials):
        return bake_mixed(src, dst, gltf, bin_)
    if textured and images:
        # embed external images so the importer never misses them
        for img in images:
            uri = img.get("uri")
            if uri and not uri.startswith("data:"):
                p = os.path.join(os.path.dirname(src), uri.replace("/", os.sep))
                if not os.path.exists(p):
                    p = os.path.join(os.path.dirname(src), os.path.basename(uri))
                data = open(p, "rb").read()
                img.pop("uri", None); img["bufferView"] = add_buffer_view(gltf, bin_, data); img["mimeType"] = "image/png"
        gltf["buffers"] = [{"byteLength": len(bin_)}]
        write_glb(dst, gltf, bin_)
        return "embedded"
    # ---- bake per-material base colours into a palette
    colors = []
    for m in materials:
        f = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])
        colors.append(tuple(srgb_byte(x) for x in f[:3]) + (255,))
    if not colors: colors = [(255, 255, 255, 255)]
    n = len(colors); cols = int(math.ceil(math.sqrt(n))); rows = int(math.ceil(n / cols))
    cell = 8; width, height = cols * cell, rows * cell
    pixels = [(0, 0, 0, 255)] * (width * height)
    for i, c in enumerate(colors):
        cx, cy = (i % cols) * cell, (i // cols) * cell
        for y in range(cell):
            for x in range(cell): pixels[(cy + y) * width + (cx + x)] = c
    png = png_rgba(width, height, pixels)
    img_view = add_buffer_view(gltf, bin_, png)
    gltf["images"] = [{"bufferView": img_view, "mimeType": "image/png"}]
    gltf["samplers"] = [{"magFilter": 9728, "minFilter": 9728, "wrapS": 33071, "wrapT": 33071}]
    gltf["textures"] = [{"source": 0, "sampler": 0}]
    gltf["materials"] = [{"name": "palette", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0.0, "roughnessFactor": 1.0}}]
    # every primitive: new UVs that sit in the middle of its colour cell
    for mesh in gltf.get("meshes", []):
        for prim in mesh["primitives"]:
            mi = prim.get("material", 0)
            u = ((mi % cols) + 0.5) / cols; v = ((mi // cols) + 0.5) / rows
            count = accessor_count(gltf, prim["attributes"]["POSITION"])
            data = struct.pack("<%df" % (count * 2), *([u, v] * count))
            view = add_buffer_view(gltf, bin_, data)
            gltf["accessors"].append({"bufferView": view, "componentType": 5126, "count": count, "type": "VEC2"})
            prim["attributes"]["TEXCOORD_0"] = len(gltf["accessors"]) - 1
            prim["attributes"].pop("COLOR_0", None)
            prim["material"] = 0
    gltf["buffers"] = [{"byteLength": len(bin_)}]
    write_glb(dst, gltf, bin_)
    return f"baked {n} colours"

def main():
    src, dst = sys.argv[1], sys.argv[2]
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        done = 0
        for root, _, files in os.walk(src):
            for fn in files:
                if fn.lower().endswith(".glb"):
                    bake(os.path.join(root, fn), os.path.join(dst, fn)); done += 1
        print(f"{done} files -> {dst}")
    else:
        print(bake(src, dst))

if __name__ == "__main__":
    main()
