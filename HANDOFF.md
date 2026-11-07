# TamaOS — Full Handoff

TamaOS sends custom content to a Tamagotchi On / Meets over Bluetooth Low Energy (BLE), without the dead official app. This file replaces the old `HANDOFF.md` on the PC, which is out of date about points.

**Status as of 2026-11-07**

- **Sending works.** Wallpapers (including your own photos), custom toys and custom food all show up on the device.
- **Sending works from both phone and PC.** The iPhone sends through the Bluefy browser. A Windows PC sends with the Python script.
- **Gotchi Points (coins) are understood.** They are verified byte-for-byte against the MyMeets app's code and its Bluetooth capture. They are **not yet confirmed on the device** with the new page.

**Added later on 2026-11-07 (not yet tried on the device):**

- The site now has every MyMeets feature: the full **Catalogue** (Shop tab) and **Marriage** (Marry tab, with Visit and Back).
- **Pixel order was wrong.** 4-bit pixels are **low nibble first**, not high (see §5). The photo encoder and our four presets have been fixed.

## Repo layout

| Path | What it is |
|---|---|
| `index.html` | The site (Shop, Custom and Marry tabs), served by GitHub Pages. It is **built** from `tools/page.html`. |
| `data/` | The MyMeets catalogue and character assets used by the Shop and Marry tabs (about 6.7 MB). They must be uploaded next to `index.html`. |
| `pc/tamaos_send.py` | PC sender (needs `pip install bleak`). This is the fixed version, with points at 0xbb/0xbc. |
| `items/*.txt` | The custom items and the starter wallpaper |
| `tools/page.html` | Source of the site. Run `python tools/build_page.py` after editing it. |
| `tools/mymeets_ref.py` | A Python port of MyMeets 2.3.7 (item parsing, images, characters, every packet type), written from its IL. The site's JavaScript is checked against it. |
| `tools/make_data.py` | Rebuilds `data/` from a MyMeets `assets` folder |
| `tools/fix_nibbles.py` | Swaps the pixel nibbles in an item file and fixes its checksum |
| `tools/palettes.json`, `tools/dna.json` | Character color sets and DNA patterns copied out of MyMeets.exe |
| `HANDOFF.md` | This file |

`pc/tamaos_send.py` was rebuilt from this spec. It is checked to build the exact same bytes as `index.html` (the hello, plus each of the 5 items at 0, 50, 1,000 and 99,999 points). It has not yet been run against the device.

**About `data/`:** these are Bandai's item and character files, as shipped inside MyMeets. Putting them in a public repo makes them public. That's the owner's call.

---

**Confirmed on the device (2026-11-07):** a marriage from the Marry tab worked. The Tama showed a baby and asked for a name, which is the normal result of a marriage. Still to confirm: which mode was used, and whether the Experimental (not adult) switch was on.

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

### All message types (from MyMeets' `BLETmgcPacket`)

Byte 0x4c is the **operand** and 0x5e is the **command**. Every exchange is: hello (`operand`, command 0x00), the Tama's reply, the real message, the Tama's reply.

| Feature | Operand | Command | Size |
|---|---|---|---|
| Send item | 0x17 | 0x3a | 0x100 + item part + 2 |
| Visit (Tama goes to the app) | 0x14 | 0x34 | 0x102, no data |
| Back (bring the Tama home) | 0x15 | 0x36 | 0x102, no data |
| Marriage | 0x16 | 0x38 | 0x99a6 (39,334) |

**Marriage message.** It uses the same header, plus:

- 0x42: 3 color-set numbers, for body, head and back.
- 0x5f–0xba: a partner record (sex, name "TAMA" in mojis, body ID, generation 2, growth 4, birthday 0x101, DNA patterns).
- 0xcc / 0xd0 / 0xec: offsets of three attached sections (0x100, 0x810c, 0x8198).

It has three sections, each with a header of `u32 kind, u32 1, u32 size`:

1. A 32 KB character block. It holds each part's Offset, Tbl and Char files at fixed places. The partner's sex goes at body Tbl + 6.
2. 0x80 bytes of character info.
3. Two 48×40 "parent" pictures, 0xc00 each.

`tools/mymeets_ref.py` has the full layout.

**Marriage flow (MyMeets):**

1. **Visit.** On the Tama: Connection → App → Visit (あそびにいく). Send the Visit messages. The second reply is the visiting Tama's data:
   - 0x5f is its sex.
   - The u32 at 0xcc points to a section where +14 is its character ID.
   - The u32 at 0xd0 points to a section where +14 is its growth stage. 2 or more means adult.
   - Bytes 114–115, 120–121, 138–139 and 142–143 of the first reply are a "visitor ID".
2. **Marry or Back.** Press a button on the Tama, then Connection → App → Return? (かえる？) → Yes. Send the Marriage messages, or Back if the Tama isn't an adult.

The menu names come from MyMeets' own instruction pictures inside the exe. For items, MyMeets uses Connection → App → **Present** (プレゼント).

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

MyMeets reads the header as:

- 0x30: u32 real file size.
- 0x48: u32 file size.
- 0x4c: u16 ROM version.
- 0x4e: u32 **destination**. This sets the type:
  - `81071f00` wallpaper
  - `81010101` / `81010102` / `81010201` / `81010d02` food
  - `81042a01` item
  - `81023400` / `81023500` accessory
  - `94025b01` game
  - `94024702` station
- 0x52: u64 signature.
- 0x5a: ID.
- 0x5e: name in mojis.
- 0x76: price.
- 0x78: animation.
- 0x7a: hunger effect.
- 0x7b: happiness effect.

Images start at 0x200, except for accessories, where they start at 0x5c2. Games and stations have no images that MyMeets reads.

**Mojis (Tama text):** byte pairs of `language` (4 = JP, 8 = EN) and `row<<4 | column`, looked up in a 16×16 table (the `MOJIS` table in the site).

### Image frames (at 0x200)

- The section starts with a u16 frame count.
- Each frame has:
  - a u16 size, then width, height and color count, then u16 1 (or 256 for 8-bit), then 0xff;
  - a palette of u16 big-endian BGR565 colors;
  - pixels: 4-bit if there are 16 colors or fewer, otherwise 8-bit.
- **The low nibble is the left pixel.** We had this backwards. MyMeets' `TamagoImage` reads low-first, and every official item is much smoother read that way (464k vs 567k neighbour changes). Our photo wallpapers and the four presets were sent with each pair of pixels swapped. Both are fixed now.
- Slot 0 / pixel (0,0) is the transparent color (`07e0`, green).

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

### TamaOS site (`index.html` + `data/`, iPhone and any Web Bluetooth browser)

- Built from `tools/page.html` by `tools/build_page.py`. The Shop and Marry tabs load `data/` when they're first opened.
- **Tabs:**
  - **Shop** is MyMeets' Catalogue: English and Japanese items by type, with search, animated preview and price.
  - **Custom** is the original sender (presets, photo, starter, item file).
  - **Marry** is MyMeets' Marriage:
    - pick body, face, head and back from any of 118 characters;
    - 13 color sets for body, head and back;
    - Random character, Random colors, or a whole character;
    - Marry character / Get character / Random genes;
    - Boy, girl or random sex, and English or Japanese speech;
    - then Visit → Marry, or Back.
- The visit state is kept in localStorage, so reloading between step 1 and step 2 is safe.
- After a visit, the Marry tab shows **Your Tama**:
  - from the reply: character ID and picture, growth stage, and probable sex, name, generation and birthday;
  - **Save** and **Copy** buttons for the raw reply. These dumps are the starting point for real mods (for example, finding where age is stored).
- **Experimental switch:** allows marrying a Tama that isn't an adult. MyMeets blocks this in the app, not on the Tama. Nobody knows what the Tama does with it, and the page warns about that.
- The owner asked about a "Magic Hut" age-up cheat. Nothing documented was found; it's a location in the Magic version.
- **iPhone:** Safari has no Web Bluetooth, so use the **Bluefy** browser. Bluefy only allows Bluetooth on a top-level https page. The Claude artifact frame blocks it, so the page has to be self-hosted.
  - It was on tiiny.host, but that account is out of uploads.
  - Now: **GitHub Pages** from this repo (Settings → Pages → deploy from `main`). The URL is `https://aviscryptostuff-bit.github.io/tamasend/`.
- **How to tell you have the new page:** the coins hint says *"Sent along with the item. 0 to 99,999."*, the box starts at 0, and the top shows `+0 PTS`. If it says "58 is tested…", that's the old page.
- Features:
  - Starter wallpaper.
  - Photo → wallpaper. Converts to 128×128 with 15 colors, using median-cut quantizing and Floyd–Steinberg dithering. The wallpaper number auto-increments from 51001 and is saved in localStorage.
  - Price override (now for any item, off by default so items go out exactly as MyMeets sends them).
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
- Verified later on 2026-11-07, in headless Chromium:
  - the page's JavaScript matches `tools/mymeets_ref.py` byte for byte for character pictures, small parent pictures, the 32 KB character block, a full 39,334-byte marriage message, and the Visit, Back and hello messages;
  - the item hello still equals the real MyMeets capture;
  - with a simulated Tama, Shop send, Visit and Marry each run end to end with the right operands and commands and a correct checksum.
  - **None of the new features has been tried on a real Tama yet.** The Python port and the JS were both written from MyMeets' IL, so a misreading of the IL would be in both.

### Custom items (`custom/build_items.py`, on the PC)

These are built from real MyMeets items used as templates. The script swaps in new frames (same size and color count), the file name, ID, number, display name, price and checksum. The built files are in `items/`.

| Item | Template | ID | Behavior | File |
|---|---|---|---|---|
| pistol | `tg18_as00025_1` (shuriken) | `tg16_as03305_1` | throw at target; the held-pistol frame matches the big icon | `items/pistol_as03305.txt` |
| skateboard | `as01118` (bike) | `tg16_as03302_1` | ride | `items/skateboard_as03302.txt` |
| pizza | `oy01001` (snack) | `tg16_oy03101_1` | snack | `items/pizza_oy03101.txt` |
| burger | `gh00083` (meal) | `tg16_gh03201_1` | meal | `items/burger_gh03201.txt` |

- All are priced at 1.
- Their pixels were drawn high-nibble-first. `tools/fix_nibbles.py` re-saved them low-nibble-first, so they should now look as designed on the Tama.
- Sprites are drawn as text maps in the script (`PISTOL_BIG` 30×19, `PISTOL_HELD` 18 wide with the grip at the left edge).
- `build_items.py` itself isn't in this repo yet. Copy it in from the PC when you're back on one.

### PC tools (Windows, `Downloads\TamaOS`)

- `tamaos_send.py` sends any item file. Usage: `python tamaos_send.py <item.txt> [--points N] [--delay ms]`. It needs `pip install bleak`.
  - **The copy on the PC is outdated** (it puts points at 0x5e). Replace it with `pc/tamaos_send.py` from this repo.
  - The new version also has `--address MAC` (skips scanning) and `--dump FILE` (builds the message without sending), and it warns about a bad checksum or a 0x5a/ID mismatch.
- `tamaos_scan.py` is the first scanner/GATT mapper.
- `tools/parse_capture.py` parses btvs/Wireshark captures.
- `ilread.py` is a small .NET IL disassembler, used to read `MyMeets.exe`. A newer one, built on the `dnfile` Python package, was written in the cloud session. It decodes method signatures, enum values and static arrays. It isn't in the repo, but `tools/mymeets_ref.py` holds what it found.
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
| Sprites and photos had pixel pairs swapped | 4-bit pixels are low nibble first (§5); encoder and presets fixed |

## 8. Next steps

1. **Turn on GitHub Pages** for this repo (Settings → Pages → Deploy from a branch → `main`, `/ (root)`), with `index.html` **and** `data/` on `main`. Then open `https://aviscryptostuff-bit.github.io/tamasend/` in Bluefy.
2. **Test the Shop.** Send any wallpaper from the catalogue. Then **test Marry** with an adult Tama: step 1 (Visit), then step 2. If the Tama's menus don't match the steps on the page, send screenshots.
3. Re-send a preset (for example the pistol) and check that the sprite looks cleaner than before.
4. **Test coins.** Send the Starter wallpaper with 50 points. If it fails, save the log.
5. If points work with wallpapers but not with toys or food, try version byte `03` on those items. Or copy exactly how MyMeets sends points with that item type (capture it).
6. Possible additions:
   - a one-tap "Send coins" button;
   - more custom items using other behavior IDs;
   - decode the accessory header (images start at 0x5c2; 1,350 bytes before that aren't decoded);
   - custom marriage partners drawn from scratch (the character format is now understood).
   - (Done: effect bytes are at 0x7a hunger and 0x7b happiness. Character data is used by the Marry tab.)
7. Back on a PC: use `pc/tamaos_send.py` from this repo, and copy `custom/build_items.py`, `tools/` and `ilread.py` into the repo.
8. The longer-term ideas (hub, arcade, firmware) are still open.

## 9. Notes for whoever picks this up

- The owner is non-technical and phone-first. Give short, step-by-step instructions, and expect screenshots back.
- Treat the downloaded MyMeets package as untrusted. Only read it; don't run it.
- Never claim something works on the device until the owner confirms it.

## 10. Running our own code on the Tama (from Bolter's Magic Hut)

The owner remembered a **"time potion"** from the **Magic Hut** that grows a Tama up. It isn't in MyMeets. It's a community file by Bolter (MyMeets' author) at https://archive.org/details/magic_hut, copied into `community/` along with **Moon Terrace** and the **Potion** game. The Shop tab offers them under "Community mods". Sent the normal way (App → Download), they install as a new location or game.

### Locations and games contain ARM code

- **Locations** (destination `94024702`) and **games** (`94025b01`) are programs, not pictures.
  - 0xAE is a u32 code size.
  - 0x200 starts with `00 01 xx xx`, then the code starts at **0x204**.
  - The code is **32-bit ARM** (not Thumb): `push {..,lr}`, `mov lr,pc; bx r3` calls, literal pools.
- The file is mapped at **0x207F0000**, so the code reaches its own pictures as `0x207F0000 + file offset`.
- **Firmware functions** are called through fixed Thumb addresses `0x200004xx`–`0x20003Dxx`. Official and Bolter's files use the same ones, so it's a stable API. Seen so far (guesses from use):

| Address | Seen as |
|---|---|
| `0x20000425`, `0x20000431`, `0x2000043D` (`0x20000430 + 1/+0xD`) | button checks |
| `0x20000449`, `0x20000455`, `0x20000461` | button sounds |
| `0x200008FF`, `0x2000091F` | draw a picture |
| `0x20000933` | sound or wait (`r0 = 0x1E, r1 = 7`) |
| `0x2000063F` | delay (ms) |
| `0x20000499` | random number |
| `0x20000F47` | get a firmware resource by ID |
| `0x20003B0F` | screen or frame related |

- `0xF800D700 + 0xDA/0xDB/0xDC` hold the three button-press flags. The code clears them after reading.
- `disasm_item.py` (in `tools/`) prints an annotated disassembly. It needs `pip install capstone`.

### How the Magic Hut changes the pet

- **Firmware detection:** it sums the bytes of firmware resource `0x37`. `0x2394` gives region 0 and `0x2C3A` gives region 1 (probably JP vs EN/On). It does the same with resource `0x774`, giving one of 5 known builds.
- **Pet save pointer:** `*(u32*)0x200004D4`.
- **Pet variables** are at pointer + offset, from the table at file 0x1E44 (12 entries per region):

| Variable | Region 0 offset | Region 1 offset | Size | What the Magic Hut does with it |
|---|---|---|---|---|
| 0 | 0x005 | 0x005 | u8 | set to 6 (with 1 and 2): probably hunger or hearts |
| 1 | 0x00C | 0x00C | u8 | cleared; bit 7 set by the time potion (probably an "evolve" flag) |
| 2 | 0x011 | 0x011 | u8 | set to 100: probably happiness |
| 3 | 0x020 | 0x020 | u32 | set to 99,999: **Gotchi Points** |
| 4 | 0x036 | 0x036 | u16 | **+1 if ≤ 4: growth stage (time potion)** |
| 5 | 0x03A | 0x03A | ? | |
| 6 | 0x052 | 0x052 | u8 | read |
| 7 | 0x22E | 0x22E | ? | |
| 8 | 0x38A | 0x3A0 | ? | |
| 9 | 0x282 | 0x28A | ? | |
| 10 | 0x372 | 0x384 | u8 | bit 0 toggled |
| 11 | 0x404 | 0x420 | u8 | set, and mirrored to `0xF800C058` (region 0) or `0xF800C060` (region 1) |

- Getter and setter helpers in magic_hut.txt: set8 `0x43C`, set16 `0x458`, set32 `0x474`, get8 `0x490`, get16 `0x4A8`, get32 `0x4C0`. The potion routines start at `0x5A8` (time), `0x5FC` (stats), `0x698` (toggle) and `0x788` (coins).
- **Header differences:**
  - Bolter's files have 0x48 = file size − 2, where official files have the full size.
  - potion.txt's trailing checksum doesn't match the usual sum.
  - People report them working through WebMeets anyway, and we send them unchanged.

### Next steps for custom code

1. Send the Magic Hut and confirm on the device that the time potion grows a Tama.
2. Compare against a "Save my Tama's data" dump from a Visit. The visit reply probably carries some of the same pet variables.
3. Build our own location ("TamaOS Lab"): reuse Bolter's helpers and API calls, with our own menu, for example "grow up", "max coins", "full stats", or set any variable. This needs an ARM assembler (`arm-none-eabi-as`, or a small Python assembler). How the firmware enters the code at 0x204 still needs mapping, by comparing the official station and game files.
4. **Risk:** custom code runs with full access to the Tama. A bad write can corrupt the save; a reset should recover it, but that's unverified. Test changes one at a time.

## 11. Firmware API map (toward our own programs)

This is static analysis of the location/game files we have (official + Bolter's). We do **not** have the firmware image, so we can name functions only by how the programs use them.

### The firmware function table

Every program is ARM code at 0x207F0204 that calls fixed firmware entry points in `0x2000xxxx` / `0x20003xxx` via `ldr r3,=addr; mov lr,pc; bx r3`. Across all 11 files, only ~30 distinct entry points are ever called — this is the whole known API surface. `tools/re_api.py`-style analysis (see scratch) counted the calls:

| Address | Calls | Likely meaning |
|---|---|---|
| `0x20000425/31/3d` | ~18 | read the three buttons (A/B/C) |
| `0x20000449/55/61` | ~21 | button beeps (always r0=0) |
| `0x20000499` | 3 | random number |
| `0x2000063f` | 10 | wait, r0 = milliseconds (0x320=800, 0x20=32) |
| `0x200008ff` | 71 | draw a sprite |
| `0x2000091f` | 93 | draw a sprite at an X position |
| `0x20000933` | 249 | draw / refresh a frame (r0=500 almost always) |
| `0x20000a37` | 88 | select draw layer (mostly r0=1) |
| `0x20000f47` | 73 | **load firmware resource by ID** → pointer |
| `0x20003b0f/c93/d41` | ~170 | lower-level screen / pixel ops |
| rare: `0x5ef,0x603,0x6ff,0x713,0x89f,0x9c7,0xa9b` | 1 each | used by a single game — unexplored |

### The resource loader (0x20000f47)

Takes a resource ID in r0 and returns a pointer into firmware data. IDs seen: `0x1c, 0x37, 0x79, 0x114, 0x115, 0x378, 0x774, 0x789`. The Magic Hut sums the bytes of resources `0x37` and `0x774` to fingerprint the firmware region (JP vs EN). The ID range implies the firmware holds ~2000 internal resources (sprites, tables, sounds) that a program can pull — this is the main unmapped "content space".

### The pet save (how cheats work)

- Pet data pointer: `*(u32*)0x200004D4`.
- Variables at pointer+offset, from the table at file 0x1E44 (see section 10): growth stage (offset 0x36), Gotchi Points (0x20), happiness (0x11), hunger (0x05), etc.
- Helpers in magic_hut.txt: get8 0x490 / get16 0x4A8 / get32 0x4C0, set8 0x43C / set16 0x458 / set32 0x474.

### What this unlocks, and the honest ceiling

- **Now (no new access):** write our own location/game that calls these ~30 functions in new combinations — our own menus, cheats with our own values (the Cheat Hut already does this by patching), and loading firmware resources by ID.
- **Needs a device to experiment on:** what each of the ~2000 resource IDs actually is, and what the rare functions do. The way to learn this is a **resource probe**: a tiny, safe program that loads resource N, draws it, and lets you step N with the buttons — turning the Tama itself into the lab. This reads and draws only; it writes nothing to the save.
- **Needs the firmware image:** finding functions beyond the ~30 (direct sound synthesis, spawning characters, etc.). That requires a hardware dump of the chip or the firmware binary from elsewhere.

### Tools

- `tools/disasm_item.py` — annotated ARM disassembly of a location/game file.
- The API/resource analysis scripts live in the session scratchpad (`re_api.py`, `re_res.py`); fold them into `tools/` when continuing.

## 12. The firmware itself (the foundation for verified custom code)

To build custom programs we can *verify* before sending (instead of guessing and risking the device), we need the firmware. Found it 2026-11-07.

### Hardware (from the kaero/t-on datasheets)

- **Main chip:** GeneralPlus **GPEL3101A**, **ARM7TDMI** core (datasheet DDI0029). This confirms our item programs are ARM/Thumb — correct.
- **Bluetooth:** TI **CC2650**. **Flash:** GigaDevice **GD25Q64** (8 MB SPI). **EEPROM:** 24C128.
- Dumping is done by soldering to test points and reading the SPI flash with a minipro (`minipro -p GD25Q64C -r dump.bin`). Test-point map is in the repo.

### Where to get it

- **Community RE project:** `github.com/kaero/t-on` — two real 8 MB SPI flash dumps (magic-green, fairy-blue), the datasheets, and an **online firmware viewer** at kaero.github.io/t-on.
- The official archive.org SPI dump collection is **dark** (taken down — do not chase mirrors).
- **Do not commit the firmware binary to this repo** — it's Bandai's copyrighted code. Analyze it locally; only facts/notes go in the repo.
- Emulator for verifying programs: **Paramix Studio / T18Emu** (`github.com/mameise/Paramix-Studio`) — ships no ROM; you supply your own dump.

### Flash layout (magic-green dump)

| Flash offset | Contents |
|---|---|
| `0x000000` | 8-byte header `"SPII"` + load addr `0x2000000c`, then the ARM vector table |
| `0x00000c`.. | **firmware code**, runs at RAM `0x20000000` |
| ~`0x1b0000` | item / save storage (TAMAGO blocks) |
| ~`0x4e9000` | built-in **item catalogue** (TAMAGO + `tg18_` IDs, like MyMeets' assets) |

### The key that unlocks disassembly

**RAM address `0x2000XXXX` = flash offset `0x0c + 0xXXXX`.** Verified: the reset vector at RAM `0x20000020` holds `0x20000048`, and the firmware functions disassemble as valid Thumb at the mapped offsets. So every firmware function our programs call (`0x200008ff`, `0x20000f47`, …) can now be read directly.

- `0x20000f47` is not a plain loader: it's a **dispatch function** (`bl helper; ldr r3,[table, r0*4]; mov pc,r3`). r0 selects a firmware service/resource. Reading that table enumerates what programs can reach — the real capability map.
- The firmware references the downloaded-program base `0x207F0000` at two code sites (near RAM `0x2012f040`, `0x2014c7a4`). Disassembling the code that uses those literals gives the **entry convention** for a downloaded location/game — the last missing piece before we can write our own program and verify it in the emulator.

### Honest status

- **Done:** firmware obtained, hardware identified, memory map cracked, functions now disassemblable.
- **Next:** (a) find the program loader → entry convention; (b) dump the `0x20000f47` service table → full capability list; (c) stand up T18Emu to run/verify a custom program before it ever touches the device.
- Only after (c) should any hand-written program be sent to a real Tama.

### Loader findings (magic-green dump)

- The firmware's **download verifier** is at RAM `0x2012efcc` and `0x2014c656` (Thumb). It confirms a downloaded program is placed at **`0x207F0000`**, reads the big-endian **code size at item offset `0xae`**, and runs the `0x207F0000..+size` range through several checks.
- `0x2012f68c` is a **call veneer** (`bx r3; bx r4; ...`), so the loader's "constants" (`0x2013fa15`, `0x201583fb`, `0x2001448c`, ...) are firmware functions called indirectly. Finding the final "enter the program" jump means following that indirect-call chain — better done in an emulator than by hand.
- **Practical takeaway:** reading firmware instructions by hand has hit diminishing returns. The next leap (entry convention, the `0x20000f47` service table, and writing a program we can verify) wants a **running emulator** (Paramix T18Emu) as the platform. That's a separate, larger setup task.


## 13. Emulator and a working cheat verifier (no device)

Found a finished emulator and built a verifier, both with no hardware.

### The emulator exists: nijiiro-egg

`github.com/oreo-fox/nijiiro-egg` is an open-source (MIT) Tamagotchi On/Meets emulator in Rust, with a Python/Unicorn prototype. It runs the real firmware from an 8 MB dump. Reading its code **independently confirmed all of section 11–12**: executes at `0x20000000`, reset PC `0x20000048`, SRAM at `0xF8000000`. It supports "ON Magic (EN)" (the owner's version). Setup guide: `docs/EMULATOR_SETUP.md`. It needs a PC (Windows now, Android planned).

### Firmware boots in a sandbox here

A minimal Unicorn harness (my own code) boots the magic-green dump: it runs from `0x20000048` into the `0x20013xxx` range and reaches the `0xF800xxxx` SRAM init. It then **stalls in a clock/PLL wait** on MMIO `0xD0000000` — expected, because a minimal harness doesn't emulate the chip peripherals. A *full* playable boot is what nijiiro-egg already does; reproducing it is not worth it.

### `tools/verify_cheat.py` — proving a cheat before sending it

The harness **is** enough to run a single item-program routine in isolation and check what it writes. `verify_cheat.py` loads a Magic-Hut-style file at `0x207F0000`, sets up a fake pet and the pet pointer at `0x200004D4`, stubs the item's region-detection, and runs the actual ARM cheat routines. Results (confirmed):

- Original Magic Hut: coins routine writes **99999** to pet `+0x20` (Gotchi Points); stats routine writes happiness **100** to `+0x11` and **6** to `+0x05`.
- Our Cheat Hut (site) patched to coins 12345 / happiness 77: writes **12345** and **77**. End-to-end match.

**This is the key safety tool:** any custom cheat we build can be run in the sandbox and checked against the intended writes *before* it goes to a real Tama. Needs `pip install unicorn capstone`.

### What this unlocks next (safe, doable here)

1. Extend `verify_cheat.py` into a general item-program runner (stub the ~10 firmware calls from section 11) so whole custom programs can be dry-run.
2. Write new cheat routines (set any variable, grow-up, etc.), verify them in the sandbox, then expose them in the site's Cheat Hut.
3. Only send to the device what the verifier has confirmed.
