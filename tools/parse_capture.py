"""
Decode a Wireshark .pcapng captured with Microsoft's btvs.exe (-Mode Wireshark)
into the TamaOS protocol: every ATT write/notify, then reassembled messages.

Usage:  python tools/parse_capture.py capture.pcapng
"""
import struct
import sys

NAMES = {0x52: "WRITE_CMD", 0x12: "WRITE_REQ", 0x13: "WRITE_RSP", 0x1B: "NOTIFY",
         0x0A: "READ_REQ", 0x0B: "READ_RSP", 0x02: "MTU_REQ", 0x03: "MTU_RSP"}


def packets(path):
    d = open(path, "rb").read()
    i, links, out = 0, [], []
    while i + 12 <= len(d):
        t, l = struct.unpack_from("<II", d, i)
        b = d[i + 8:i + l - 4]
        if t == 1:  # interface description
            links.append(struct.unpack_from("<H", b, 0)[0])
        elif t == 6:  # enhanced packet
            iface, th, tl, cap, _ = struct.unpack_from("<IIIII", b, 0)
            out.append((((th << 32) | tl) / 1e6, links[iface], b[20:20 + cap]))
        i += l
    return out


def att_events(path):
    pk = packets(path)
    t0 = pk[0][0]
    for ts, lt, p in pk:
        if lt == 201:  # LINKTYPE_BLUETOOTH_HCI_H4_WITH_PHDR
            direction = "TX" if struct.unpack(">I", p[:4])[0] == 0 else "RX"
            h = p[4:]
        else:
            direction, h = "??", p
        if not h or h[0] != 2:  # ACL data only
            continue
        l2len, cid = struct.unpack_from("<HH", h, 5)
        if cid != 4:  # ATT channel
            continue
        att = h[9:9 + l2len]
        if att[0] in (0x52, 0x12, 0x1B):
            yield ts - t0, direction, NAMES[att[0]], att[3:]


def main(path):
    msgs, cur = [], None
    for t, d, kind, val in att_events(path):
        if kind == "WRITE_REQ":
            print(f"{t:8.3f} {d} {kind} {val.hex()}  (CCCD / enable notify)")
            continue
        if val[:1] == b"\xf0" and len(val) <= 8:
            print(f"{t:8.3f} {d} CTRL {val.hex()}")
            if val == b"\xf0\x8d" or val[:2] == b"\xf0\x0d":
                cur = [t, d, bytearray()]
            elif val in (b"\xf0\xcd", b"\xf0\x4d") and cur:
                msgs.append(cur)
                cur = None
            continue
        if cur is not None:
            cur[2] += val
    for t, d, b in msgs:
        ok = len(b) > 2 and (sum(b[:-2]) & 0xFFFF) == int.from_bytes(b[-2:], "little")
        print(f"\nMSG t={t:.3f} {d} len={len(b)} checksum_ok={ok}")
        print(bytes(b[:0x120]).hex())


if __name__ == "__main__":
    main(sys.argv[1])
