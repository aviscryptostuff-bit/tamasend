"""Builds the site's data files from the MyMeets assets (read only)."""
import sys, os, json, glob, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import mymeets_ref as mm
src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
index = {}
for lang in ("en", "jp"):
    blob = bytearray(); rows = []
    for f in sorted(glob.glob(f"{src}/items/{lang}/*.txt")):
        d = open(f, "rb").read(); it = mm.parse_item(d)
        if not it: continue
        rows.append([len(blob), len(d), it["type"], it["id"], it["name"], it["price"], it["asset"]])
        blob += d
    open(f"{out}/items_{lang}.bin", "wb").write(blob); index[lang] = rows
# Community files (e.g. Bolter's Magic Hut) from <repo>/community, shown as their own catalogue.
extra = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "community")
blob = bytearray(); rows = []
for f in sorted(glob.glob(f"{extra}/*.txt")):
    d = open(f, "rb").read(); it = mm.parse_item(d)
    if not it: continue
    rows.append([len(blob), len(d), it["type"], it["id"], it["name"], it["price"], it["asset"]]); blob += d
if rows:
    open(f"{out}/items_mods.bin", "wb").write(blob); index["mods"] = rows
json.dump(index, open(f"{out}/items.json", "w"), ensure_ascii=False, separators=(",", ":"))
files = {os.path.basename(f).lower(): f for f in glob.glob(f"{src}/characters/*")}
ids = sorted({int(os.path.basename(f)[3:7]) for f in files.values()})
blob = bytearray(); chars = {}
def put(name):
    global blob
    f = files.get(name.lower())
    if not f: return None
    d = open(f, "rb").read(); r = [len(blob), len(d)]; blob += d; blob += bytes(-len(blob) % 4); return r
for cid in ids:
    ch = {}
    for pi, p in enumerate("BMAK"):
        e = {"o": put(f"{pi+1:02d}c{cid:04d}_Offset_{p}.txt"), "c": put(f"{pi+9:02d}c{cid:04d}_Char_{p}.txt")}
        e["t"] = put(f"{pi+5:02d}c{cid:04d}_Tbl_{p}.txt")
        if p == "B": e["te"] = put(f"{pi+5:02d}c{cid:04d}_Tbl_B_en.txt")
        ch[p] = e
    chars[cid] = ch
open(f"{out}/chars.bin", "wb").write(blob)
json.dump({"ids": ids, "chars": chars}, open(f"{out}/chars.json", "w"), separators=(",", ":"))
print("items:", {k: len(v) for k, v in index.items()}, "chars:", len(ids), "chars.bin", len(blob))
