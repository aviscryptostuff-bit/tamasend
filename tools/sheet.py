"""Contact sheet: py sheet.py out.png a.png b.png ... (labels = file names).

Reads the emulator's PNGs (RGB, 8-bit) with only the standard library.
"""
import struct
import sys
import zlib


def read_png(path):
    data = open(path, "rb").read()
    pos, idat, w, h = 8, b"", 0, 0
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            bpp = {2: 3, 6: 4}[ctype]
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = w * bpp
    rows, prev = [], bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line[i] for i in range(stride) if i % bpp < 3))
        prev = line
    return w, h, rows


def write_png(path, w, h, rows):
    raw = b"".join(b"\0" + r for r in rows)

    def chunk(k, b):
        return struct.pack(">I", len(b)) + k + b + struct.pack(">I", zlib.crc32(k + b) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)


def main():
    out, files = sys.argv[1], sys.argv[2:]
    imgs = [read_png(f) for f in files]
    tw, th = max(i[0] for i in imgs), max(i[1] for i in imgs)
    cols = min(len(imgs), 5)
    nrows = (len(imgs) + cols - 1) // cols
    gap = 6
    W, H = cols * (tw + gap) + gap, nrows * (th + gap) + gap
    canvas = [bytearray(b"\x40\x40\x40" * W) for _ in range(H)]
    for k, (w, h, rows) in enumerate(imgs):
        ox, oy = gap + (k % cols) * (tw + gap), gap + (k // cols) * (th + gap)
        for y in range(h):
            canvas[oy + y][ox * 3:(ox + w) * 3] = rows[y]
    write_png(out, W, H, [bytes(r) for r in canvas])
    print("wrote", out, "order:", " | ".join(f.rsplit("/", 1)[-1] for f in files))


if __name__ == "__main__":
    main()
