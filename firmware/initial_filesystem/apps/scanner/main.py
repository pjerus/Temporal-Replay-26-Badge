"""
/apps/scanner/main.py — Phase 1 hardware demo.

Exercises every I/O channel:
  Joystick      → moves cursor on 8x8 LED matrix
  UP/DOWN/LEFT/RIGHT buttons → also move cursor
  CONFIRM       → cycle color (brightness level)
  IMU tilt/face → shown on OLED; face-down dims LEDs
  BACK          → clean exit

Cursor is a single lit pixel on the 8x8 IS31FL3731 matrix.
OLED shows live joystick XY, cursor pos, IMU tilt, and face state.
"""

__title__ = "Scanner"
__description__ = "Phase 1 hardware demo"
__order__ = 0

import time
import gc

from badge_app import read_stick_4way, GCTicker

# --- demo state ---
cursor_x = 3
cursor_y = 3
bright_index = 0

BRIGHTNESS_LEVELS = (80, 160, 40)
BRIGHTNESS_LABELS = ("med", "hi", "lo")

LOOP_MS = 80          # main loop interval ~12 fps
JOY_COOLDOWN_MS = 120 # min ms between joystick-driven moves

last_joy_move = 0

def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)

def render_oled(cx, cy, brt_label, jx, jy, tilt_x, tilt_y, face_down, imu_ok):
    oled_clear()
    # header
    ui_header("Scanner", "Phase 1")

    # cursor position
    oled_set_cursor(0, 14)
    oled_print("Cur:" + str(cx) + "," + str(cy) + "  Brt:" + brt_label)

    # joystick raw
    oled_set_cursor(0, 26)
    oled_print("Joy:" + str(jx) + "/" + str(jy))

    # IMU
    if imu_ok:
        oled_set_cursor(0, 38)
        oled_print("Tilt " + str(int(tilt_x)) + "/" + str(int(tilt_y)))
        oled_set_cursor(0, 50)
        oled_print("Face:" + ("down" if face_down else "up  "))
    else:
        oled_set_cursor(0, 38)
        oled_print("IMU: not ready")

    oled_show()

def render_matrix(cx, cy, brightness):
    led_clear()
    led_set_pixel(cx, cy, brightness)

def cleanup():
    led_clear()
    matrix_app_stop()
    led_override_end()
    oled_clear(True)

# --- entry point ---
imu_ok = imu_ready()

led_override_begin()
led_clear()
led_brightness(80)

gc_ticker = GCTicker()

while True:
    now = time.ticks_ms()

    # --- exit ---
    if button_pressed(BTN_BACK):
        break

    # --- brightness cycle on CONFIRM ---
    if button_pressed(BTN_CONFIRM):
        bright_index = (bright_index + 1) % len(BRIGHTNESS_LEVELS)
        haptic_pulse(80, 20)

    brightness = BRIGHTNESS_LEVELS[bright_index]
    brt_label  = BRIGHTNESS_LABELS[bright_index]

    # --- face-down dims matrix ---
    face_down = imu_face_down() if imu_ok else False
    active_brightness = brightness // 4 if face_down else brightness

    # --- joystick move (with cooldown) ---
    if time.ticks_diff(now, last_joy_move) >= JOY_COOLDOWN_MS:
        jx_dir, jy_dir = read_stick_4way()
        if jx_dir != 0 or jy_dir != 0:
            cursor_x = clamp(cursor_x + jx_dir, 0, 7)
            cursor_y = clamp(cursor_y + jy_dir, 0, 7)
            last_joy_move = now

    # --- button moves (edge-triggered, no cooldown needed) ---
    if button_pressed(BTN_UP):
        cursor_y = clamp(cursor_y - 1, 0, 7)
    if button_pressed(BTN_DOWN):
        cursor_y = clamp(cursor_y + 1, 0, 7)
    if button_pressed(BTN_LEFT):
        cursor_x = clamp(cursor_x - 1, 0, 7)
    if button_pressed(BTN_RIGHT):
        cursor_x = clamp(cursor_x + 1, 0, 7)

    # --- read sensors for display ---
    jx = joy_x()
    jy = joy_y()
    tilt_x = imu_tilt_x() if imu_ok else 0
    tilt_y = imu_tilt_y() if imu_ok else 0

    # --- render ---
    render_matrix(cursor_x, cursor_y, active_brightness)
    render_oled(cursor_x, cursor_y, brt_label, jx, jy, tilt_x, tilt_y, face_down, imu_ok)

    gc_ticker.tick()
    time.sleep_ms(LOOP_MS)

cleanup()
exit()
