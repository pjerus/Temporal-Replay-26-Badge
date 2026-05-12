#include "BleScan.h"

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <esp_heap_caps.h>
#include <freertos/FreeRTOS.h>
#include <freertos/portmacro.h>
#include <string.h>

namespace {

constexpr int kMaxEntries = 32;
constexpr uint8_t kAdTypeNameShort = 0x08;
constexpr uint8_t kAdTypeNameComplete = 0x09;

struct Entry {
    bool     used;
    int      addr_type;
    uint8_t  addr[6];
    int8_t   rssi;
    uint32_t last_seen_ms;
    char     name[28];   // truncated UTF-8 BLE local names; NUL-terminated
};

portMUX_TYPE   s_mux         = portMUX_INITIALIZER_UNLOCKED;
Entry          s_table[kMaxEntries] = {};
volatile bool  s_initialised = false;
volatile bool  s_scanArmed   = false;
BLEScan       *s_scan        = nullptr;

// Find the slot for this address, or the slot to evict if the table is
// full. Returns the index. MUST be called inside the critical section.
int findOrEvictSlot(const uint8_t addr[6]) {
    int free_slot = -1;
    int oldest_slot = 0;
    uint32_t oldest_ts = 0xFFFFFFFFu;
    for (int i = 0; i < kMaxEntries; ++i) {
        if (s_table[i].used && memcmp(s_table[i].addr, addr, 6) == 0) {
            return i;
        }
        if (!s_table[i].used && free_slot < 0) {
            free_slot = i;
        }
        if (s_table[i].used && s_table[i].last_seen_ms < oldest_ts) {
            oldest_ts = s_table[i].last_seen_ms;
            oldest_slot = i;
        }
    }
    return (free_slot >= 0) ? free_slot : oldest_slot;
}

bool extractName(const uint8_t *adv, size_t adv_len, char *out, size_t out_len) {
    if (out_len == 0) return false;
    out[0] = '\0';
    size_t i = 0;
    while (i + 1 < adv_len) {
        const uint8_t field_len = adv[i];
        if (field_len == 0) break;
        if (i + field_len >= adv_len) break;
        const uint8_t ad_type = adv[i + 1];
        if (ad_type == kAdTypeNameShort || ad_type == kAdTypeNameComplete) {
            const size_t name_len = field_len - 1;
            const size_t n = (name_len < out_len - 1) ? name_len : (out_len - 1);
            memcpy(out, adv + i + 2, n);
            out[n] = '\0';
            return true;
        }
        i += 1 + field_len;
    }
    return false;
}

class ScanCallback : public BLEAdvertisedDeviceCallbacks {
    void onResult(BLEAdvertisedDevice dev) override {
        const uint8_t *raw = dev.getAddress().getNative();
        if (!raw) return;

        // Best-effort name extract from the raw payload (NimBLE scan results
        // don't always populate dev.getName() reliably for every adv).
        char name_buf[28] = {0};
        const uint8_t *payload = dev.getPayload();
        const size_t payload_len = dev.getPayloadLength();
        if (payload && payload_len > 0) {
            extractName(payload, payload_len, name_buf, sizeof(name_buf));
        }

        const int8_t rssi = (int8_t)dev.getRSSI();
        const int addr_type = (int)dev.getAddressType();
        const uint32_t now_ms = (uint32_t)millis();

        portENTER_CRITICAL(&s_mux);
        const int slot = findOrEvictSlot(raw);
        Entry &e = s_table[slot];
        memcpy(e.addr, raw, 6);
        e.addr_type = addr_type;
        e.rssi = rssi;
        e.last_seen_ms = now_ms;
        // Keep the better name: only overwrite the stored name if the new
        // sample carries one. Some advs are name-less (scan-response carries
        // it), so don't blow away a previously captured name.
        if (name_buf[0] != '\0') {
            strncpy(e.name, name_buf, sizeof(e.name) - 1);
            e.name[sizeof(e.name) - 1] = '\0';
        }
        e.used = true;
        portEXIT_CRITICAL(&s_mux);
    }
};

bool ensureInitialised() {
    if (s_initialised) return true;

    Serial.printf("[blescan] init  largest=%u free=%u\n",
                  (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL),
                  (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL));

    if (!BLEDevice::init(String("PocketScanner"))) {
        Serial.println("[blescan] BLEDevice::init failed");
        return false;
    }
    s_scan = BLEDevice::getScan();
    if (!s_scan) {
        Serial.println("[blescan] getScan returned null");
        return false;
    }
    // wantDuplicates=true so RSSI updates on every packet, not once per
    // device — needed to keep the live list responsive.
    s_scan->setAdvertisedDeviceCallbacks(new ScanCallback(), true, false);
    s_scan->setActiveScan(true);   // request scan responses (for names)
    s_scan->setInterval(160);      // 100 ms
    s_scan->setWindow(150);        // 93.75 ms — near-continuous listen

    s_initialised = true;
    Serial.println("[blescan] init OK");
    return true;
}

}  // namespace

namespace BleScan {

bool start() {
    if (!ensureInitialised()) return false;
    if (s_scanArmed) return true;
    // duration=0 → continuous scan until stop().
    s_scan->start(0, nullptr, false);
    s_scanArmed = true;
    return true;
}

void stop() {
    if (!s_initialised || !s_scan) {
        s_scanArmed = false;
        return;
    }
    if (s_scanArmed) {
        s_scan->stop();
        // clearResults() drops the BLEScan-internal duplicate vector that
        // grows unbounded with wantDuplicates=true. Without this, a long
        // session starves the heap.
        s_scan->clearResults();
        s_scanArmed = false;
    }
}

bool isScanning() {
    return s_scanArmed;
}

int count() {
    int n = 0;
    portENTER_CRITICAL(&s_mux);
    for (int i = 0; i < kMaxEntries; ++i) {
        if (s_table[i].used) n++;
    }
    portEXIT_CRITICAL(&s_mux);
    return n;
}

bool getEntry(int idx,
              uint8_t addr_out[6],
              int *addr_type_out,
              int *rssi_out,
              uint32_t *last_seen_ms_out,
              char *name_out,
              size_t name_buf_len) {
    if (idx < 0) return false;
    portENTER_CRITICAL(&s_mux);
    int seen = 0;
    for (int i = 0; i < kMaxEntries; ++i) {
        if (!s_table[i].used) continue;
        if (seen == idx) {
            const Entry &e = s_table[i];
            memcpy(addr_out, e.addr, 6);
            if (addr_type_out)    *addr_type_out = e.addr_type;
            if (rssi_out)         *rssi_out = e.rssi;
            if (last_seen_ms_out) *last_seen_ms_out = e.last_seen_ms;
            if (name_out && name_buf_len > 0) {
                const size_t n = (strlen(e.name) < name_buf_len - 1)
                                 ? strlen(e.name) : (name_buf_len - 1);
                memcpy(name_out, e.name, n);
                name_out[n] = '\0';
            }
            portEXIT_CRITICAL(&s_mux);
            return true;
        }
        seen++;
    }
    portEXIT_CRITICAL(&s_mux);
    return false;
}

int prune(uint32_t stale_ms) {
    int removed = 0;
    const uint32_t now_ms = (uint32_t)millis();
    portENTER_CRITICAL(&s_mux);
    for (int i = 0; i < kMaxEntries; ++i) {
        if (!s_table[i].used) continue;
        if ((now_ms - s_table[i].last_seen_ms) > stale_ms) {
            s_table[i].used = false;
            removed++;
        }
    }
    portEXIT_CRITICAL(&s_mux);
    return removed;
}

}  // namespace BleScan
