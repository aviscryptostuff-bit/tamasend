"""Annotated ARM disassembly of a TAMAGO location/game file (loaded at 0x207F0000).

Usage: pip install capstone; python tools/disasm_item.py community/magic_hut.txt > magic_hut.asm
"""
import sys, struct, capstone
BASE = 0x207F0000
d = open(sys.argv[1], "rb").read()
size = struct.unpack_from(">I", d, 0xae)[0]; start = 0x204; end = start + size
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
pool = set()
lines = []
for o in range(start, end, 4):
    w = struct.unpack_from("<I", d, o)[0]
    ins = list(md.disasm(d[o:o+4], BASE + o))
    note = ""
    if (w & 0x0f7f0000) == 0x051f0000:
        imm = w & 0xfff; up = (w >> 23) & 1; a = o + 8 + (imm if up else -imm)
        v = struct.unpack_from("<I", d, a)[0]; pool.add(a); note = f"   ; = {v:#010x}"
        if BASE <= v < BASE + len(d): note += f" (file+{v-BASE:#x})"
    txt = f"{ins[0].mnemonic} {ins[0].op_str}" if ins else ".word"
    if o in pool: txt = f".word {w:#010x}"
    lines.append(f"{o:06x}: {txt}{note}")
print("\n".join(lines))
