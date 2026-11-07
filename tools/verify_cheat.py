"""Run a Cheat-Hut/Magic-Hut item program's cheat routine inside Unicorn and
check what it writes to a fake pet struct. Verifies custom-program LOGIC with
no device. The program's ARM code runs sandboxed; only firmware hooks are faked."""
import sys, struct
from unicorn import *
from unicorn.arm_const import *

item = open(sys.argv[1], "rb").read()   # a Magic-Hut-style location file (community/*.txt or a patched copy)
PROG = 0x207F0000                       # downloaded program loads here
PET  = 0x20800000                       # fake pet struct
PETPTR_GLOBAL = 0x200004D4              # firmware global holding the pet pointer
VARTBL = 0x1e44                         # offset in the item of the variable table (region 0 = first 12 u32)

uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
uc.mem_map(0x20000000, 0x01000000)                     # firmware RAM window (holds PROG, PET, global)
uc.mem_write(PROG, item)
uc.mem_write(PETPTR_GLOBAL, struct.pack("<I", PET))    # pet pointer -> fake pet
uc.mem_write(PET, b"\x00" * 0x600)                     # clear fake pet

# Stub the item's GetVarPtr (file 0x418) so we skip firmware region detection:
#   r0 = variable index -> returns pet_pointer + table[index]
def hook_code(uc, addr, size, _):
    if addr == PROG + 0x418:
        idx = uc.reg_read(UC_ARM_REG_R0)
        off = struct.unpack_from("<I", item, VARTBL + 4*idx)[0]
        petptr = struct.unpack_from("<I", uc.mem_read(PETPTR_GLOBAL, 4), 0)[0]
        uc.reg_write(UC_ARM_REG_R0, petptr + off)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))   # return
uc.hook_add(UC_HOOK_CODE, hook_code)

def call(entry):
    uc.reg_write(UC_ARM_REG_SP, PET + 0x400)
    uc.reg_write(UC_ARM_REG_LR, 0x20FF0000)          # sentinel return
    uc.emu_start(PROG + entry, 0x20FF0000, count=100000)

# coins routine is at file 0x788, patched value at 0x7a0
coins_val = struct.unpack_from("<I", item, 0x7a0)[0]
coins_off = struct.unpack_from("<I", item, VARTBL + 4*3)[0]   # var 3 = Gotchi Points
call(0x788)
written = struct.unpack_from("<I", uc.mem_read(PET + coins_off, 4), 0)[0]
print(f"coins routine: patched value in file = {coins_val}, written to pet[+{coins_off:#x}] = {written}  -> {'OK' if written==coins_val else 'MISMATCH'}")

# stats routine at file 0x5fc: var2=happiness(=file 0x600 imm), var0=6, var1=0
happy_imm = item[0x600]
uc.mem_write(PET, b"\x00" * 0x600)
call(0x5fc)
h = uc.mem_read(PET + struct.unpack_from("<I", item, VARTBL+4*2)[0], 1)[0]
v0 = uc.mem_read(PET + struct.unpack_from("<I", item, VARTBL+4*0)[0], 1)[0]
print(f"stats routine: happiness imm in file = {happy_imm}, written var2 = {h}, var0 = {v0}  -> {'OK' if h==happy_imm else 'MISMATCH'}")
