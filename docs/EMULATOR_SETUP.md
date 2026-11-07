# Running your Tama on a PC (emulator setup)

This is a simple guide to set up **nijiiro-egg**, a Tamagotchi On/Meets emulator, on a Windows PC. It lets your Tama live on the computer screen. It's also the workbench we'd use later to build and test custom programs safely.

You can't do this on a phone — it needs a Windows PC (an Android version is planned by the emulator's author, not out yet).

## What you'll need

1. A Windows PC (even borrowed, for 15 minutes).
2. The emulator (free, open-source).
3. A firmware file for your Tama version (an 8 MB `.bin`). See the firmware note below.

## Steps

1. On the PC, open **https://github.com/oreo-fox/nijiiro-egg/releases** and download the newest release zip (a file like `nijiiro-egg-win.zip`).
2. Unzip it somewhere easy, like the Desktop. You'll get a folder with `nijiiro-egg.exe` and empty `roms` and `saves` folders.
3. Put your firmware `.bin` file into the **`roms`** folder.
4. Double-click **`nijiiro-egg.exe`**. Then use **File → Open ROM** and pick your firmware.
5. Your Tama boots up. Use the on-screen or keyboard buttons to play. It saves automatically.

### If Windows warns you

- **"Windows protected your PC" (SmartScreen):** click **More info → Run anyway**. It happens because the app isn't from a big company, not because it's unsafe.
- **Microsoft Defender flags it (Trojan:Win32/Wacatac):** this is a known **false positive** the author is getting fixed. In Windows Security → Virus & threat protection → Protection history, **Restore** the file, then add the folder under Exclusions. Only do this if you're comfortable; it's the author's own note in their README.

## The firmware (ROM) — honest notes

The emulator ships with **no firmware** — that part is Bandai's, and you supply it. Your Tama is the "ON Magic (EN)" version, which the emulator supports.

- **The clean way** is to dump the firmware off your own Tama. That needs soldering to the board and a flash reader, so it's a hardware project — not something you can do without tools.
- **The firmware also exists publicly** in a community reverse-engineering repo, `github.com/kaero/t-on` (in its `dumps` folder, 8 MB `.bin` files). It's there for research. It is Bandai's copyrighted code, so downloading it is a grey area — the honest, clean route is your own dump. You own the toy, which is why this is a reasonable thing for personal use, but I'm telling you straight so you can decide.
- Do **not** put the firmware file into this TamaSend repo (it's public — that would be sharing Bandai's code). Keep it on the PC only.

## What this does and doesn't give you

- **Does:** run and play your Tama on a PC; a safe place to experiment.
- **Doesn't (yet):** make custom cheats/programs by itself. That's a separate development project that uses the emulator as a test bench. Getting there needs steady PC access and more work.

## Limitations (from the emulator)

- Windows only for now (Android planned).
- No Bluetooth/infrared yet, so no connecting to the phone app or the site — only built-in (NPC) marriage.
- The pet doesn't age while the app is closed (like taking the batteries out).
