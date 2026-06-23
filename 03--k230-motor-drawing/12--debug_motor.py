"""
============================================================
  电机调试工具 —— 逐步排查激光画矩形问题

  短按 (<1s) → 执行当前测试步骤
  长按 (>=1s) → 跳过当前步骤

  测试从易到难：UART通信 → 单轴微动 → 小矩形 → 大矩形
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
#  测试步骤（从小到大逐步验证）
#  格式: (名称, 发送命令, 等待ms, 说明)
# ============================================================
TEST_STEPS = [
    # 第1步: 测试UART（发送0,0，应该收到STM32回复"x:0 y:0"）
    ("1.UART测试",      "0,0\n",          500,  "应该看到STM32回复x:0 y:0"),

    # 第2步: Yaw +10步（水平微动）
    ("2.Yaw +10步",     "R,10,0,800\n",   1200, "激光应该向右微动"),

    # 第3步: Yaw -10步（回原位）
    ("3.Yaw -10步",     "R,-10,0,800\n",  1200, "激光应该向左回到原位"),

    # 第4步: Pitch +10步（垂直微动）
    ("4.Pitch +10步",   "R,0,10,800\n",   1200, "激光应该向下微动"),

    # 第5步: Pitch -10步（回原位）
    ("5.Pitch -10步",   "R,0,-10,800\n",  1200, "激光应该向上回到原位"),

    # 第6步: 小矩形 20x15步
    ("6.小矩形20x15",   "R,20,15,800\n",  2500, "激光画小矩形"),

    # 第7步: 中矩形 44x33步 (~5x3.7度)
    ("7.中矩形44x33",   "R,44,33,800\n",  4000, "激光画中矩形"),

    # 第8步: 标准矩形 89x67步 (~10x7.5度)
    ("8.标准矩形89x67", "R,89,67,800\n",  6000, "激光画标准矩形"),
]


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
    print("  电机调试工具 - 逐步排查")
    print("  共 {} 个步骤".format(len(TEST_STEPS)))
    print("  短按=执行  长按=跳过")
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
    print("UART 初始化完成, 波特率 115200")

    test_idx = 0               # 当前步骤索引
    key_hold_frames = 0        # 按键持续帧数
    status_msg = "准备就绪"
    last_feedback = ""
    feedback_raw = ""          # 原始数据用于调试
    running_cmd = False        # 正在执行命令
    cmd_done_time = 0          # 命令完成后的等待帧

    while True:
        clock.tick()
        os.exitpoint()

        img = sensor.snapshot(chn=CAM_CHN_ID_0)

        # ---- 按键检测（帧计数方式） ----
        if key.is_pressed() == 1:
            key_hold_frames += 1
        else:
            if key_hold_frames > 0:
                # 刚松手
                if key_hold_frames < 30:
                    # ---- 短按：执行当前步骤 ----
                    if test_idx < len(TEST_STEPS):
                        name, cmd, wait_ms, hint = TEST_STEPS[test_idx]
                        print(">>> [{}]".format(name))
                        print("    发送: '{}'".format(cmd.strip()))
                        print("    预期: {}".format(hint))
                        try:
                            uart.send(cmd)
                            status_msg = "{} - 已发送".format(name)
                            test_idx += 1
                        except Exception as e:
                            print("    !!! 发送失败: {}".format(e))
                            status_msg = "发送失败! {}".format(e)
                    else:
                        status_msg = "全部测试完成!"
                        print(status_msg)
                else:
                    # ---- 长按：跳过当前步骤 ----
                    if test_idx < len(TEST_STEPS):
                        name = TEST_STEPS[test_idx][0]
                        print("--- 跳过: {}".format(name))
                        test_idx += 1
                        status_msg = "已跳过: {}".format(name)
                    else:
                        test_idx = 0
                        status_msg = "已重置"
                        print("--- 重置测试 ---")

            key_hold_frames = 0

        # ---- 接收 STM32 反馈 ----
        data = uart.read()
        if data is not None:
            msg = safe_str(data)
            feedback_raw = repr(data)
            if msg:
                print("[STM32] {}".format(msg))
                last_feedback = msg
                # 检测完成信号
                if "Done" in msg:
                    status_msg = "绘制完成!"

        # ---- 画面显示 ----
        # 标题
        img.draw_string_advanced(5, 3, 20,
            "=== MOTOR DEBUG ===", color=(0, 255, 255))

        # 步骤进度
        progress = "{}/{}".format(test_idx, len(TEST_STEPS))
        img.draw_string_advanced(5, 28, 18,
            "Progress: {}".format(progress), color=(255, 255, 0))

        # 下一个测试
        if test_idx < len(TEST_STEPS):
            next_name = TEST_STEPS[test_idx][0]
            next_hint = TEST_STEPS[test_idx][3]
        else:
            next_name = "DONE"
            next_hint = "所有测试完成"
        img.draw_string_advanced(5, 50, 16,
            "Next: {}".format(next_name), color=(0, 255, 0))
        img.draw_string_advanced(5, 70, 14,
            "Hint: {}".format(next_hint), color=(0, 200, 0))

        # 状态
        img.draw_string_advanced(5, 92, 17,
            "Status: {}".format(status_msg), color=(255, 255, 0))

        # STM32 原始反馈
        if last_feedback:
            img.draw_string_advanced(5, 114, 15,
                "STM32: {}".format(last_feedback[:55]), color=(255, 160, 0))

        # 操作说明
        img.draw_string_advanced(5, 138, 15,
            "[短按] 执行  [长按] 跳过", color=(180, 180, 180))

        # FPS
        img.draw_string_advanced(5, 162, 18,
            "fps: {:.0f}".format(clock.fps()), color=(255, 0, 0))

        # 按键状态条
        if key_hold_frames > 0:
            bar_len = min(key_hold_frames, 30)
            bar = "=" * (bar_len // 2)
            if key_hold_frames >= 30:
                bar += " LONG"
            img.draw_string_advanced(5, 185, 14,
                "Hold:{}".format(bar), color=(255, 128, 128))

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
