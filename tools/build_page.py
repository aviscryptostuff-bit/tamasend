"""Builds index.html from tools/page.html by filling in the embedded data.

Usage (from the repo root):  python tools/build_page.py
"""
import base64, json, os
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rd = lambda p: open(os.path.join(root, p), "rb").read()
page = rd("tools/page.html").decode("utf-8")
presets = {k: base64.b64encode(rd(f"items/{f}")).decode() for k, f in
           [("pistol", "pistol_as03305.txt"), ("skateboard", "skateboard_as03302.txt"), ("pizza", "pizza_oy03101.txt"), ("burger", "burger_gh03201.txt")]}
fill = {
    "/*@BG50001@*/": base64.b64encode(rd("items/wallpaper_bg50001.txt")).decode(),
    "/*@PRESETS@*/": json.dumps(presets),
    "/*@PALETTES@*/": json.dumps(json.loads(rd("tools/palettes.json")), separators=(",", ":")),
    "/*@DNA@*/": json.dumps(json.loads(rd("tools/dna.json")), separators=(",", ":")),
}
for k, v in fill.items():
    assert page.count(k) == 1, k
    page = page.replace(k, v)
open(os.path.join(root, "index.html"), "w", encoding="utf-8").write(page)
print("index.html", len(page), "bytes")
