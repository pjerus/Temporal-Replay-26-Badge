"""Drive the tank base over Bluetooth: pf_ble_drive.py [--status] [<left> <right> <ms> ...]

Speeds are -7..7 per tread (fractions allowed, to one decimal), positive forward.
Needs the badge on the echo-drive firmware and ROCKY_TREAD_SECRET set (8 characters).
Run with:  uv run --with bleak pf_ble_drive.py 4 4 1500
"""
import asyncio, os, struct, sys

NAME = "Rocky IR Tread"
WRITE_UUID = "98b99101-ab97-48b5-a9c9-e666e456806c"
STATE_UUID = "1350f2e6-4bdf-4459-a813-4afaf1a8ffee"
RESEND_S = 0.2
TTL_DS = 6            # each command is valid 0.6 s: three missed resends, then the badge stops


def build_cmd(secret: bytes, left: float, right: float, ttl_ds: int) -> bytes:
    if len(secret) != 8:
        raise ValueError("secret must be 8 bytes")
    lt, rt = round(left * 10), round(right * 10)
    if abs(lt) > 70 or abs(rt) > 70 or not 1 <= ttl_ds <= 10:
        raise ValueError("speed must be -7..7 and ttl 1..10")
    return secret + struct.pack("<bbB", lt, rt, ttl_ds)


def next_sleep(remaining_s: float) -> float:
    """How long to wait before the next resend without running past the step's end."""
    return max(0.0, min(RESEND_S, remaining_s))


def parse_state(b: bytes) -> dict:
    if len(b) != 8:
        raise ValueError("state must be 8 bytes")
    flags, lt, rt, left_ds, batt, free_q, min_q, accepted = struct.unpack("<BbbBBBBB", b)
    return {"driving": bool(flags & 1), "ir_ready": bool(flags & 2),
            "low_memory": bool(flags & 4), "rejected": bool(flags & 8),
            "left": lt / 10, "right": rt / 10, "left_s": left_ds / 10, "battery": batt,
            "free_kb": free_q / 4, "min_free_kb": min_q / 4, "accepted": accepted}


async def run(steps, status_only):
    from bleak import BleakClient, BleakScanner
    secret = os.environ.get("ROCKY_TREAD_SECRET", "").encode()
    if len(secret) != 8:
        raise SystemExit("ROCKY_TREAD_SECRET must be set to 8 characters")
    dev = await BleakScanner.find_device_by_name(NAME, timeout=10)
    if dev is None:
        raise SystemExit(f"no badge named {NAME!r} found")
    async with BleakClient(dev) as c:
        await asyncio.sleep(0.5)                       # let the badge bring IR up
        print("status", parse_state(bytes(await c.read_gatt_char(STATE_UUID))))
        if status_only:
            return
        try:
            for left, right, ms in steps:
                now = asyncio.get_running_loop().time
                end = now() + ms / 1000
                while now() < end:
                    await c.write_gatt_char(WRITE_UUID, build_cmd(secret, left, right, TTL_DS), response=True)
                    await asyncio.sleep(next_sleep(end - now()))
                if left or right:                      # end the step on time, not when the ttl runs out
                    await c.write_gatt_char(WRITE_UUID, build_cmd(secret, 0, 0, 1), response=True)
                print("did", left, right, ms)
        finally:
            await c.write_gatt_char(WRITE_UUID, build_cmd(secret, 0, 0, 1), response=True)
        await asyncio.sleep(0.5)
        print("status", parse_state(bytes(await c.read_gatt_char(STATE_UUID))))


def main(argv):
    status_only = "--status" in argv
    nums = [float(a) for a in argv if a != "--status"]
    if (not nums and not status_only) or len(nums) % 3:
        raise SystemExit(__doc__)
    steps = [(nums[i], nums[i + 1], int(nums[i + 2])) for i in range(0, len(nums), 3)]
    for left, right, _ in steps:
        build_cmd(b"00000000", left, right, TTL_DS)    # range check before connecting
    asyncio.run(run(steps, status_only))


if __name__ == "__main__":
    main(sys.argv[1:])