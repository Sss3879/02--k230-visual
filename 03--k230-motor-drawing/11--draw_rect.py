"""
============================================================
  激光画矩形 v2 —— 摄像头预览 + 按键画矩形

  短按 (<1s) → 画小矩形
  长按 (>=1s) → 画大矩形

  如果画不出来，先用 12--debug_motor.py 逐步排查！
============================================================
"""
import time
import os
import sys

from media.sensor import *
from media.display import *
from media.media import *

from ybUtils.YbKey import YbKey
from ybUtils.YbUart import YbUart

sensor = None

# ============================================================
#  可调参数 —— 先从小步开始测试！
#  电机：1.8°步距角，16细分 → 3200脉冲/圈 ≈ 0.1125°/步
#  44步 ≈ 5°   89步 ≈ 10°   178步 ≈ 20°
# ============================================================
SMALL_RECT_W = 44    # 小矩形宽度 (~5°)
SMALL_RECT_H = 33    # 小矩形高度 (~3.7°)
BIG_RECT_W   = 89    # 大矩形宽度 (~10°)
BIG_RECT_H   = 67    # 大矩形高度 (~7.5°)
RECT_DELAY   = 800   # 步间延时 (微秒)，越小越快


def safe_str(data):
    """安全地将收到的数据转成字符串"""
    try:
        if isinstance(data, bytes):
            return data.decode().strip()
        elif isinstance(data, str):
            return data.strip()
        else:
            return str(data)
    except:
        return repr(data)


try:
    print("========================================")
    print("  激光画矩形 v2")
    print("  小矩形: {}x{} 步 (~{:.1f}x{:.1f}度)".format(
        SMALL_RECT_W, SMALL_RECT_H,
        SMALL_RECT_W * 0.1125, SMALL_RECT_H * 0.1125))
    print("  大矩形: {}x{} 步 (~{:.1f}x{:.1f}度)".format(
        BIG_RECT_W, BIG_RECT_H,
        BIG_RECT_W * 0.1125, BIG_RECT_H * 0.1125))
    print("  短按=小矩形  长按=大矩形")
    print("========================================")

    # ---- 摄像头初始化 ----
    sensor = Sensor()
    sensor.reset()
    sensor.set_framesize(width=640, height=480)
    sensor.set_pixformat(Sensor.RGB565)
    Display.init(Display.ST7701, to_ide=True)
    MediaManager.init()
    sensor.run()

    clock = time.clock()

    # ---- 外设初始化 ----
    key = YbKey()
    uart = YbUart(baudrate=115200)

    key_hold_frames = 0
    last_feedback = ""
    draw_status = "等待按键..."

    while True:
        clock.tick()
        os.exitpoint()

        img = sensor.snapshot(chn=CAM_CHN_ID_0)

        # ---- 按键检测（短按小矩形，长按大矩形） ----
        if key.is_pressed() == 1:
            key_hold_frames += 1
        else:
            if key_hold_frames > 0:
                if key_hold_frames < 30:
                    w, h = SMALL_RECT_W, SMALL_RECT_H
                    tag = "小"
                else:
                    w, h = BIG_RECT_W, BIG_RECT_H
                    tag = "大"

                cmd = "R,{},{},{}\n".format(w, h, RECT_DELAY)
                print(">>> 画{}矩形: {}x{}步, 延时{}us".format(tag, w, h, RECT_DELAY))
                try:
                    uart.send(cmd)
                    draw_status = "画{}矩形 {}x{}步".format(tag, w, h)
                except Exception as e:
                    print("!!! UART发送失败: {}".format(e))
                    draw_status = "发送失败!"

            key_hold_frames = 0

        # ---- 接收 STM32 反馈 ----
        data = uart.read()
        if data is not None:
            msg = safe_str(data)
            if msg:
                print("[STM32] {}".format(msg))
                last_feedback = msg
                if "Done" in msg:
                    draw_status = "矩形完成!"
                elif "Draw Rect" in msg:
                    draw_status = "STM32 正在画..."

        # ---- 画面显示 ----
        img.draw_string_advanced(5, 3, 22,
            "LASER DRAW RECT v2", color=(0, 255, 255))

        img.draw_string_advanced(5, 32, 16,
            "Small: {}x{} st  Big: {}x{} st".format(
                SMALL_RECT_W, SMALL_RECT_H, BIG_RECT_W, BIG_RECT_H),
            color=(0, 255, 0))

        img.draw_string_advanced(5, 55, 17,
            "Status: {}".format(draw_status), color=(255, 255, 0))

        if last_feedback:
            img.draw_string_advanced(5, 80, 15,
                "STM32: {}".format(last_feedback[:55]), color=(255, 160, 0))

        img.draw_string_advanced(5, 108, 15,
            "[短按]小矩形  [长按]大矩形", color=(180, 180, 180))

        # 按键进度条
        if key_hold_frames > 0:
            bar = "=" * min(key_hold_frames // 2, 15)
            tag = " SHORT" if key_hold_frames < 30 else " LONG"
            img.draw_string_advanced(5, 130, 15,
                "Hold:{}{}".format(bar, tag), color=(255, 128, 128))

        img.draw_string_advanced(5, 155, 18,
            "fps: {:.0f}".format(clock.fps()), color=(255, 0, 0))

        Display.show_image(img)

except KeyboardInterrupt as e:
    print("用户停止: ", e)
except BaseException as e:
    print(f"异常: {e}")
finally:
    if isinstance(sensor, Sensor):
        sensor.stop()
    Display.deinit()
    os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
    time.sleep_ms(100)
    MediaManager.deinit()
