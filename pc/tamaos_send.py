#!/usr/bin/env python3
"""TamaOS sender for PC: send a Tamagotchi On / Meets item file over Bluetooth LE.

Usage:
    pip install bleak
    python tamaos_send.py <item.txt> [--points N] [--delay MS] [--address MAC]
    python tamaos_send.py <item.txt> --dump out.bin      # build the message only, no Bluetooth

The message layout matches index.html (and the MyMeets capture): points go at
0xbb/0xbc, the command byte at 0x5e is 0x3a. The old copy that put points at
0x5e was wrong and made transfers fail at 100%.

Before sending: on the Tama pick Connection -> APP, press back, then
Connection -> Download. It must be daytime on the Tama's clock.
"""
import argparse
import asyncio
import struct
import sys
import time

SVC = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE = "0000fff2-0000-1000-8000-00805f9b34fb"   # to the Tama, write without response
NOTIFY = "0000fff1-0000-1000-8000-00805f9b34fb"  # from the Tama
NAME = "TMGC_meets"

SENDER_ID = bytes([0x7C, 0x68, 0x48, 0x97, 0x75, 0xA6, 0x4E, 0x99])
START, END, YOUR_TURN = b"\xf0\x8d", b"\xf0\xcd", b"\xf0\x8e\x0d"
CONTROL = {0x0C, 0x0D, 0x4D, 0x8D, 0xCD, 0x8E}
CMD_HELLO, CMD_ITEM, MAX_POINTS = 0x00, 0x3A, 99999


# ---------- message building (little-endian) ----------
def header(total_len, command, points, has_item):
    h = bytearray(0x100)
    h[0:6] = b"TAMAGO"
    struct.pack_into("<I", h, 0x48, total_len)
    h[0x4C] = 0x17
    h[0x52:0x5A] = SENDER_ID
    h[0x5E] = command
    if points > 0:
        h[0xBB] = 0x03
        struct.pack_into("<I", h, 0xBC, points)
    if has_item:
        struct.pack_into("<I", h, 0xD4, 256)
    h[0xFC:0x100] = b"\x10\x00\x01\x04"
    return h


def finish(body):
    return bytes(body) + struct.pack("<H", sum(body) & 0xFFFF)


def hello_msg():
    return finish(header(0x102, CMD_HELLO, 0, False))


def item_msg(item, points=0):
    tail = struct.pack("<III", 2, 1, len(item)) + bytes(item) + struct.pack("<I", 0)
    return finish(header(0x100 + len(tail) + 2, CMD_ITEM, points, True) + tail)


def item_info(item):
    """Return (file name, asset ID) or None if this isn't an item file."""
    if len(item) < 0x4A or item[:6] != b"TAMAGO":
        return None
    name = item[6:0x32].decode("utf-16-be", "replace").split("\x00")[0]
    asset = item[0x34:0x4A].split(b"\x00")[0].decode("ascii", "replace")
    return name, asset


def item_problems(item):
    """Checks that catch the usual mistakes. Items are big-endian."""
    out = []
    stored = struct.unpack_from(">H", item, len(item) - 2)[0]
    if sum(item[:-2]) & 0xFFFF != stored:
        out.append("item checksum (last 2 bytes) is wrong")
    if struct.unpack_from(">H", item, 0x4A)[0] != len(item):
        out.append("length at 0x4a doesn't match the file size")
    _, asset = item_info(item)
    num = struct.unpack_from(">H", item, 0x5A)[0]
    if str(num) not in asset:
        out.append(f"number at 0x5a ({num}) doesn't match the ID {asset}; the Tama will ignore it")
    return out


# ---------- Bluetooth link ----------
class Link:
    def __init__(self, client):
        self.client = client
        self.q = asyncio.Queue()

    async def start(self):
        await self.client.start_notify(NOTIFY, lambda _c, data: self.q.put_nowait(bytes(data)))
        await asyncio.sleep(0.3)

    async def w(self, data):
        await self.client.write_gatt_char(WRITE, data, response=False)

    async def next(self, timeout):
        p = await asyncio.wait_for(self.q.get(), timeout)
        print("RX", p.hex())
        return p

    async def send(self, msg, label, pace_ms, wait_ack=True):
        while not self.q.empty():
            self.q.get_nowait()
        print(f"TX start {label} ({len(msg)} bytes)")
        await asyncio.sleep(0.5 if not wait_ack else 0)   # WebMeets waits 500 ms first
        await self.w(START)
        await asyncio.sleep(0.06 if not wait_ack else 0.05)
        n = (len(msg) + 19) // 20
        deadline = time.perf_counter()
        for i in range(n):
            await self.w(msg[i * 20:(i + 1) * 20])
            deadline += pace_ms / 1000            # steady pace: writes queue up on Windows
            wait = deadline - time.perf_counter()
            if wait > 0:
                await asyncio.sleep(wait)
            if label == "item" and (i % 10 == 9 or i == n - 1):
                print(f"\r  {100 * (i + 1) // n}%", end="", flush=True)
        if label == "item":
            print()
        if not wait_ack:
            await asyncio.sleep(0.06)
        await self.w(END)
        if not wait_ack:
            return
        try:
            ack = await self.next(10 if label == "hello" else 45)
        except asyncio.TimeoutError:
            if label == "hello":
                sys.exit("The Tama connected but didn't answer the hello. It probably left the Download "
                         "screen or fell asleep. Wake it, do APP -> back -> Download again, and rerun.")
            sys.exit(f"The Tama didn't confirm the {label}. Try a bigger --delay.")
        if ack[:2] != b"\xf0\x0c":
            sys.exit(f"The Tama didn't accept the {label} (got {ack.hex()}).")

    async def reply(self):
        await self.w(YOUR_TURN)
        data = bytearray()
        while True:
            try:
                p = await self.next(30)
            except asyncio.TimeoutError:
                sys.exit("The Tama stopped answering before it finished its reply.")
            if len(p) <= 8 and p[0] == 0xF0 and p[1] in CONTROL:
                if p[1] == 0x4D:
                    break
                continue
            data += p
        try:
            while True:
                await self.next(0.4)
        except asyncio.TimeoutError:
            pass
        return data[0x5E] if len(data) > 0x5E and data[:6] == b"TAMAGO" else None


def is_program(item):
    """Locations (94024702) and games (94025b01) are programs the Tama has to
    write into flash after receiving them."""
    return len(item) > 0x52 and item[0x4E] == 0x94


async def run(item, points, pace, address, no_reply=False, quick=False):
    from bleak import BleakClient, BleakScanner

    fixed_address = address
    client = None
    for attempt in range(1, 5):
        target = fixed_address
        if not target:
            print(f"Looking for {NAME} (do APP -> back -> Download on the Tama)...")
            dev = await BleakScanner.find_device_by_name(NAME, timeout=20)
            if not dev:
                sys.exit(f"{NAME} not found. Is the Tama on the Download screen, and is it daytime on its clock?")
            target = dev  # connect to the fresh scan result, not a stale address
        print(f"Connecting to {getattr(target, 'address', target)} (try {attempt} of 4)")
        client = BleakClient(target, timeout=20)
        try:
            await client.connect()
            break
        except (asyncio.CancelledError, asyncio.TimeoutError, OSError, Exception) as e:
            print(f"  Windows couldn't finish connecting ({type(e).__name__}). Retrying in 2 s...")
            try:
                await client.disconnect()
            except Exception:
                pass
            client = None
            await asyncio.sleep(2)
    if client is None:
        sys.exit("Couldn't connect after 4 tries. Turn Windows Bluetooth off and on, put the Tama "
                 "back on the Download screen, and rerun.")
    async with client:
        link = Link(client)
        await link.start()
        await link.send(hello_msg(), "hello", pace)
        print("hello answered with command", await link.reply())
        if quick:
            # Exactly what WebMeets does: send, don't wait for the ack, wait 200 ms,
            # listen up to 0.5 s for "finished", then disconnect and leave the
            # Tama to process the item on its own.
            await link.send(item_msg(item, points), "item", pace, wait_ack=False)
            await asyncio.sleep(0.2)
            try:
                t0 = time.perf_counter()
                while time.perf_counter() - t0 < 0.5:
                    p = await link.next(0.5)
                    if p[:4] == b"\xf0\x0c\x00\x02":
                        break
            except asyncio.TimeoutError:
                pass
            print("Sent and disconnecting right away (exact WebMeets behaviour). Watch the Tama's bar.")
        else:
            await link.send(item_msg(item, points), "item", pace)
        if quick:
            pass
        elif no_reply:
            # WebMeets style: don't ask for a reply (the "your turn" can land while
            # the Tama is still writing a location/game to flash). Just listen for
            # a moment, then disconnect and let the Tama finish on its own.
            # The Tama's Bluetooth chip acks as soon as it has buffered the whole
            # message; the main CPU then copies it in and saves it (the bar on the
            # Tama). Disconnecting during that copy makes it fail, so stay
            # connected, quietly, until the Tama says it is finished (f00c 0002,
            # what WebMeets waits for) or drops the link itself.
            print("Sent. Staying connected while the Tama copies and saves it (watch its bar)...")
            t0 = time.perf_counter()
            while time.perf_counter() - t0 < 120:
                if not client.is_connected:
                    print("The Tama closed the connection.")
                    break
                try:
                    p = await link.next(5)
                except asyncio.TimeoutError:
                    print(f"  ...still waiting ({time.perf_counter() - t0:.0f}s)")
                    continue
                if p[:4] == b"\xf0\x0c\x00\x02":
                    print("The Tama says it's finished.")
                    await asyncio.sleep(1)
                    break
            else:
                print("No 'finished' signal after 2 minutes; check the Tama's screen.")
        else:
            cmd = await link.reply()
            print("item answered with command", cmd, "(accepted)" if cmd == CMD_ITEM + 1 else "")
    print("Done. Check your Tama." + (f" {points} Gotchi Points were included." if points else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("item", help="item file (.txt from MyMeets assets/items, or one from items/)")
    ap.add_argument("--points", type=int, default=0, help="Gotchi Points to add, 0 to 99,999")
    ap.add_argument("--delay", type=int, default=40, help="ms per 20-byte chunk (40-45 is safe)")
    ap.add_argument("--address", help="Bluetooth address, skips scanning")
    ap.add_argument("--dump", metavar="FILE", help="write the built message to FILE and stop")
    ap.add_argument("--webmeets", action="store_true",
                    help="exactly like WebMeets: 15 ms pace, don't wait for the ack, disconnect right after sending")
    ap.add_argument("--no-reply", action="store_true",
                    help="don't ask the Tama for a reply after the item (automatic for locations and games)")
    a = ap.parse_args()

    item = open(a.item, "rb").read()
    info = item_info(item)
    if not info:
        sys.exit(f"{a.item} isn't a Tamagotchi item (no TAMAGO header).")
    if not 0 <= a.points <= MAX_POINTS:
        sys.exit("--points must be 0 to 99,999.")
    print(f"Item: {info[1]} ({info[0]}), {len(item)} bytes, +{a.points} points")
    for p in item_problems(item):
        print("Warning:", p)
    if a.dump:
        open(a.dump, "wb").write(item_msg(item, a.points))
        print("Wrote", a.dump)
        return
    no_reply = a.no_reply or is_program(item)
    if is_program(item):
        print("This is a location/game: sending it WebMeets style (no reply request after the item).")
    if a.webmeets:
        print("WebMeets mode: 15 ms pace, disconnect right after sending.")
        asyncio.run(run(item, a.points, 15, a.address, True, quick=True))
        return
    asyncio.run(run(item, a.points, max(10, min(200, a.delay)), a.address, no_reply))


if __name__ == "__main__":
    main()
