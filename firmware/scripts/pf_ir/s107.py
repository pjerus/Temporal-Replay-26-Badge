"""Send Syma S107G helicopter commands from the Mac: s107.py [--b] <yaw> <pitch> <throttle> <ms> [...]

yaw and pitch are 0..127 with 63 centred; throttle is 0..127. --b selects the remote's channel B.
  s107.py 63 63 40 3000       low throttle for three seconds
"""
import pathlib, sys
from badge_exec import run

chan_b = '--b' in sys.argv
nums = [int(a) for a in sys.argv[1:] if a != '--b']
if not nums or len(nums) % 4 or any(not 0 <= v <= 127 for i, v in enumerate(nums) if i % 4 < 3):
    raise SystemExit(__doc__)
steps = [tuple(nums[i:i + 4]) for i in range(0, len(nums), 4)]
script = (pathlib.Path(__file__).parent / 's107_send.py').read_text()
script = script.replace('__STEPS__', repr(steps)).replace('__CHANNEL_B__', repr(chan_b))
out, err = run(script, timeout=sum(s[3] for s in steps) / 1000 + 20)
print('\n'.join(l for l in out.splitlines() if l.startswith(('did', 'DONE'))))
if 'Traceback' in err: print(err)
