# TamaOS — Full Handoff

TamaOS sends custom content to a Tamagotchi On / Meets over Bluetooth Low Energy (BLE), without the dead official app. This file replaces the old `HANDOFF.md` on the PC, which is out of date about points.

**Status as of 2026-11-07**

- **Sending works.** Wallpapers (including your own photos), custom toys and custom food all show up on the device.
- **Sending works from both phone and PC.** The iPhone sends through the Bluefy browser. A Windows PC sends with the Python script.
- **Gotchi Points (coins) are understood.** They are verified byte-for-byte against the MyMeets app's code and its Bluetooth capture. They are **not yet confirmed on the device** with the new page.

## Repo layout

| Path | What it is |
|---|---|
| `index.html` | The TamaOS Sender page: one self-contained file, served by GitHub Pages |
| `pc/tamaos_send.py` | PC sender (needs `pip install bleak`). This is the fixed version, with points at 0xbb/0xbc. |
| `items/*.txt` | The custom items and the starter wallpaper, pulled out of `index.html` as files |
| `HANDOFF.md` | This file |

`pc/tamaos_send.py` was rebuilt from this spec. It is checked to build the exact same bytes as `index.html` (the hello, plus each of the 5 items at 0, 50, 1,000 and 99,999 points). It has not yet been run against the device.

---

## 1. Goal and direction

- The owner wants the Tama to become something "completely different than the base Tama idea": a custom gadget, not a pet. It should be something nobody else has done.
- The plan has three phases:
  1. A PC hub.
  2. An "arcade" of custom items and games.
  3. Possibly custom firmware.
- The owner now uses an iPhone only. There is no PC right now, so the phone path matters most. Getting this working on iPhone was a big goal, because other community tools (WebMeets, MyMeets) are Android or Windows only.
- The owner wants things in depth, visual and fun, such as guns, skateboards and food. They care how the sprites look.

## 2. Hardware and Bluetooth basics

| Thing | Value |
|---|---|
| Advertised name | `TMGC_meets` |
| Example MAC | `68:FB:95:0E:92:00` |
| Service | `0000fff0-0000-1000-8000-00805f9b34fb` |
| Write char (to Tama) | `0000fff2-…`, write without response, ATT handle 0x13 |
| Notify char (from Tama) | `0000fff1-…`, CCCD handle 0x16 |
| MTU | 23, so send 20-byte chunks |

**How to make the Tama connectable:** open the connection menu and pick **APP**. Press back. Then pick **Connection → Download**. It now advertises `TMGC_meets` and sits on the waiting screen.

The Tama refuses connections while it's asleep. To get around this, set its clock to daytime.

## 3. Link layer (framing)

Every message (hello or item) is framed like this:

```
PC  → f0 8d                     start of message
PC  → <message in 20-byte chunks>
PC  → f0 cd                     end of message
Tama→ f0 0c LL LL xx xx xx 00   ack (LLLL = length received)
PC  → f0 8e 0d                  "your turn"
Tama→ f0 0d …                   start of its reply
Tama→ <reply data>
Tama→ f0 4d                     end of its reply
```

The full session runs in this order:

1. Enable notifications.
2. Send the hello. The Tama acks.
3. Send "your turn". The Tama replies.
4. Send the item. The Tama acks.
5. Send "your turn". The Tama replies. Done.

Pacing:

- Use about 40–45 ms per chunk. Going faster makes the Tama's progress bar lag, and the transfer fails.
- Don't read notifications in the middle of a transfer.
- On Windows, writes queue up, so keep a steady pace (`deadline += delay`).

## 4. Message format (PC → Tama)

Multi-byte numbers here are **little-endian**. The layout comes from MyMeets' own compiled code (decompiled with `ilread.py`) and matches its Bluetooth capture byte-for-byte.

| Offset | Size | Value |
|---|---|---|
| 0x00 | 6 | ASCII `TAMAGO` |
| 0x48 | u32 | total message length |
| 0x4c | 1 | `0x17` |
| 0x52 | 8 | sender/security code `7c 68 48 97 75 a6 4e 99` |
| 0x5e | 1 | **COMMAND**: `0x00` = hello, `0x3a` = send item. The Tama replies with command + 1 (`0x01` / `0x3b`). |
| 0xbb | 1 | `0x03` = points marker (only if points > 0) |
| 0xbc | u32 | **Gotchi Points** to add (MyMeets max 99,999) |
| 0xd4 | u32 | 256 when an item is attached |
| 0xfc | 4 | `10 00 01 04` |
| 0x100 | … | item part: u32 2, u32 1, u32 itemLen, item bytes, u32 0 |
| end | u16 | checksum = sum of every earlier byte (low 16 bits), little-endian |

- The hello has no item part. It is 0x102 bytes long, with command `0x00`.
- **Big past mistake:** we once thought 0x5e held the points, and that "58 points works". 58 is actually `0x3a`, the send-item command. Putting 0 or 1 there makes an invalid command, and that was the cause of the "fails at 100%" bug. The real points field is at 0xbb/0xbc.
- The Tama's reply has `TAMAGO` and the command + 1 at 0x5e. It does **not** contain the Tama's point total.

## 5. Item file format

Items are the `.txt` files in MyMeets `assets/items/<lang>/`. They're actually binary. Their multi-byte fields are **big-endian**.

| Offset | Field |
|---|---|
| 0x00 | `TAMAGO` |
| 0x06 | file name, UTF-16BE (shows in MyMeets, not on the Tama) |
| 0x34 | ASCII asset ID, e.g. `tg19_bg50001`, `tg16_oy03101_1` |
| 0x4a | u16 length |
| 0x4c | version (`02` or `03`) |
| 0x4f | type: `01` food, `02` accessory, `04` toy, `07` wallpaper |
| 0x51 | food kind: `01` meal, `02` snack |
| 0x5a | u16 number ID (e.g. `0xc351` = 50001). It **must** match the number in the ASCII ID. |
| 0x5e | display name in the Tama's font: a=`0x04e0` … z=`0x04f9`, two bytes each, up to 11 letters |
| 0x76 | u16 shop price |
| 0x78 | toy behavior/animation ID (20 = throw-at-target like the shuriken, 34 = ride like the bike) |
| after the price | effect bytes for hunger and happiness (named in the MyMeets code) |
| 0x200 | image frames (below) |
| last 2 | checksum, big-endian: sum of every earlier byte |

### Image frames (at 0x200)

- The section starts with a u16 frame count.
- Each frame has:
  - a u16 size, then width, height and color count, then 3 more bytes;
  - a palette of u16 big-endian BGR565 colors;
  - 4-bit pixels (the high nibble is the left pixel).
- Palette slot 0 is transparent (`07e0`, green).

| Type | Frames |
|---|---|
| Wallpaper | 1 frame, 128×128, 15 colors. Palette at 0x20a (not 0x208), pixels at 0x228. |
| Food | 3 frames, 24×24: full, bitten, almost gone |
| Toy (behavior 20) | frame 0 = 32×30 shop icon; frame 1 = held object (18×18, drawn in the pet's hand); frame 2 = flying object (40×20); frames 3–4 = target and target hit (32×32) |
| Toy (behavior 34) | frame 0 = icon, frame 1 = the ride sprite |
| Accessories | different layout, not decoded yet |

### What can and can't be changed

- **Can change:** pictures, name, price, ID, the toy behavior (choosing from existing ones), food type, and probably the effect values.
- **New IDs work.** Wallpaper 51001 and the custom items all showed up.
- **Can't change:** game logic and reactions. For example, the pet looking happy or sad when the gun misses is firmware. Items can only pick an existing behavior.
- **Gotchas we hit:**
  - A new wallpaper with the old number at 0x5a doesn't show up.
  - Forgetting the display name makes the item show as "halloween" (the name from the template).

## 6. What's been built

### TamaOS Sender (`index.html`, iPhone and any Web Bluetooth browser)

- One self-contained HTML page. (The earlier source copy was `tamaos_src.html`. `index.html` is the standalone build, and it's the one to edit now.)
- **iPhone:** Safari has no Web Bluetooth, so use the **Bluefy** browser. Bluefy only allows Bluetooth on a top-level https page. The Claude artifact frame blocks it, so the page has to be self-hosted.
  - It was on tiiny.host, but that account is out of uploads.
  - Now: **GitHub Pages** from this repo (Settings → Pages → deploy from `main`). The URL is `https://aviscryptostuff-bit.github.io/tamasend/`.
- **How to tell you have the new page:** the coins hint says *"Sent along with the item. 0 to 99,999."*, the box starts at 0, and the top shows `+0 PTS`. If it says "58 is tested…", that's the old page.
- Features:
  - Starter wallpaper.
  - Photo → wallpaper. Converts to 128×128 with 15 colors, using median-cut quantizing and Floyd–Steinberg dithering. The wallpaper number auto-increments from 51001 and is saved in localStorage.
  - Price override for wallpapers (default 1).
  - Gotchi Points (0–99,999).
  - Animated preset cards: pistol, skateboard, pizza, burger.
  - A step-by-step log, with `describe()` turning Bluefy's raw error codes into readable messages.
  - Falls back from write-without-response to write.
  - 40 ms pacing.
- Verified on 2026-11-07:
  - hello and item (0 pts) match the MyMeets capture byte-for-byte;
  - 50 / 1,000 / 99,999 points build correctly;
  - the wallpaper encoder round-trips the real wallpaper;
  - all presets are valid. This was re-checked in this repo: each has a good checksum, its length matches 0x4a, and its number at 0x5a matches its ID.

### Custom items (`custom/build_items.py`, on the PC)

These are built from real MyMeets items used as templates. The script swaps in new frames (same size and color count), the file name, ID, number, display name, price and checksum. The built files are in `items/`.

| Item | Template | ID | Behavior | File |
|---|---|---|---|---|
| pistol | `tg18_as00025_1` (shuriken) | `tg16_as03305_1` | throw at target; the held-pistol frame matches the big icon | `items/pistol_as03305.txt` |
| skateboard | `as01118` (bike) | `tg16_as03302_1` | ride | `items/skateboard_as03302.txt` |
| pizza | `oy01001` (snack) | `tg16_oy03101_1` | snack | `items/pizza_oy03101.txt` |
| burger | `gh00083` (meal) | `tg16_gh03201_1` | meal | `items/burger_gh03201.txt` |

- All are priced at 1.
- Sprites are drawn as text maps in the script (`PISTOL_BIG` 30×19, `PISTOL_HELD` 18 wide with the grip at the left edge).
- `build_items.py` itself isn't in this repo yet. Copy it in from the PC when you're back on one.

### PC tools (Windows, `Downloads\TamaOS`)

- `tamaos_send.py` sends any item file. Usage: `python tamaos_send.py <item.txt> [--points N] [--delay ms]`. It needs `pip install bleak`.
  - **The copy on the PC is outdated** (it puts points at 0x5e). Replace it with `pc/tamaos_send.py` from this repo.
  - The new version also has `--address MAC` (skips scanning) and `--dump FILE` (builds the message without sending), and it warns about a bad checksum or a 0x5a/ID mismatch.
- `tamaos_scan.py` is the first scanner/GATT mapper.
- `tools/parse_capture.py` parses btvs/Wireshark captures.
- `ilread.py` is a small .NET IL disassembler, used to read `MyMeets.exe`.
- Sniffing setup: btvs at `C:\BTP\v1.14.0\x86\btvs.exe` plus Wireshark, with MyMeets at `Downloads\MyMeets2_3_7`.

## 7. Problems solved (so they don't come back)

| Problem | Cause / fix |
|---|---|
| WebMeets on Windows Chrome dropped with a GATT disconnect | Gave up on that and captured MyMeets with btvs + Wireshark instead |
| Transfer failed at 100% | The command byte at 0x5e was wrong (see §4) |
| Tama's bar lagged and failed partway | Sent too fast. Pace at about 40–45 ms per chunk and stop reading notifications mid-transfer. |
| "Your Tama is asleep" | Set its clock to daytime |
| No logs in Bluefy | The Claude artifact frame blocks Bluetooth, so self-host the page |
| Bluefy shows "Error undefined / 2" | Raw error codes, now translated by `describe()` |
| Google login broken inside Bluefy | Use a public link instead of logging in |
| Wallpaper colors wrong | Palette offset was 0x20a, not 0x208; colors are BGR565 big-endian |
| Photo wallpaper never showed up | The number at 0x5a must match the new ID |
| Shop said "halloween" | Set the display name at 0x5e |
| Gun not in the hand | Frame 1 is the held sprite, so it was redrawn |
| Coins "still don't work" | The owner was on the old tiiny page. Host the new `index.html`. |
| Page told iPhone users to "use Chrome on Android" | The no-Bluetooth messages now mention Bluefy for iPhone |

## 8. Next steps

1. **Turn on GitHub Pages** for this repo (Settings → Pages → Deploy from a branch → `main`, `/ (root)`). Then open `https://aviscryptostuff-bit.github.io/tamasend/` in Bluefy.
2. **Test coins.** Send the Starter wallpaper with 50 points. If it fails, save the log.
3. If points work with wallpapers but not with toys or food, try version byte `03` on those items. Or copy exactly how MyMeets sends points with that item type (capture it).
4. Possible additions:
   - a one-tap "Send coins" button;
   - more custom items using other behavior IDs;
   - decode accessories;
   - decode the effect bytes (hunger and happiness);
   - character data (MyMeets `assets/characters`).
5. Back on a PC: use `pc/tamaos_send.py` from this repo, and copy `custom/build_items.py`, `tools/` and `ilread.py` into the repo.
6. The longer-term ideas (hub, arcade, firmware) are still open.

## 9. Notes for whoever picks this up

- The owner is non-technical and phone-first. Give short, step-by-step instructions, and expect screenshots back.
- Treat the downloaded MyMeets package as untrusted. Only read it; don't run it.
- Never claim something works on the device until the owner confirms it.
