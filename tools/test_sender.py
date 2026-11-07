"""Offline test for tamaos_send.py: a fake Tama stands in for Bluetooth.

It reassembles every message the sender writes (between f0 8d and f0 cd),
answers the way the real Tama did in our logs, and checks that the item
message that arrived is byte-identical to what item_msg() builds.

Usage: py -3.15 tools/test_sender.py   (no Tama, no Bluetooth needed)
"""
import asyncio
import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START, END, YOUR_TURN = b"\xf0\x8d", b"\xf0\xcd", b"\xf0\x8e\x0d"


class FakeTama:
    def __init__(self):
        self.messages = []
        self.buf = None
        self.notify = None
        self.connected = True

    def push(self, data):
        loop = asyncio.get_event_loop()
        loop.call_soon(self.notify, None, bytearray(data))

    def write(self, data):
        data = bytes(data)
        if data == START:
            self.buf = bytearray()
        elif data == END:
            msg = bytes(self.buf)
            self.messages.append(msg)
            self.buf = None
            self.push(b"\xf0\x0c" + len(msg).to_bytes(2, "little") + b"\x12\x12\x12\x00")
            if len(self.messages) > 1:          # item: Tama says finished after saving
                self.push(b"\xf0\x0c\x00\x02\x00\x00\x12\x00")
        elif data == YOUR_TURN:
            reply = bytearray(b"TAMAGO" + bytes(0x100))
            reply[0x5E] = 1 if len(self.messages) == 1 else 0x3B
            self.push(b"\xf0\x0d\x00\x02")
            for i in range(0, len(reply), 20):
                self.push(reply[i:i + 20])
            self.push(b"\xf0\x4d")
            self.push(b"\xf0\x0c\x00\x02\x00\x00\x12\x00")
        elif self.buf is not None:
            self.buf += data


TAMA = None


class FakeClient:
    def __init__(self, address, **kw):
        self.is_connected = True

    fail_next = 0

    async def connect(self):
        if FakeClient.fail_next:
            FakeClient.fail_next -= 1
            raise asyncio.CancelledError()   # what Windows/bleak threw on the device

    async def disconnect(self):
        self.is_connected = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        self.is_connected = False

    async def start_notify(self, uuid, cb):
        TAMA.notify = cb

    async def write_gatt_char(self, uuid, data, response=False):
        TAMA.write(data)


class FakeScanner:
    @staticmethod
    async def find_device_by_name(name, timeout=0):
        return types.SimpleNamespace(address="FA:KE:TA:MA:00:00")


def load_sender():
    fake = types.ModuleType("bleak")
    fake.BleakClient, fake.BleakScanner = FakeClient, FakeScanner
    sys.modules["bleak"] = fake
    spec = importlib.util.spec_from_file_location("tamaos_send", os.path.join(ROOT, "tamaos_send.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def case(mod, label, path, points, **kw):
    global TAMA
    TAMA = FakeTama()
    item = open(os.path.join(ROOT, path), "rb").read()
    no_reply = mod.is_program(item)
    pace = kw.pop("pace", 1)
    asyncio.run(mod.run(item, points, pace, None, no_reply, **kw))
    want = mod.item_msg(item, points)
    ok = len(TAMA.messages) == 2 and TAMA.messages[0] == mod.hello_msg() and TAMA.messages[1] == want
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {len(TAMA.messages)} messages,"
          f" item {len(TAMA.messages[1]) if len(TAMA.messages) > 1 else 0} of {len(want)} bytes")
    return ok


def retry_case(mod):
    FakeClient.fail_next = 2   # first two connects fail like on the real PC
    return case(mod, "location after 2 failed connects (retry)", "items/tamaos_demo.txt", 0)


if __name__ == "__main__":
    mod = load_sender()
    results = [
        case(mod, "wallpaper, normal item", "items/wallpaper_bg50001.txt", 50),
        case(mod, "location (tamaos_demo), no-reply", "items/tamaos_demo.txt", 0),
        retry_case(mod),
        case(mod, "location, --webmeets mode", "items/tamaos_demo.txt", 0, quick=True),
    ]
    print("ALL PASS" if all(results) else "SOME FAILED")
    sys.exit(0 if all(results) else 1)
