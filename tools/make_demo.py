"""Build tamaos_demo.txt: our own downloadable *location* program for a
Tamagotchi On (Magic EN v058), written from scratch in ARM assembly.

What it does (runs when you visit the location):
  * full-screen animated plasma, drawn pixel by pixel into the LCD framebuffer
  * a 2-frame walking pixel character bouncing around on top
  * a scrolling text banner
  * any button (A/B/C) exits back to the game; also exits after ~60 s

How it talks to the firmware (all verified in the nijiiro-egg emulator):
  * framebuffer address = LCD DMA source register 0xD050033C (RGB565 LE)
  * present frame  : API stub 0x20000713  (-> 0xF8006481)
  * wait ms        : API stub 0x2000063F  (r0 = milliseconds)
  * button A/B/C   : API stubs 0x20000425 / 0x20000431 / 0x2000043D (r0 = pressed)
  * clear A/B/C    : API stubs 0x20000449 / 0x20000455 / 0x20000461 (r0 = 0)
The API stubs are the fixed table official programs use, so they are the
safest entry points.

Usage: py make_demo.py [out.txt]
"""
import math
import struct
import sys

from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM

BASE = 0x207F0000          # where the firmware maps a location while it runs
CODE = 0x204               # code starts here (0x200: u16 1, u16 body length)
DATA = 0x1000              # our tables live here (file offset)

# ---------------------------------------------------------------- art / data

def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def hsv(h, s, v):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
    return int(r * 255), int(g * 255), int(b * 255)


SINE = bytes(round(42.5 + 42.5 * math.sin(2 * math.pi * i / 256)) for i in range(256))
# soft pastel rainbow for the plasma (256 entries)
PLASMA = [rgb565(*hsv(i / 256, 0.55, 0.95)) for i in range(256)]

# 16x16 character, 2 walking frames. '.' = transparent
SPRITE_PAL = {
    ".": 0x0000,                     # index 0 = transparent
    "K": rgb565(30, 20, 60),         # outline
    "W": rgb565(255, 255, 255),      # body
    "P": rgb565(255, 150, 190),      # cheeks
    "Y": rgb565(255, 220, 80),       # antenna / feet
    "E": rgb565(20, 20, 40),         # eyes
}
FRAMES = [
    """
.......YY.......
.......YY.......
........K.......
.....KKKKKK.....
....KWWWWWWK....
...KWWWWWWWWK...
..KWWEWWWWEWWK..
..KWWEWWWWEWWK..
..KWPWWWWWWPWK..
..KWWWWKKWWWWK..
...KWWWWWWWWK...
....KWWWWWWK....
.....KKKKKK.....
.....K....K.....
....YY....YY....
................
""",
    """
.......YY.......
.......YY.......
.......K........
.....KKKKKK.....
....KWWWWWWK....
...KWWWWWWWWK...
..KWWEWWWWEWWK..
..KWWEWWWWEWWK..
..KWPWWWWWWPWK..
..KWWWKKKKWWWK..
...KWWWWWWWWK...
....KWWWWWWK....
.....KKKKKK.....
......K..K......
.....YY..YY.....
................
""",
]
PAL_KEYS = list(SPRITE_PAL)


def sprite_bytes():
    out = bytearray()
    for fr in FRAMES:
        rows = [r for r in fr.strip("\n").split("\n")]
        assert len(rows) == 16 and all(len(r) == 16 for r in rows), "sprite must be 16x16"
        for r in rows:
            out += bytes(PAL_KEYS.index(c) for c in r)
    return bytes(out)


# 5x7 font, only the letters we use
FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    " ": ["00000"] * 7,
}
MESSAGE = "TAMAOS LAB - CUSTOM CODE RUNNING ON YOUR TAMAGOTCHI!   PRESS ANY BUTTON   "
TEXT_H = 14   # 7 rows x2


def text_bitmap(msg):
    cols = []
    for ch in msg:
        g = FONT[ch]
        for x in range(5):
            cols.append([g[y][x] == "1" for y in range(7)])
        cols.append([False] * 7)
    w = len(cols) * 2
    while w % 8:                     # pad with blank columns to a whole byte
        cols.append([False] * 7)
        w = len(cols) * 2
    bits = []
    for y in range(TEXT_H):
        bits += [cols[x // 2][y // 2] for x in range(w)]
    packed = bytes(sum(bits[i + k] << (7 - k) for k in range(8)) for i in range(0, len(bits), 8))
    return w, packed


# ---------------------------------------------------------------- code

def build(out_path, graft=None):
    """graft: path of a working location (e.g. Magic Hut). Its file is kept
    byte for byte; only its code area gets our code + data and 0xAE points at
    our entry. Otherwise a fresh official-style file is made."""
    DATA = 0x0A00 if graft else 0x1000
    tw, tbits = text_bitmap(MESSAGE)
    assert tw > 256, "scroll math assumes the banner is wider than 2 screens"
    spr = sprite_bytes()
    spal = b"".join(struct.pack("<H", SPRITE_PAL[k]) for k in PAL_KEYS) + b"\0" * (32 - 2 * len(PAL_KEYS))

    # data layout (file offsets)
    o_sine = DATA
    o_plasma = o_sine + 256
    o_spal = o_plasma + 512
    o_spr = o_spal + 32
    o_text = o_spr + len(spr)
    end = o_text + len(tbits)
    A = lambda o: BASE + o  # noqa: E731

    asm = f"""
entry:
    push {{r4-r11, lr}}
    mov r11, #0                 @ frame counter
frame:
    ldr r0, k_lcdsrc
    ldr r4, [r0]                @ r4 = framebuffer
    cmp r4, #0
    ldreq r4, k_fbdef

    @ ---- plasma: c = sin[x+f] + sin[x+y+2f] + sin[f-2y] + f
    ldr r9, k_sine
    ldr r8, k_plasma
    mov r10, r4
    mov r7, #0
py_loop:
    sub r0, r11, r7, lsl #1
    and r0, r0, #255
    ldrb r6, [r9, r0]
    add r6, r6, r11             @ row term + colour cycling
    mov r5, #0
px_loop:
    add r0, r5, r11
    and r0, r0, #255
    ldrb r1, [r9, r0]
    add r0, r5, r7
    add r0, r0, r11, lsl #1
    and r0, r0, #255
    ldrb r2, [r9, r0]
    add r1, r1, r2
    add r1, r1, r6
    and r1, r1, #255
    mov r1, r1, lsl #1
    ldrh r1, [r8, r1]
    strh r1, [r10], #2
    add r5, r5, #1
    cmp r5, #128
    blt px_loop
    add r7, r7, #1
    cmp r7, #128
    blt py_loop

    @ ---- bouncing sprite: x = 8 + sin[3f] (8..93), y = 24 + sin[5f+64]/2
    add r0, r11, r11, lsl #1
    and r0, r0, #255
    ldrb r9, [r9, r0]
    add r9, r9, #8              @ r9 = sx
    ldr r0, k_sine
    add r1, r11, r11, lsl #2
    add r1, r1, #64
    and r1, r1, #255
    ldrb r6, [r0, r1]
    mov r6, r6, lsr #1
    add r6, r6, #20             @ r6 = sy
    ldr r0, k_spr
    and r1, r11, #4             @ frame = (f>>2)&1 -> offset 256
    add r0, r0, r1, lsl #6
    ldr r1, k_spal
    mov r7, #0
sy_loop:
    mov r5, #0
sx_loop:
    mov r2, r7, lsr #1
    mov r3, r5, lsr #1
    add r2, r3, r2, lsl #4
    ldrb r2, [r0, r2]
    cmp r2, #0
    beq s_skip
    mov r2, r2, lsl #1
    ldrh r2, [r1, r2]
    add r3, r7, r6
    add r12, r5, r9
    add r3, r12, r3, lsl #7
    mov r3, r3, lsl #1
    strh r2, [r4, r3]
s_skip:
    add r5, r5, #1
    cmp r5, #32
    blt sx_loop
    add r7, r7, #1
    cmp r7, #32
    blt sy_loop

    @ ---- banner: dark band y=104..121, text at y=106
    ldr r1, k_band
    mov r2, #104
    add r0, r4, r2, lsl #8      @ fb + 104*256
    mov r3, #0x900              @ 18 rows * 128 px
band_loop:
    strh r1, [r0], #2
    subs r3, r3, #1
    bne band_loop

    mov r0, r11, lsl #1         @ scroll = 2f mod W
    ldr r1, k_tw
scroll_mod:
    cmp r0, r1
    subge r0, r0, r1
    bge scroll_mod
    mov r8, r0                  @ r8 = scroll
    ldr r10, k_text
    ldr r12, k_white
    mov r7, #0
ty_loop:
    mov r5, #0
tx_loop:
    add r2, r5, r8
    cmp r2, r1
    subge r2, r2, r1
    mla r3, r7, r1, r2          @ bit index = row*W + tx (1 bit per pixel, MSB first)
    mov r0, r3, lsr #3
    ldrb r0, [r10, r0]
    and r3, r3, #7
    rsb r3, r3, #7
    mov r0, r0, lsr r3
    tst r0, #1
    beq t_skip
    add r3, r7, #106
    add r3, r5, r3, lsl #7
    mov r3, r3, lsl #1
    strh r12, [r4, r3]
t_skip:
    add r5, r5, #1
    cmp r5, #128
    blt tx_loop
    add r7, r7, #1
    cmp r7, #{TEXT_H}
    blt ty_loop

    @ ---- show it, wait, check buttons
    ldr r3, k_present
    mov lr, pc
    bx r3
    mov r0, #30
    ldr r3, k_wait
    mov lr, pc
    bx r3
    ldr r3, k_keya
    mov lr, pc
    bx r3
    mov r5, r0
    ldr r3, k_keyb
    mov lr, pc
    bx r3
    orr r5, r5, r0
    ldr r3, k_keyc
    mov lr, pc
    bx r3
    orrs r5, r5, r0
    bne done
    add r11, r11, #1
    ldr r0, k_maxf
    cmp r11, r0
    blt frame
done:
    mov r0, #0
    ldr r3, k_clra
    mov lr, pc
    bx r3
    mov r0, #0
    ldr r3, k_clrb
    mov lr, pc
    bx r3
    mov r0, #0
    ldr r3, k_clrc
    mov lr, pc
    bx r3
    mov r0, #0
    pop {{r4-r11, lr}}
    bx lr

k_lcdsrc:  .word 0xD050033C
k_fbdef:   .word 0xF8017B30
k_sine:    .word {A(o_sine):#x}
k_plasma:  .word {A(o_plasma):#x}
k_spal:    .word {A(o_spal):#x}
k_spr:     .word {A(o_spr):#x}
k_text:    .word {A(o_text):#x}
k_tw:      .word {tw}
k_band:    .word 0x18C3
k_white:   .word 0xFFFF
k_present: .word 0x20000713
k_wait:    .word 0x2000063F
k_keya:    .word 0x20000425
k_keyb:    .word 0x20000431
k_keyc:    .word 0x2000043D
k_clra:    .word 0x20000449
k_clrb:    .word 0x20000455
k_clrc:    .word 0x20000461
k_maxf:    .word 1500
"""
    ks = Ks(KS_ARCH_ARM, KS_MODE_ARM)
    enc, _ = ks.asm(asm, BASE + CODE)
    code = bytes(enc)
    assert CODE + len(code) <= DATA, f"code too big: {len(code)} bytes"

    if graft:
        g = bytearray(open(graft, "rb").read())
        old_entry = struct.unpack_from(">I", g, 0xAE)[0]
        assert end <= old_entry, f"our code+data ({end:#x}) would overwrite past the old entry {old_entry:#x}"
        g[CODE:CODE + len(code)] = code
        g[o_sine:o_sine + 256] = SINE
        g[o_plasma:o_plasma + 512] = b"".join(struct.pack("<H", c) for c in PLASMA)
        g[o_spal:o_spal + 32] = spal
        g[o_spr:o_spr + len(spr)] = spr
        g[o_text:o_text + len(tbits)] = tbits
        struct.pack_into(">I", g, 0xAE, CODE)
        body = g[:-2]
        out = bytes(body) + struct.pack(">H", sum(body) & 0xFFFF)
        open(out_path, "wb").write(out)
        print(f"wrote {out_path}: {len(out)} bytes grafted onto {graft} (code {len(code)} B, ours end at {end:#x}, old entry {old_entry:#x})")
        return

    body = bytearray(end)
    # header, modelled on the official JP locations (big-endian fields)
    body[0:6] = b"TAMAGO"
    name = "tamaos_demo.jpg".encode("utf-16-be")
    body[6:6 + len(name)] = name
    body[0x34:0x34 + 13] = b"tg18_ode19001"
    body[0x4C:0x52] = bytes([0x03, 0x01, 0x94, 0x02, 0x47, 0x02])   # version, destination = location
    body[0x52:0x5A] = bytes.fromhex("687c9994484ea675")              # signature (as Bolter/official)
    struct.pack_into(">H", body, 0x5A, 19001)
    for k, ch in enumerate("tamaos"):                                # display name in Tama letters
        struct.pack_into(">H", body, 0x5E + 2 * k, 0x04E0 + ord(ch) - ord("a"))
    struct.pack_into(">I", body, 0xAE, CODE)                         # entry offset
    body[0xFF] = 0x40
    body[0x200:0x202] = b"\x00\x01"
    body[CODE:CODE + len(code)] = code
    body[o_sine:o_sine + 256] = SINE
    body[o_plasma:o_plasma + 512] = b"".join(struct.pack("<H", c) for c in PLASMA)
    body[o_spal:o_spal + 32] = spal
    body[o_spr:o_spr + len(spr)] = spr
    body[o_text:o_text + len(tbits)] = tbits

    total = len(body) + 2
    struct.pack_into(">I", body, 0x48, total)
    struct.pack_into(">I", body, 0x30, total + 0x422)
    struct.pack_into(">H", body, 0x202, total - CODE - 2)
    out = bytes(body) + struct.pack(">H", sum(body) & 0xFFFF)
    open(out_path, "wb").write(out)
    print(f"wrote {out_path}: {len(out)} bytes, code {len(code)} bytes, banner {tw}px wide")


if __name__ == "__main__":
    # py make_demo.py OUT.txt [--graft WORKING_LOCATION.txt]
    args = sys.argv[1:]
    graft = None
    if "--graft" in args:
        i = args.index("--graft"); graft = args[i + 1]; del args[i:i + 2]
    build(args[0] if args else "tamaos_demo.txt", graft)
