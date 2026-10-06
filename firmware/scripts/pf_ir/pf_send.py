"""Send a LEGO Power Functions command from the badge: pf_send.py <data 0-15> [milliseconds]

data is BBAA in binary, two bits per receiver output: 00 coast, 01 one way, 10 the other way, 11 brake.
Example: pf_send.py 5 1500   -> both outputs one way for 1.5 s, then coast.
"""
import pathlib, sys
from badge_exec import run

data = int(sys.argv[1], 0)
ms = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
script = (pathlib.Path(__file__).parent / 'ir_send_pf.py').read_text()
out, err = run(script.replace('__DATA__', str(data)).replace('__RUN_MS__', str(ms)), timeout=ms / 1000 + 20)
print(out, end='')
