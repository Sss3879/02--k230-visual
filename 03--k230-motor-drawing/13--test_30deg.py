"""
============================================================
  30度大幅度测试 —— 简单直接
  短按 → 水平右移30度
  长按 → 垂直下移30度
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

# 电机参数
STEP_ANGLE = 1.8       # 步距角
MICROSTEP = 16         # 细分
PULSE_PER_ROUND = 360.0 / STEP_ANGLE * MICROSTEP  # = 3200

def deg_to_steps(angle_deg):
    """角度转步数"""
    return int(angle_deg / 360.0 * PULSE_PER_ROUND)

# 30度对应的步数
ANGLE_DEG = 30
STEPS = deg_to_steps(ANGLE_DEG)  # ≈ 267步
DELAY_US = 800

print("30度 = {} 步".format(STEPS))

try:
    print("=== 30度大幅度测试 ===")
    print("短按=水平右移30度  长按=垂直下移30度")

    # ---- 摄像头 ----
    sensor = Sensor()
    sensor.reset()
    sensor.set_framesize(width=640, height=480)
    sensor.set_pixformat(Sensor.RGB565)
    Display.init(Display.ST7701, to_ide=True)
    MediaManager.init()
    sensor.run()

    clock = time.clock()

    # ---- 外设 ----
    key = YbKey()
    uart = YbUart(baudrate=115200)
    print("UART 初始化完成")

    key_hold_frames = 0
    last_msg = "等待按键..."
    send_count = 0

    while True:
        clock.tick()
        os.exitpoint()

        img = sensor.snapshot(chn=CAM_CHN_ID_0)

        # ---- 按键 ----
        if key.is_pressed() == 1:
            key_hold_frames += 1
        else:
            if key_hold_frames > 0:
                send_count += 1

                if key_hold_frames < 30:
                    # 短按: 水平移动 (Yaw)
                    cmd = "R,{},{},{}\n".format(STEPS, 0, DELAY_US)
                    tag = "水平右移{}度 ({}步)".format(ANGLE_DEG, STEPS)
                else:
                    # 长按: 垂直移动 (Pitch)
                    cmd = "R,{},{},{}\n".format(0, STEPS, DELAY_US)
                    tag = "垂直下移{}度 ({}步)".format(ANGLE_DEG, STEPS)

                print(">>> [{}] 发送: {}".format(send_count, cmd.strip()))
                uart.send(cmd)
                last_msg = tag

            key_hold_frames = 0

        # ---- 接收 ----
        data = uart.read()
        if data is not None:
            try:
                if isinstance(data, bytes):
                    msg = data.decode().strip()
                else:
                    msg = str(data).strip()
            except:
                msg = repr(data)
            if msg:
                print("[STM32] {}".format(msg))
                last_msg = "[回] {}".format(msg[:50])

        # ---- 显示 ----
        img.draw_string_advanced(5, 3, 22,
            "30 DEG TEST", color=(0, 255, 255))
        img.draw_string_advanced(5, 30, 18,
            "Angle: {} deg = {} steps".format(ANGLE_DEG, STEPS), color=(0, 255, 0))
        img.draw_string_advanced(5, 52, 18,
            "Yaw: R,{},0,{}".format(STEPS, DELAY_US), color=(255, 255, 0))
        img.draw_string_advanced(5, 72, 18,
            "Pitch: R,0,{},{}".format(STEPS, DELAY_US), color=(255, 255, 0))
        img.draw_string_advanced(5, 98, 18,
            "Msg: {}".format(last_msg[:45]), color=(255, 200, 100))
        img.draw_string_advanced(5, 122, 16,
            "[短按]Yaw  [长按]Pitch", color=(180, 180, 180))
        img.draw_string_advanced(5, 145, 18,
            "Cmd sent: {}".format(send_count), color=(200, 200, 200))
        img.draw_string_advanced(5, 170, 20,
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
