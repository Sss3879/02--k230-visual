"""
============================================================
  摄像头闭环画矩形 —— 用摄像头追踪激光，沿矩形路径移动

  原理：在屏幕中定义一个矩形（4个角点），逐点追踪激光，
       用现有 STM32 误差修正协议把激光移到目标位置。

  流程：
    1. 按下按键 → 在当前激光位置定义一个矩形
    2. 激光依次走到矩形的 4 个角：左上→右上→右下→左下→左上
    3. 每个角点到达后，停顿一下，再移动到下一个

  不需要修改 STM32 代码！直接用原来的 x,y 误差协议。
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
RECT_W = 120   # 矩形宽度（像素）
RECT_H = 80    # 矩形高度（像素）
SETTLE_MS = 800       # 到达角点后的稳定时间（ms）
CORRECT_THRESHOLD = 6 # 误差小于此值认为到达目标（像素）
MAX_STEPS_PER_CORNER = 200  # 每个角点最多修正次数（防止死循环）

# 激光颜色阈值（根据实际激光颜色调整）
# 格式: (L_min, L_max, A_min, A_max, B_min, B_max)
LASER_THRESHOLDS = [
    (75, 100, -29, 50, -17, 5),
    (38, 100, 18, 79, -23, 19),
]


def send_error(uart, x_err, y_err):
    """发送误差给 STM32"""
    msg = "{},{}\n".format(int(x_err), int(y_err))
    uart.send(msg)


def find_laser_center(img):
    """找到激光光斑的中心坐标，返回 (cx, cy) 或 None"""
    blobs = img.find_blobs(
        LASER_THRESHOLDS,
        False,
        x_stride=3, y_stride=3,
        pixels_threshold=20,
        margin=True
    )
    if blobs:
        # 取最大的 blob
        best = max(blobs, key=lambda b: b.w() * b.h())
        cx = best.x() + best.w() / 2
        cy = best.y() + best.h() / 2
        return (cx, cy)
    return None


try:
    print("=== 摄像头闭环画矩形 ===")
    print("矩形大小: {}x{} 像素".format(RECT_W, RECT_H))

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

    # ---- 状态机 ----
    # 0=等待按键, 1=锁定起点, 2=移动中, 3=到达角点暂停, 4=完成
    state = 0
    state_msg = "按按键定义矩形起点"

    # 矩形四个角（在激光当前位置基础上偏移）
    corners = []          # [(x, y), ...]  4个角点
    current_corner = 0    # 当前目标角点索引
    step_count = 0        # 当前角点的修正次数
    laser_pos = None      # 当前激光位置

    # 存储起点
    start_x, start_y = 0, 0

    key_hold_frames = 0
    draw_count = 0

    while True:
        clock.tick()
        os.exitpoint()

        img = sensor.snapshot(chn=CAM_CHN_ID_0)

        # ---- 追踪激光 ----
        laser_pos = find_laser_center(img)
        if laser_pos:
            lx, ly = laser_pos
            img.draw_cross(int(lx), int(ly), color=(0, 255, 0), size=8, thickness=2)

        # ---- 按键 ----
        if key.is_pressed() == 1:
            key_hold_frames += 1
        else:
            if key_hold_frames > 0:
                if state == 0 and laser_pos is not None:
                    # 第一次按键 → 用当前激光位置作为起点，定义矩形
                    start_x, start_y = laser_pos
                    # 定义矩形5个点：起点→右上→右下→左下→回到起点（闭合）
                    corners = [
                        (start_x, start_y),                          # 0. 起点
                        (start_x + RECT_W, start_y),                 # 1. 右上
                        (start_x + RECT_W, start_y + RECT_H),        # 2. 右下
                        (start_x, start_y + RECT_H),                 # 3. 左下
                        (start_x, start_y),                          # 4. 回到起点（闭合）
                    ]
                    current_corner = 0
                    step_count = 0
                    state = 2
                    state_msg = "移动到角点1/5 (右上)"
                    print(">>> 矩形起点: ({:.0f},{:.0f}), {}x{}".format(
                        start_x, start_y, RECT_W, RECT_H))

                elif state == 4:
                    # 完成后按键 → 重新开始
                    state = 0
                    state_msg = "按按键定义矩形起点"
                    corners = []
                    current_corner = 0

                elif state in (2, 3):
                    # 移动中按键 → 取消
                    state = 0
                    state_msg = "已取消，按按键重新开始"
                    corners = []
                    current_corner = 0

            key_hold_frames = 0

        # ---- 状态机逻辑 ----
        if state == 2 and laser_pos is not None and current_corner < len(corners):
            # 移动中
            tx, ty = corners[current_corner]
            lx, ly = laser_pos
            # 误差 = 激光 - 目标（与10--drawing.py保持一致）
            x_err = lx - tx
            y_err = ly - ty

            # 发送误差修正
            send_error(uart, x_err, y_err)
            step_count += 1

            # 检查是否到达
            if abs(x_err) < CORRECT_THRESHOLD and abs(y_err) < CORRECT_THRESHOLD:
                # 到达当前角点
                print("  到达角点 {}/4 ({:.0f},{:.0f}), 用了{}步".format(
                    current_corner + 1, tx, ty, step_count))
                current_corner += 1
                step_count = 0

                if current_corner >= len(corners):
                    # 所有角点完成！
                    state = 4
                    draw_count += 1
                    state_msg = "完成! 共画{}个矩形".format(draw_count)
                    print("*** 矩形绘制完成! ***")
                else:
                    state = 3
                    step_count = 0   # 重置帧计数，用于暂停计时
                    state_msg = "暂停中... 下一步角点{}/4".format(current_corner + 1)

            elif step_count >= MAX_STEPS_PER_CORNER:
                # 超时，跳过这个角点
                print("  超时! 跳过角点 {}/4, 误差 x={:.0f} y={:.0f}".format(
                    current_corner + 1, x_err, y_err))
                current_corner += 1
                step_count = 0
                if current_corner >= len(corners):
                    state = 4
                    state_msg = "完成(部分跳过)"
                else:
                    state = 3

        elif state == 3:
            # 到达角点后暂停
            # 用帧计数估算时间（约30fps，每帧~33ms）
            step_count += 1  # 复用为帧计数
            settle_frames = SETTLE_MS // 33  # 需要多少帧
            if step_count >= settle_frames:
                state = 2
                step_count = 0
                labels = ["起点", "右上", "右下", "左下", "闭合"]
                state_msg = "移动到角点{}/5 ({})".format(
                    current_corner + 1, labels[current_corner])

            # 暂停期间也发误差0（保持位置）
            send_error(uart, 0, 0)

        # ---- 显示 ----
        # 画目标矩形
        if corners:
            for i in range(4):
                x1, y1 = corners[i]
                x2, y2 = corners[(i + 1) % 4]
                img.draw_line(int(x1), int(y1), int(x2), int(y2),
                             color=(255, 0, 0), thickness=2)
            # 高亮当前目标角点
            if current_corner < 4:
                tx, ty = corners[current_corner]
                img.draw_circle(int(tx), int(ty), 8,
                               color=(0, 0, 255), thickness=3, fill=True)

        if laser_pos:
            lx, ly = laser_pos
            img.draw_string_advanced(int(lx) + 12, int(ly) - 5, 16,
                "laser", color=(0, 255, 0))

        # 状态信息
        img.draw_string_advanced(5, 3, 20,
            "DRAW RECT (camera)", color=(0, 255, 255))
        img.draw_string_advanced(5, 28, 17,
            "State: {}".format(state_msg[:45]), color=(255, 255, 0))
        img.draw_string_advanced(5, 50, 17,
            "Rect: {}x{} px".format(RECT_W, RECT_H), color=(0, 255, 0))

        if laser_pos:
            img.draw_string_advanced(5, 72, 16,
                "Laser: ({:.0f},{:.0f})".format(lx, ly), color=(0, 200, 0))
        else:
            img.draw_string_advanced(5, 72, 16,
                "Laser: NOT FOUND!", color=(255, 0, 0))

        if state == 2 and current_corner < len(corners):
            tx, ty = corners[current_corner]
            img.draw_string_advanced(5, 92, 16,
                "Target: ({:.0f},{:.0f}) step:{}".format(tx, ty, step_count),
                color=(255, 200, 0))

        img.draw_string_advanced(5, 115, 15,
            "[按]定义起点  [再按]取消", color=(180, 180, 180))

        if state == 4:
            img.draw_string_advanced(5, 135, 18,
                "DONE! {} rects drawn".format(draw_count), color=(0, 255, 0))

        img.draw_string_advanced(5, 160, 18,
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
