#include <Arduino.h>
#include <stdint.h>
#include <string.h>

#include "../../ble/BleScan.h"

#include "temporalbadge_runtime.h"

extern "C" int temporalbadge_runtime_ble_scan_start(void) {
    return BleScan::start() ? 0 : -1;
}

extern "C" void temporalbadge_runtime_ble_scan_stop(void) {
    BleScan::stop();
}

extern "C" int temporalbadge_runtime_ble_scan_count(void) {
    return BleScan::count();
}

extern "C" int temporalbadge_runtime_ble_scan_prune(uint32_t stale_ms) {
    return BleScan::prune(stale_ms);
}

// Returns 0 on success, -1 if idx is out of range.
// Output buffer layout:
//   addr_out: 6 bytes (BD_ADDR, big-endian)
//   addr_type_out: 0 = public, 1 = random, others reserved (Arduino BLE enum)
//   rssi_out: signed dBm
//   age_ms_out: ms since last advertisement seen
//   name_out: NUL-terminated UTF-8, truncated to name_buf_len-1 bytes
extern "C" int temporalbadge_runtime_ble_scan_get(int idx,
                                                   uint8_t addr_out[6],
                                                   int *addr_type_out,
                                                   int *rssi_out,
                                                   uint32_t *age_ms_out,
                                                   char *name_out,
                                                   size_t name_buf_len) {
    uint32_t last_seen_ms = 0;
    bool ok = BleScan::getEntry(idx, addr_out, addr_type_out, rssi_out,
                                &last_seen_ms, name_out, name_buf_len);
    if (!ok) return -1;
    if (age_ms_out) {
        const uint32_t now_ms = (uint32_t)millis();
        *age_ms_out = now_ms - last_seen_ms;
    }
    return 0;
}
