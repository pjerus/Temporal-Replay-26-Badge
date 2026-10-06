"""Drive the tank base from the Mac: pf_drive.py <left> <right> <ms> [<left> <right> <ms> ...]

Speeds are -7..7 per tread, positive forward, 0 coast. Examples:
  pf_drive.py 3 3 1000              slow forward for a second
  pf_drive.py 4 -4 600 0 0 300 -3 -3 800    spin right, pause, back up
"""
import pathlib, sys
from badge_exec import run

nums = [int(a) for a in sys.argv[1:]]
if not nums or len(nums) % 3 or any(abs(s) > 7 for i, s in enumerate(nums) if i % 3 < 2):
    raise SystemExit(__doc__)
steps = [tuple(nums[i:i + 3]) for i in range(0, len(nums), 3)]
script = (pathlib.Path(__file__).parent / 'ir_drive.py').read_text().replace('__STEPS__', repr(steps))
out, err = run(script, timeout=sum(s[2] for s in steps) / 1000 + 20)
print('\n'.join(l for l in out.splitlines() if l.startswith(('did', 'DONE'))))
if 'Traceback' in err: print(err)
