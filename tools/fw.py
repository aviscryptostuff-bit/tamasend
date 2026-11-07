"""Tiny helper for reading the Tama firmware (ON Magic EN v058 dump).

Address 0x20XXXXXX == flash offset 0xXXXXXX (the image runs in place, as
nijiiro-egg maps it). Note: the old handoff's "+0x0c" mapping is wrong.
Usage from other scripts:  from fw import *
"""
import struct
import sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM

ROM = __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0] + "/roms/magic-green.bin"
D = open(ROM, "rb").read()
BASE = 0x20000000
OFF = 0


def f2r(off):
    return off - OFF + BASE


def r2f(addr):
    return (addr & ~1) - BASE + OFF


def u32(addr):
    return struct.unpack_from("<I", D, r2f(addr))[0]


def cstr(addr, n=200):
    o = r2f(addr)
    return D[o:D.index(b"\0", o, o + n)].decode("latin1")


def refs(value, lo=0, hi=0x200000):
    """Code-area offsets (as RAM addrs) holding the u32 `value` (literal pools)."""
    b = struct.pack("<I", value)
    out, i = [], lo
    while True:
        i = D.find(b, i, hi)
        if i < 0:
            return out
        if i % 4 == 0:
            out.append(f2r(i))
        i += 1


_thumb = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
_arm = Cs(CS_ARCH_ARM, CS_MODE_ARM)
_thumb.detail = False


def dis(addr, n=40, thumb=True):
    md = _thumb if thumb else _arm
    o = r2f(addr)
    lines = []
    for ins in md.disasm(D[o:o + n * 4], addr & ~1):
        note = ""
        if ins.mnemonic.startswith("ldr") and "[pc" in ins.op_str:
            try:
                imm = int(ins.op_str.split("#")[-1].rstrip("]"), 0)
                lit = ((ins.address + 4) & ~3) + imm
                v = u32(lit)
                note = f"   ; ={v:#010x}"
                if BASE <= v < BASE + 0x200000:
                    try:
                        s = cstr(v, 120)
                        if len(s) > 3 and s.isprintable():
                            note += f' "{s[:70]}"'
                    except ValueError:
                        pass
            except Exception:
                pass
        lines.append(f"{ins.address:08x}: {ins.mnemonic:8s}{ins.op_str}{note}")
        if len(lines) >= n:
            break
    return "\n".join(lines)


def sweep(addr, end):
    """Thumb linear sweep that steps over data it can't decode."""
    out = []
    a = addr & ~1
    while a < end:
        chunk = dis(a, 200).split("\n") if True else []
        got = [l for l in chunk if l]
        if not got:
            out.append(f"{a:08x}: .hword {struct.unpack_from('<H', D, r2f(a))[0]:#06x}")
            a += 2
            continue
        for l in got:
            la = int(l.split(":")[0], 16)
            if la >= end:
                return "\n".join(out)
            out.append(l)
        last = int(got[-1].split(":")[0], 16)
        # next address after the last decoded instruction
        h = struct.unpack_from("<H", D, r2f(last))[0]
        a = last + (4 if (h >> 11) in (0x1D, 0x1E, 0x1F) else 2)
    return "\n".join(out)


def bl_callers(target, lo=0x20000000, hi=0x201B0000):
    """Thumb BL instructions (and literal pointers) that reach `target`."""
    target &= ~1
    out = []
    for a in range(lo, hi, 2):
        o = r2f(a)
        h1, h2 = struct.unpack_from("<HH", D, o)
        if h1 >> 11 == 0b11110 and h2 >> 11 in (0b11111, 0b11101):
            off = ((h1 & 0x7FF) << 12) | ((h2 & 0x7FF) << 1)
            if off & 0x400000:
                off -= 0x800000
            dest = a + 4 + off
            if h2 >> 11 == 0b11101:
                dest &= ~3
            if dest == target:
                out.append(a)
    return out


def ldr_refs(value, lo=0x2000000C, hi=0x20200000):
    """Thumb `ldr rX,[pc,#imm]` instructions whose literal equals value."""
    pools = set(refs(value))
    out = []
    for p in pools:
        # a thumb ldr-literal reaches up to 1020 bytes forward
        for a in range(max(lo, p - 1024), p, 2):
            h = struct.unpack_from("<H", D, r2f(a))[0]
            if h >> 11 == 0b01001:
                imm = (h & 0xFF) * 4
                if ((a + 4) & ~3) + imm == p:
                    out.append(a)
    return sorted(out)


if __name__ == "__main__":
    a = int(sys.argv[1], 16)
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    print(dis(a, n, thumb=not (len(sys.argv) > 3 and sys.argv[3] == "arm")))
