"""Decode a capture made by ir_listen.py: pf_decode.py <capture.txt>"""
import binascii, struct, sys

def decode(pairs):
    bits = ''
    for mark, space in pairs:
        total = mark + space
        if space == 0 or total > 1700: bits += 'E'      # end of frame
        elif total < 566: bits += '0'                    # nominal 421 us
        elif total < 948: bits += '1'                    # nominal 711 us
        else: bits += 'S'                                # start/stop, nominal 1184 us
    return bits

for line in open(sys.argv[1]):
    if not line.startswith('F '):
        continue
    _, ms, hexed = line.split()
    raw = binascii.unhexlify(hexed)
    bits = decode([struct.unpack_from('<HH', raw, i) for i in range(0, len(raw), 4)])
    core, info = bits.strip('SE'), ''
    if len(core) == 16 and set(core) <= set('01'):
        n = [int(core[i:i + 4], 2) for i in range(0, 16, 4)]
        ok = (0xF ^ n[0] ^ n[1] ^ n[2]) == n[3]
        info = f'channel={(n[0] & 3) + 1} mode={n[1] & 7} data={n[2]:04b} checksum={"ok" if ok else "BAD"}'
    print(ms, bits, info)
