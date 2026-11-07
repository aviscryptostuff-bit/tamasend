"""Swap the pixel nibbles of every 4-bit frame in an item file and fix its checksum."""
import sys, struct
for path in sys.argv[1:]:
    d = bytearray(open(path, "rb").read()); o = 0x200; n = struct.unpack_from(">H", d, o)[0]; o += 2
    for _ in range(n):
        size = struct.unpack_from(">H", d, o)[0]; b = o + 2; w, h, nc = d[b], d[b+1], d[b+2]
        if nc <= 16:
            p = b + 6 + 2 * nc
            for i in range(p, p + w * h // 2): d[i] = ((d[i] & 15) << 4) | (d[i] >> 4)
        o += 2 + size
    struct.pack_into(">H", d, len(d) - 2, sum(d[:-2]) & 0xffff)
    open(path, "wb").write(d); print("fixed", path)
