# TamaOS — Start Here (session handoff)

Last updated: 2026-11-07. Short status so anyone (or a new session) can pick up fast. Deep detail is in [HANDOFF.md](HANDOFF.md) (sections 1–15).

## What TamaOS is

A phone-first website that talks to a Tamagotchi On/Meets over Bluetooth, with no official app. Live at **https://aviscryptostuff-bit.github.io/tamasend/** (open in **Bluefy** on iPhone). Source builds from `tools/page.html` via `python tools/build_page.py` → `index.html`. Site data is in `data/`.

Owner is phone-only most of the time (a PC is occasionally borrowed). Keep instructions short and step-by-step.

## The site today (all tabs live)

- **Shop:** every MyMeets item (849 EN+JP) + Bolter's community mods (Magic Hut, Moon Terrace, Potion) under "Community mods", all sendable with Gotchi Points.
- **Custom:** presets (pistol/skateboard/pizza/burger), photo→wallpaper, starter wallpaper, any item file, and the **Cheat Hut** (see below).
- **Marry:** full MyMeets marriage — build a partner, Visit then Marry (or Back).

## Confirmed working on the real device

- Sending items, Gotchi Points, photo wallpapers. ✓
- **Marriage** (gave a baby, asked to name it). ✓

## The Cheat Hut (Custom tab) — verified cheats

Re-programs Bolter's Magic Hut in the browser and sends it. Each cheat is proven in a sandbox (`tools/verify_cheat.py`, Unicorn) before shipping:

- **Coins** (Gotchi Points) — any value 0–99,999
- **Happiness** — any value 0–100
- **Hunger** — any value
- **Growth stage** — set exactly (baby → adult; fixes "too young to marry")

**Pending real-device test:** send the Cheat Hut with growth "Set to 2", stats maxed, and confirm the Tama is old enough to marry. If it works, growth cheat is confirmed on hardware.

## Firmware research (how cheats are made safely)

- Hardware: GeneralPlus ARM7TDMI SoC. Firmware runs at `0x20000000`; pet state in SRAM; ON Magic EN pet struct base = `0xF800D864`.
- We have community firmware dumps (`github.com/kaero/t-on`) and a working emulator (`github.com/oreo-fox/nijiiro-egg`). **No firmware binary is committed here** (Bandai copyright) — analyzed locally only.
- Sandbox + verifier means any value cheat can be proven before it touches the device.
- Full pet-struct map in HANDOFF §15; firmware API/loader in §11–12; cheat-field map in §14.

## Honest frontier (what's NOT done, and why)

- New fields found (`+0x3a`, `+0x52`, `+0x384`...) are **game-state flags**, not simple stats — unsafe to set blind.
- The wild stuff — **secret characters, god mode, age/weight, unlocks** — is real but needs the **emulator actually running on a PC** to see effects before bottling them as cheats. Doing it blind risks corrupting the pet. This is the main "next session with a PC" task.
- `docs/EMULATOR_SETUP.md` is the guide to run nijiiro-egg on a borrowed PC.

## Suggested next steps

1. Owner: test the growth cheat on the real Tama (above).
2. When a PC is free: follow `docs/EMULATOR_SETUP.md`, get nijiiro-egg booting, then a session can safely explore character/unlock cheats by watching the emulator.
3. Optional safe add: a one-tap "marry-ready" combo (adult + full stats) in the Cheat Hut.

## Dev notes

- Edit `tools/page.html`, run `python tools/build_page.py`, test headless (Playwright/Chromium is preinstalled), commit, PR to `main` (Pages auto-deploys).
- `tools/`: `verify_cheat.py` (cheat sandbox), `disasm_item.py` (ARM disassembly of location/game files), `mymeets_ref.py` (Python port of MyMeets), `make_data.py`/`build_page.py`.
- Branch: `claude/tamaos-handoff-yp5nwd`.
