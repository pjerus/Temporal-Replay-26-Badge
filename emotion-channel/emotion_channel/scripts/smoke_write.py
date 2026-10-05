"""Drive the badge emotion service directly over BLE, for bring-up.

    python -m emotion_channel.scripts.smoke_write [--name TemporalBadge]
        [--address AA:BB:..] [--mood scared] [--intensity 1.0] [--ttl-ms 8000]

Prints the state characteristic before and after the write.
"""
import argparse
import asyncio

from bleak import BleakScanner

from .. import config
from ..backends import BleBackend
from ..client import EmotionClient


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", help="skip the scan and connect to this address")
    ap.add_argument("--name", default="TemporalBadge")
    ap.add_argument("--mood", default="scared")
    ap.add_argument("--intensity", type=float, default=1.0)
    ap.add_argument("--ttl-ms", type=int, default=8000)
    args = ap.parse_args()

    address = args.address
    if not address:
        print(f"scanning for {args.name!r} (up to 12s)...")
        dev = await BleakScanner.find_device_by_name(args.name, timeout=12.0)
        if not dev:
            print("badge not found — is it on, and showing a screen past boot?")
            return
        address = dev.address
        print(f"found {address}")

    client = EmotionClient(BleBackend(address, config.badge_secret()))
    print("state before:", await client.state())
    print(f"injecting {args.mood} @ {args.intensity} for {args.ttl_ms} ms ...")
    print("state after: ", await client.inject(args.mood, args.intensity, args.ttl_ms))


if __name__ == "__main__":
    asyncio.run(main())
