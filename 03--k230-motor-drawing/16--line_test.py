"""
============================================================
  直线运动测试 —— 诊断激光画弧线问题

  测试:
    1. 按按键 → 在当前激光位置定义一条水平线(→右)
    2. 激光沿直线移动
    3. 屏幕显示轨迹点，观察是否漂移

  可调参数见下方
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
#  可调参数
# ============================================================
LINE_LENGTH      = 100    # 直线长度（像素）
CORRECT_THRESH   = 4      # 到达目标阈值（像素）
MAX_STEPS        = 300    # 最大修正次数
SETTLE_DELAY_MS  = 500    # 到达后稳定时间

# === 测试用: 只改这一个参数 ===
# 0   = 完全封锁Y（纯水平，看是否直线）
# 1.0 = 不抑制（原始行为，看弧线多严重）
# >1  = 放大Y修正（如果激光自然往下掉，放大Y可以补偿）
Y_SUPPRESS       = 1.0    # 先试试1.0看原始弧线，再试0看纯水平

ROI_X = 24
ROI_Y = 21
ROI_W = 320
ROI_H = 240

LASER_THRESHOLDS = [
    (75, 100, -29, 50, -17, 5),
    (38, 100, 18, 79, -23, 19),
]


def send_error(uart, x_err, y_err):
    msg = "{},{}\n".format(int(x_err), int(y_err))
    uart.send(msg)


def find_laser_center(img):
    blobs = img.find_blobs(
        LASER_THRESHOLDS, False,
        x_stride=3, y_stride=3,
        pixels_threshold=20, margin=True
    )
    if blobs:
        best = max(blobs, key=lambda b: b.w() * b.h())
        return (best.x() + best.w() / 2, best.y() + best.h() / 2)
    return None


try:
    print("=== 直线运动测试 ===")
    print("参数: 线长={}px, Y抑制={}".format(LINE_LENGTH, Y_SUPPRESS))

    sensor = Sensor()
    sensor.reset()
    sensor.set_framesize(width=640, height=480)
    sensor.set_pixformat(Sensor.RGB565)
    Display.init(Display.ST7701, to_ide=True)
    MediaManager.init()
    sensor.run()

    clock = time.clock()
    key = YbKey()
    uart = YbUart(baudrate=115200)

    # 状态: 0=等待, 1=移动中, 2=到达暂停, 3=完成
    state = 0
    state_msg = "按按键开始水平线测试"
    target_x = target_y = 0
    start_x = start_y = 0
    step_count = 0
    laser_pos = None
    key_hold_frames = 0
    test_count = 0

    # 轨迹记录
    trail = []  # [(x, y), ...] 记录移动中的激光位置
    max_y_dev = 0  # 最大Y轴偏差

    while True:
        clock.tick()
        os.exitpoint()

        img = sensor.snapshot(chn=CAM_CHN_ID_0)
        img = img.copy(roi=(ROI_X, ROI_Y, ROI_W, ROI_H))

        # ---- 追踪激光 ----
        laser_pos = find_laser_center(img)
        if laser_pos:
            lx, ly = laser_pos
            img.draw_cross(int(lx), int(ly), color=(0, 255, 0), size=6, thickness=1)

        # ---- 按键 ----
        if key.is_pressed() == 1:
            key_hold_frames += 1
        else:
            if key_hold_frames > 0:
                if state == 0 and laser_pos is not None:
                    start_x, start_y = laser_pos
                    target_x = start_x + LINE_LENGTH
                    target_y = start_y  # 水平线，Y不变
                    step_count = 0
                    trail = []
                    max_y_dev = 0
                    state = 1
                    state_msg = "水平移动中... ({:.0f}->{:.0f})".format(start_x, target_x)
                    print(">>> 测试{}: ({:.0f},{:.0f}) -> ({:.0f},{:.0f}) 水平{}px".format(
                        test_count + 1, start_x, start_y, target_x, target_y, LINE_LENGTH))

                elif state == 3:
                    state = 0
                    state_msg = "按按键开始水平线测试"
                    trail = []

            key_hold_frames = 0

        # ---- 移动状态 ----
        if state == 1 and laser_pos is not None:
            lx, ly = laser_pos
            x_err = lx - target_x       # X方向: 全速修正
            y_err = (ly - target_y) * Y_SUPPRESS  # Y方向: ×抑制系数

            # 记录轨迹
            trail.append((lx, ly))
            y_dev = abs(ly - start_y)
            if y_dev > max_y_dev:
                max_y_dev = y_dev

            # 发送修正
            send_error(uart, x_err, y_err)
            step_count += 1

            # 到达检查
            if abs(x_err) < CORRECT_THRESH and abs(y_err) < CORRECT_THRESH:
                print("  到达! 步数={}, 最大Y偏差={:.1f}px, 轨迹点数={}".format(
                    step_count, max_y_dev, len(trail)))
                state = 2
                step_count = 0

            elif step_count >= MAX_STEPS:
                print("  超时! 最后误差 x={:.0f} y={:.0f}, Y偏差={:.1f}".format(
                    x_err, y_err, max_y_dev))
                state = 2
                step_count = 0

        elif state == 2:
            step_count += 1
            settle_frames = SETTLE_DELAY_MS // 33
            if step_count >= settle_frames:
                state = 3
                test_count += 1
                state_msg = "完成! Y偏差={:.1f}px [按]重测".format(max_y_dev)

        # ---- 显示 ----
        # 画目标线（红色虚线）
        if state >= 1:
            img.draw_line(int(start_x), int(start_y), int(target_x), int(target_y),
                         color=(255, 0, 0), thickness=2)
            # 起点和终点标记
            img.draw_circle(int(start_x), int(start_y), 5, color=(0, 255, 0), thickness=2)
            img.draw_circle(int(target_x), int(target_y), 5, color=(255, 0, 0), thickness=2)

        # 画轨迹（白点）
        for i, (tx, ty) in enumerate(trail):
            if i % 3 == 0:  # 每3帧画一个点，避免太密
                img.draw_circle(int(tx), int(ty), 1, color=(255, 255, 255), thickness=1)

        # 信息
        img.draw_string_advanced(5, 3, 20,
            "LINE TEST", color=(0, 255, 255))
        img.draw_string_advanced(5, 26, 17,
            "State: {}".format(state_msg[:40]), color=(255, 255, 0))
        img.draw_string_advanced(5, 48, 16,
            "Y_suppress={}".format(Y_SUPPRESS),
            color=(180, 180, 180))
        img.draw_string_advanced(5, 68, 16,
            "Max Y dev: {:.1f}px".format(max_y_dev), color=(255, 200, 0))

        if laser_pos:
            img.draw_string_advanced(5, 88, 15,
                "Laser:({:.0f},{:.0f}) step:{}".format(lx, ly, step_count),
                color=(0, 200, 0))
        else:
            img.draw_string_advanced(5, 88, 15,
                "Laser: NOT FOUND!", color=(255, 0, 0))

        if state == 0:
            img.draw_string_advanced(5, 110, 16,
                "[按]开始测试", color=(0, 255, 0))
        elif state == 3:
            img.draw_string_advanced(5, 110, 16,
                "[按]重新测试", color=(0, 255, 0))
            img.draw_string_advanced(5, 130, 16,
                "Tests done: {}".format(test_count), color=(255, 200, 0))

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
