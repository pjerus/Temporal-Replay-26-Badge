#include "../../src/drive/PfTreads.h"
#include <cassert>
#include <cstdio>
int main() {
  using namespace pftreads;
  const Tuning t{0, 109, true};
  // Reference values from the tuned scripts/pf_ir/ir_drive.py.
  assert(frameBits(0, 0, t) == 0x400B);    // coast both
  assert(frameBits(3, 3, t) == 0x43D5);    // forward: A=16-3, B flipped=3
  assert(frameBits(-4, 4, t) == 0x444B);   // spin left
  const Tuning ch2{1, 109, true};
  assert(frameBits(7, 7, ch2) == 0x5794);
  const Tuning noflip{0, 100, false};
  assert(frameBits(3, 3, noflip) == 0x4DDB);

  // encodePairs: start, 16 bits MSB first, stop
  uint16_t p[36];
  encodePairs(0x400B, p);
  assert(p[0] == 158 && p[1] == 1026);          // start
  assert(p[2] == 158 && p[3] == 263);           // bit15 = 0
  assert(p[4] == 158 && p[5] == 553);           // bit14 = 1
  assert(p[34] == 158 && p[35] == 1026);        // stop
  assert(p[33] == 553);                         // bit0 = 1

  // Dither: 4.0 with 109% trim averages 4.36 on the left, 4.0 on the right
  Dither d; d.reset();
  int sumL = 0, sumR = 0, l, r;
  for (int i = 0; i < 100; i++) { d.next(40, 40, t, l, r); sumL += l; sumR += r;
    assert(l == 4 || l == 5); assert(r == 4); }
  assert(sumL == 436 && sumR == 400);

  // negative speeds mirror
  d.reset(); sumL = 0;
  for (int i = 0; i < 100; i++) { d.next(-40, -40, t, l, r); sumL += l; assert(r == -4); }
  assert(sumL == -436);

  // trim_clamps_at_seven: 7.0 * 1.09 never exceeds 7
  d.reset();
  for (int i = 0; i < 50; i++) { d.next(70, 70, t, l, r); assert(l == 7 && r == 7); }

  // zero stays zero
  d.reset(); d.next(0, 0, t, l, r); assert(l == 0 && r == 0);
  std::puts("pf_treads ok");
}