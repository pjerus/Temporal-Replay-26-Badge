"""Phase 1 hardware demo, packaged as a callable screen.

Same behavior as the original /apps/scanner/main.py through Phase 1:
joystick + buttons move a cursor on the 8x8 LED matrix, CONFIRM cycles
brightness, IMU face-down dims output, BACK exits cleanly.
"""

import time

from badge_app import read_stick_4way, GCTicker

BRIGHTNESS_LEVELS = (80, 160, 40)
BRIGHTNESS_LABELS = ("med", "hi", "lo")
LOOP_MS = 80
JOY_COOLDOWN_MS = 120


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _render_oled(cx, cy, brt_label, jx, jy, tilt_x, tilt_y, face_down, imu_ok):
    oled_clear()
    ui_header("Scanner", "Demo")
    oled_set_cursor(0, 14)
    oled_print("Cur:" + str(cx) + "," + str(cy) + "  Brt:" + brt_label)
    oled_set_cursor(0, 26)
    oled_print("Joy:" + str(jx) + "/" + str(jy))
    if imu_ok:
        oled_set_cursor(0, 38)
        oled_print("Tilt " + str(int(tilt_x)) + "/" + str(int(tilt_y)))
        oled_set_cursor(0, 50)
        oled_print("Face:" + ("down" if face_down else "up  "))
    else:
        oled_set_cursor(0, 38)
        oled_print("IMU: not ready")
    oled_show()


def _render_matrix(cx, cy, brightness):
    led_clear()
    led_set_pixel(cx, cy, brightness)


def run():
    cursor_x = 3
    cursor_y = 3
    bright_index = 0
    last_joy_move = 0
    imu_ok = imu_ready()

    led_override_begin()
    led_clear()
    led_brightness(80)

    gc_ticker = GCTicker()

    try:
        while True:
            now = time.ticks_ms()

            if button_pressed(BTN_BACK):
                break

            if button_pressed(BTN_CONFIRM):
                bright_index = (bright_index + 1) % len(BRIGHTNESS_LEVELS)
                haptic_pulse(80, 20)

            brightness = BRIGHTNESS_LEVELS[bright_index]
            brt_label = BRIGHTNESS_LABELS[bright_index]

            face_down = imu_face_down() if imu_ok else False
            active_brightness = brightness // 4 if face_down else brightness

            if time.ticks_diff(now, last_joy_move) >= JOY_COOLDOWN_MS:
                jx_dir, jy_dir = read_stick_4way()
                if jx_dir != 0 or jy_dir != 0:
                    cursor_x = _clamp(cursor_x + jx_dir, 0, 7)
                    cursor_y = _clamp(cursor_y + jy_dir, 0, 7)
                    last_joy_move = now

            if button_pressed(BTN_UP):
                cursor_y = _clamp(cursor_y - 1, 0, 7)
            if button_pressed(BTN_DOWN):
                cursor_y = _clamp(cursor_y + 1, 0, 7)
            if button_pressed(BTN_LEFT):
                cursor_x = _clamp(cursor_x - 1, 0, 7)
            if button_pressed(BTN_RIGHT):
                cursor_x = _clamp(cursor_x + 1, 0, 7)

            jx = joy_x()
            jy = joy_y()
            tilt_x = imu_tilt_x() if imu_ok else 0
            tilt_y = imu_tilt_y() if imu_ok else 0

            _render_matrix(cursor_x, cursor_y, active_brightness)
            _render_oled(cursor_x, cursor_y, brt_label, jx, jy, tilt_x, tilt_y, face_down, imu_ok)

            gc_ticker.tick()
            time.sleep_ms(LOOP_MS)
    finally:
        led_clear()
        try:
            matrix_app_stop()
        except Exception:
            pass
        try:
            led_override_end()
        except Exception:
            pass
        oled_clear(True)
