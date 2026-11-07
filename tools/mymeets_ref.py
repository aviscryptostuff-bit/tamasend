"""Python port of MyMeets 2.3.7 logic, written from its IL. Reference for the site's JS."""
import struct, os, glob, math

# ---------- TamagoString ----------
MOJIS = ['　あいうえおかきくけこさしすせそ','たちつてとなにぬねのはひふへほま','みむめもやゆよらりるれろわをんぁ',
 'ぃぅぇぉっゃゅょがぎぐげござじず','ぜぞだぢづでどばびぶべぼぱぴぷぺ','ぽー～…、。()「」.・!?&○',
 '×┣◎★┳♪┫↑↓→←￥　012','3456789アイウエオカキクケ','コサシスセソタチツテトナニヌネノ',
 'ハヒフヘホマミムメモヤユヨラリル','レロワヲンァィゥェォッャュョガギ','グゲゴザジズゼゾダヂヅデドバビブ',
 'ベボパピプペポヴ        ','│┌┐┘└├┬┤┴┼━┃┏┓┛┗','ABCDEFGHIJKLMNOP','QRSTUVWXYZ%-+  \n']
EN_CHARS = 'ABCDEFGHIKLMNOPQRSTUVWXYZ !%-+\n0123456789'
def to_mojis(text):
    text = text.upper()
    lang = 8
    for c in text:
        if c not in EN_CHARS: lang = 4; break
    out = bytearray(len(text) * 2); k = 0
    for c in text:
        for r, row in enumerate(MOJIS):
            i = row.find(c)
            if i != -1:
                if k + 1 >= len(out): raise IndexError("moji overflow")
                out[k] = lang; out[k+1] = ((r << 4) | (i & 15)) & 255; k += 2
    return bytes(out)
def from_mojis(b):
    s = ""
    for i in range(0, len(b) - 1, 2):
        if b[i] not in (4, 8): break
        s += MOJIS[b[i+1] >> 4][b[i+1] & 15]
    return s

# ---------- images ----------
def c16to24(v):
    return ((v & 31) * 255 // 31, ((v & 0x7e0) >> 5) * 255 // 63, ((v & 0xf800) >> 11) * 255 // 31)
def c24to16(r, g, b):
    return ((b >> 3) & 31) << 11 | ((g >> 2) & 63) << 5 | ((r >> 3) & 31)
class Img:
    def __init__(s, w, h, fill=(0, 0, 0, 0)): s.w, s.h = w, h; s.px = [fill] * (w * h)
    def get(s, x, y): return s.px[y * s.w + x]
    def set(s, x, y, c): s.px[y * s.w + x] = c
    def clone(s): n = Img(s.w, s.h); n.px = list(s.px); return n
def img_size_from_header(b):
    if struct.unpack_from("<H", b, 3)[0] not in (1, 256): return 0
    w, h, nc = b[0], b[1], b[2]; n = w * h
    if nc <= 16: n //= 2
    return 6 + n + nc * 2
def decode_image(b):
    """TamagoImage.FromTamagoBuffer -> Img (opaque RGBA) or None"""
    if struct.unpack_from(">H", b, 3)[0] not in (1, 256): return None
    w, h, nc = b[0], b[1], b[2]
    pal = [c16to24(struct.unpack_from(">H", b, 6 + 2*i)[0]) + (255,) for i in range(nc)]
    o = 6 + 2 * nc; im = Img(w, h)
    if nc <= 16:
        p = 0
        for i in range(w * h // 2):
            v = b[o + i]; lo, hi = v & 15, v >> 4
            if lo <= nc or hi <= nc:
                im.px[p] = pal[lo]; im.px[p+1] = pal[hi]
            p += 2
    else:
        for i in range(w * h): im.px[i] = pal[b[o + i]]
    return im
def make_transparent(im):
    key = im.px[0]
    im.px = [(0, 0, 0, 0) if c == key else c for c in im.px]
def is_empty(im):
    k = im.px[0]; return all(c == k for c in im.px)
def encode_image(im):
    """TamagoImage.FromBitmap -> bytes (ImageBuffer)"""
    pal = []
    for x in range(im.w):
        for y in range(im.h):
            c = im.get(x, y)
            if c not in pal: pal.append(c)
    n = im.w * im.h
    if len(pal) <= 16: n //= 2
    size = 6 + n + len(pal) * 2; size += size % 4
    out = bytearray(size)
    out[0], out[1], out[2] = im.w, im.h, len(pal) & 255
    struct.pack_into("<H", out, 3, 1 if len(pal) <= 16 else 256); out[5] = 0xff
    for i, c in enumerate(pal): struct.pack_into(">H", out, 6 + 2*i, c24to16(*c[:3]))
    o = 6 + 2 * len(pal)
    if len(pal) <= 16:
        for i in range(0, im.w * im.h, 2):
            a = pal.index(im.px[i]); b = pal.index(im.px[i+1])
            out[o] = (a & 15) | ((b & 15) << 4); o += 1
    else:
        for i in range(im.w * im.h): out[o] = pal.index(im.px[i]); o += 1
    return bytes(out)

# ---------- items ----------
DEST_TYPE = {0x81071f00: 1, 0x81023400: 4, 0x81023500: 4, 0x81010101: 2, 0x81010102: 2, 0x81010201: 2,
             0x81010d02: 2, 0x81042a01: 3, 0x94025b01: 6, 0x94024702: 5}
def parse_item(d):
    if len(d) < 120 or d[:6] != b"TAMAGO": return None
    dest = struct.unpack_from(">I", d, 0x4e)[0]
    it = dict(dest=dest, type=DEST_TYPE.get(dest, 0), id=struct.unpack_from(">H", d, 0x5a)[0],
              lang=d[0x5e], name=from_mojis(d[0x5e:0x76]), price=struct.unpack_from(">H", d, 0x76)[0],
              asset=d[0x34:0x48].split(b"\0")[0].decode("ascii", "replace"))
    return it

# ---------- characters ----------
PARTS = "BMAK"
SMALL = {"B": 9, "A": 7, "M": 15, "K": 6}
IMGCOUNT = {"B": 14, "A": 11, "M": 19, "K": 7}
OFFSET_TABLE = bytes.fromhex("00010000e4010000e8010000f4010000")
OFFSET_VALUES = [[0x10, 0x100, 0x400], [0x48, 0x1e4, 0x3850], [0x94, 0x1e8, 0x5300], [0xc0, 0x1f4, 0x7200]]
def load_characters(folder):
    files = {os.path.basename(f).lower(): f for f in glob.glob(folder + "/*")}
    ids = sorted({int(os.path.basename(f)[3:7]) for f in files.values()})
    chars = {}
    def rd(name):
        f = files.get(name.lower()); return open(f, "rb").read() if f else None
    for cid in ids:
        ch = {}
        for pi, p in enumerate(PARTS):
            part = {"data": {}, "images": [], "front": False}
            off = rd(f"{pi+1:02d}c{cid:04d}_Offset_{p}.txt")
            if off is None: break
            part["data"]["Offset"] = off
            if p == "B":
                for lang, suf in ((4, ""), (8, "_en")):
                    t = rd(f"{pi+5:02d}c{cid:04d}_Tbl_B{suf}.txt")
                    if t is not None: part["data"]["Tbl" + ("_en" if lang == 8 else "")] = t
            else:
                t = rd(f"{pi+5:02d}c{cid:04d}_Tbl_{p}.txt")
                if t is None: break
                if p == "K" and t[6]: part["front"] = True
                part["data"]["Tbl"] = t
            c = rd(f"{pi+9:02d}c{cid:04d}_Char_{p}.txt")
            if c is None: break
            o = 0
            while o < len(c):
                size = img_size_from_header(c[o:o+6])
                if not size or o + size > len(c): break
                im = decode_image(c[o:o+size])
                if im is None: break
                make_transparent(im)
                if is_empty(im) and p not in "KA": break
                part["images"].append(im)
                o += size + size % 4
            part["data"]["Char"] = c
            ch[p] = part
        chars[cid] = ch
    return ids, chars
def part_image(chars, cid, p, idx):
    part = chars.get(cid, {}).get(p)
    if not part or idx >= len(part["images"]) or len(part["images"]) != IMGCOUNT[p]: return None
    return part["images"][idx].clone()

PAL = None
def set_palettes(p): global PAL; PAL = [[tuple(c) for c in row] for row in p]
def colorize(im, pi):
    out = im.clone(); tpl = PAL[-1]
    for i, c in enumerate(out.px):
        for k, t in enumerate(tpl):
            d = math.sqrt(0.3*(t[0]-c[0])**2 + 0.59*(t[1]-c[1])**2 + 0.11*(t[2]-c[2])**2)
            if d <= 10.0: out.px[i] = PAL[pi][k] + (255,); break
    return out
def part_offsets(b):
    offs = {"A": (0, 0), "M": (0, 0), "K": (0, 0)}
    c0, c1, c2, c3 = b.get(0, 0), b.get(1, 0), b.get(2, 0), b.get(3, 0)
    for x in range(4): b.set(x, 0, c0)
    for y in range(b.h):
        for x in range(b.w):
            c = b.get(x, y)
            if c == (255, 0, 0, 255): offs["A"] = (x, y); b.set(x, y, c1)
            elif c == (255, 255, 0, 255): offs["M"] = (x, y); b.set(x, y, c2)
            elif c == (0, 0, 255, 255): offs["K"] = (x, y); b.set(x, y, c3); return offs
    return offs
def compose_image(chars, sel, small):
    """sel: {part: (id, palette)} in insertion order B,A,M,K etc. -> Img or None"""
    layers = {"B": None, "A": None, "M": None, "K": None}; pals = {k: 0 for k in layers}
    offs = {"A": (0, 0), "M": (0, 0), "K": (0, 0)}; front = False
    for p in sel:
        im = part_image(chars, sel[p][0], p, SMALL[p] if small else 0)
        if im is None and p != "K": return None
        if p == "B" and im is not None: offs = part_offsets(im)
        layers[p] = im; pals[p] = sel[p][1]
        if p == "K": front = chars.get(sel[p][0], {}).get("K", {}).get("front", False)
    if any(v is None for v in layers.values()): return None
    order = ["B", "A", "M", "K"] if front else ["K", "B", "A", "M"]
    w, h, x0, y0 = (48, 40, 8, 4) if small else (64, 64, 8, 6)
    out = Img(w, h, (0, 255, 0, 255))
    for p in order:
        im = colorize(layers[p], pals[p]); x, y = x0, y0
        if p != "B": x += offs[p][0] - im.w // 2; y += offs[p][1] - im.h // 2
        for yy in range(im.h):
            for xx in range(im.w):
                c = im.get(xx, yy)
                if c[3] and 0 <= x+xx < w and 0 <= y+yy < h: out.set(x+xx, y+yy, c)
    return out
def compose_character_data(chars, sex, b, m, a, k, lang):
    out = bytearray(0x8000); out[:16] = OFFSET_TABLE
    for i, (p, cid) in enumerate((("B", b), ("M", m), ("A", a), ("K", k))):
        part = chars[cid][p]; d = part["data"]
        tbl = d.get("Tbl_en" if (p == "B" and lang == 8) else "Tbl")
        for j, blob in enumerate((d["Offset"], tbl, d["Char"])):
            pos = OFFSET_VALUES[i][j]; out[pos:pos+len(blob)] = blob
            if i == 0 and j == 1: out[pos + 6] = sex & 255
    return bytes(out)

# ---------- packets ----------
TAMAGO = b"TAMAGO"; SECURITY = bytes.fromhex("7c68489775a64e99"); FORMAT = bytes.fromhex("0000000010000104")
OP = dict(visit=0x14, back=0x15, marriage=0x16, item=0x17)
CMD = dict(start=0, visit=0x34, back=0x36, marriage=0x38, item=0x3a)
def compile_packet(operand, command, size, points=0, item=None, mar=None):
    """BLETmgcPacket.Compile. mar = dict(visit, chardata, colors, dnapattern, sex, dnavalue, bkind, pkind)"""
    w = bytearray(TAMAGO)
    if mar: w += bytes(60) + mar["colors"] + bytes(3)
    else: w += bytes(66)
    w += struct.pack("<iBBI", size, operand, 0, 0) + SECURITY + struct.pack("<IB", 0, command)
    if mar:
        v = mar["visit"]; name = bytearray(16); mj = v["username"][:16]; name[:len(mj)] = mj
        w += bytes([v["sex"]]) + name + struct.pack("<HHH", 0, v["rid1"], v["id"]) + bytes(3) + b"\0"
        w += struct.pack("<HB", v["generation"], v["growth"]) + bytes(6) + bytes([v["twins"]])
        w += struct.pack("<HHBBHHH", v["unk1"], v["unk2"], mar["bkind"], mar["pkind"], v["birthday"], 0, v["rid2"]) + bytes(8)
        w += v["dnapattern"] + bytes([mar["dnavalue"], mar["sex"]]) + v["palette"] + mar["dnapattern"] + bytes([mar["dnavalue"]]) + bytes(13)
    else: w += bytes(92)
    w += (b"\x03" + struct.pack("<I", points)) if points > 0 else bytes(5)
    w += (bytes(12) + struct.pack("<II", 0x100, 0x810c)) if mar else bytes(20)
    w += (struct.pack("<I", 256) + bytes(20)) if item is not None else bytes(24)
    w += (struct.pack("<I", 0x8198) + bytes(8)) if mar else bytes(12)
    w += FORMAT
    if item is not None: w += struct.pack("<III", 2, 1, len(item)) + item + struct.pack("<I", 0)
    elif mar: w += struct.pack("<III", 0, 1, 0x8000) + mar["chardata"][:0x8000] + v["info"] + v["parents"]
    raw = bytearray(size); raw[:len(w)] = w[:size]
    cs = sum(raw) & 0xffff
    raw[len(w):len(w)+2] = struct.pack("<H", cs)
    return bytes(raw)
def visit_record(sex, cid, dna, dnapattern, palette):
    v = dict(sex=sex, username=to_mojis("TAMA"), rid1=0, rid2=0, id=cid, generation=2, growth=4, twins=0,
             birthday=0x101, unk1=0, unk2=0, dna=dna, dnapattern=dnapattern, palette=palette)
    info = bytearray(0x8c); nm = bytearray(18); mj = to_mojis("TAMA")[:18]; nm[:len(mj)] = mj
    struct.pack_into("<IIIHH", info, 0, 1, 1, 0x80, sex, 3)
    struct.pack_into("<HH", info, 12 + 4 + 64, v["birthday"], v["generation"])
    o = 12 + 4 + 64 + 4; info[o:o+18] = nm; o += 18 + 2; info[o:o+18] = nm; o += 18
    struct.pack_into("<H", info, o, v["twins"])
    v["info"] = bytes(info)
    return v
def parent_images(pa, pb):
    out = bytearray(0x180c); struct.pack_into("<III", out, 0, 8, 1, 0x1800)
    out[12:12+len(pa)] = pa; out[12+0xc00:12+0xc00+len(pb)] = pb
    return bytes(out)
def visitor_id(reply):
    return reply[114:116] + reply[120:122] + reply[138:140] + reply[142:144]
