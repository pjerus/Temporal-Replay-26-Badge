"""Run a Python script on the badge over its USB raw REPL and print what it prints."""
import glob, sys, time
import serial

def run(script, timeout=30.0):
    port = glob.glob('/dev/cu.usbmodem*')[0]
    s = serial.Serial(port, 115200, timeout=0.1)
    def rd(t):
        b = b''; t0 = time.time()
        while time.time() - t0 < t: b += s.read(65536)
        return b
    rd(1.2)                      # the firmware ignores input for 350 ms after a connect
    s.write(b'\r\x03\x03'); rd(0.4)
    s.write(b'\r\x01')
    if b'raw REPL' not in rd(1.0):
        s.close(); raise SystemExit('no raw REPL (is an app running on the badge?)')
    s.write(script.encode() + b'\x04')
    out = b''; t0 = time.time()
    while time.time() - t0 < timeout:
        out += s.read(65536)
        if out.count(b'\x04') >= 2: break
    s.write(b'\x02'); s.close()
    body = out[2:] if out.startswith(b'OK') else out
    stdout, _, err = body.partition(b'\x04')
    return stdout.decode('utf-8', 'replace'), err.rstrip(b'\x04>').decode('utf-8', 'replace')

if __name__ == '__main__':
    o, e = run(open(sys.argv[1]).read(), float(sys.argv[2]) if len(sys.argv) > 2 else 30.0)
    print(o, end='')
    if e.strip(): print('--- badge error ---\n' + e)
