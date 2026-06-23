"""
============================================================
  三合一多功能: 短按切换模式 / 长按执行

  模式1 居中: 检测矩形 → 激光自动回到矩形中心
  模式2 画框: 激光从当前位置画一个设定大小的矩形
  模式3 描边: 检测矩形 → 激光沿胶布中线自动描一圈
============================================================
"""
import time
import os
import sys
import math

from media.sensor import *
from media.display import *
from media.media import *

from ybUtils.YbKey import YbKey
from ybUtils.YbUart import YbUart

sensor = None

# ============================================================
#  通用参数
# ============================================================
ROI_X = 128
ROI_Y = 117
ROI_W = 480
ROI_H = 360

LASER_THRESHOLDS = [
    (76, 100, -9, 58, -24, 6),
    (48, 100, 14, 89, -47, 32),
]

# ============================================================
#  模式1: 居中参数
# ============================================================
CENTER_BINARY_THRESHOLD = (110, 152)
TRACE_BINARY_THRESHOLD = (110, 152)
CENTER_RECT_THRESHOLD   = 5000

# ============================================================
#  模式2: 画框参数
# ============================================================
DRAW_RECT_W = 80   # 预设矩形宽度（像素）
DRAW_RECT_H = 60   # 预设矩形高度（像素）
STEP_PX     = 8    # 插值间距

# ============================================================
#  模式3: 描边参数
# ============================================================
TRACE_BINARY_THRESHOLD = (110, 152)
TRACE_RECT_THRESHOLD   = 5000
TRACE_DETECT_FRAMES    = 10
TRACE_CORRECT_THRESH   = 14
TRACE_MAX_STEPS        = 50
TRACE_STEP_PX          = 8


def send_error(uart, x_err, y_err):
    uart.send("{},{}\n".format(int(x_err), int(y_err)))


def find_laser_center(img):
    blobs = img.find_blobs(LASER_THRESHOLDS, False,
                           x_stride=3, y_stride=3,
                           pixels_threshold=20, margin=True)
    if blobs:
        best = max(blobs, key=lambda b: b.w() * b.h())
        return (best.x() + best.w() / 2, best.y() + best.h() / 2)
    return None


def sort_clockwise(corners_list):
    cx = sum(c[0] for c in corners_list) / 4
    cy = sum(c[1] for c in corners_list) / 4
    return sorted(corners_list, key=lambda c: math.atan2(c[1]-cy, c[0]-cx))


def fit_parallelogram(corners_list):
    """平行四边形拟合: 对边向量平均+质心定位"""
    A, B, C, D = corners_list[0], corners_list[1], corners_list[2], corners_list[3]
    hx = ((B[0]-A[0]) + (C[0]-D[0])) / 2
    hy = ((B[1]-A[1]) + (C[1]-D[1])) / 2
    vx = ((C[0]-B[0]) + (D[0]-A[0])) / 2
    vy = ((C[1]-B[1]) + (D[1]-A[1])) / 2
    cx = (A[0]+B[0]+C[0]+D[0]) / 4
    cy = (A[1]+B[1]+C[1]+D[1]) / 4
    return [(cx-hx/2-vx/2, cy-hy/2-vy/2), (cx+hx/2-vx/2, cy+hy/2-vy/2),
            (cx+hx/2+vx/2, cy+hy/2+vy/2), (cx-hx/2+vx/2, cy-hy/2+vy/2)]


def interpolate_path(corners_4, step_px):
    """4个角点 → 密集插值追踪点 + 角点索引"""
    raw = corners_4 + [corners_4[0]]
    points = []
    corner_idx = set()
    for k in range(4):
        x1, y1 = raw[k]
        x2, y2 = raw[k+1]
        length = ((x2-x1)**2 + (y2-y1)**2) ** 0.5
        n = max(2, int(length / step_px))
        start = len(points)
        for i in range(n):
            t = i / (n - 1) if n > 1 else 0
            points.append((x1 + (x2-x1)*t, y1 + (y2-y1)*t))
        corner_idx.add(start + n - 1)
    points.append(corners_4[0])
    return points, corner_idx


def detect_rects(img, binary_th, rect_th, detect_frames):
    """检测黑色胶布内外圈 → (内圈4角, 外圈4角), 外圈可能为None"""
    for i in range(detect_frames):
        sample = sensor.snapshot(chn=CAM_CHN_ID_0)
        sample = sample.copy(roi=(ROI_X, ROI_Y, ROI_W, ROI_H))
        gray = sample.to_grayscale(copy=True)
        binary = gray.binary([binary_th])
        rects = binary.find_rects(threshold=rect_th)

        if rects and len(rects) >= 2:
            # 取面积最大两个(过滤激光小光斑) → 小=内圈 大=外圈
            def area(c):
                s, n = 0, len(c)
                for j in range(n):
                    s += c[j][0]*c[(j+1)%n][1] - c[j][1]*c[(j+1)%n][0]
                return abs(s)
            # 降序取最大2个 → 激光光斑面积小会被过滤
            big = sorted(rects, key=lambda r: area([(c[0],c[1]) for c in r.corners()]), reverse=True)[:2]
            a0, a1 = area([(c[0],c[1]) for c in big[0].corners()]), area([(c[0],c[1]) for c in big[1].corners()])
            inner = sort_clockwise([(c[0],c[1]) for c in (big[0] if a0 < a1 else big[1]).corners()])
            outer = sort_clockwise([(c[0],c[1]) for c in (big[1] if a0 < a1 else big[0]).corners()])
            return inner, outer

        if rects and len(rects) == 1:
            inner = sort_clockwise([(c[0],c[1]) for c in rects[0].corners()])
            return inner, None

    return None, None


# ============================================================
try:
    print("=== 三合一: 居中/画框/描边 ===")

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

    # ---- 模式 ----
    MODE_NAMES = ["1.居中", "2.画框", "3.描边", "4.重识"]
    mode = 0  # 当前模式索引

    # ---- 状态 ----
    state = 0  # 0=待机, 1=执行中, 2=完成
    state_msg = "短按切换 长按执行"

    # 共用变量
    corners = []           # 追踪点路径
    corner_indices = set() # 角点索引
    current_corner = 0
    step_count = 0
    laser_pos = None
    key_hold_frames = 0

    # 模式1: 居中
    rect_center = None     # 目标矩形中心

    # 模式2: 画框
    draw_start = None

    # 模式3: 描边
    inner_corners = []
    outer_corners = []
    total_pts = 0

    # 矩形快照: 一次检测，模式1/3复用
    snap_inner = None
    snap_outer = None

    while True:
        clock.tick()
        os.exitpoint()

        img = sensor.snapshot(chn=CAM_CHN_ID_0)
        img = img.copy(roi=(ROI_X, ROI_Y, ROI_W, ROI_H))
        laser_pos = find_laser_center(img)
        if laser_pos:
            lx, ly = laser_pos
            img.draw_cross(int(lx), int(ly), color=(0, 255, 0), size=6, thickness=1)

        # ---- 按键: 按一次执行，再按停止+切模式 ----
        if key.is_pressed() == 1:
            key_hold_frames += 1
        else:
            if key_hold_frames > 0:
                if state == 0:
                    # === 待机 → 执行当前模式 ===
                    state = 1
                    step_count = 0
                    current_corner = 0
                    print(">>> 执行: {}".format(MODE_NAMES[mode]))

                    if mode == 0:
                        # 模式1: 居中（快照优先）
                        if snap_inner is None:
                            time.sleep_ms(400)
                            snap_inner, snap_outer = detect_rects(img, CENTER_BINARY_THRESHOLD, CENTER_RECT_THRESHOLD, 10)
                        if snap_inner is not None:
                            inner_corners = snap_inner
                            outer_corners = snap_outer if snap_outer else []
                            rect_center = (sum(c[0] for c in snap_inner)/4, sum(c[1] for c in snap_inner)/4)
                            state_msg = "居中追踪中..."
                            print("  矩形中心: ({:.0f},{:.0f})".format(*rect_center))
                        else:
                            state = 2
                            state_msg = "未检测到矩形! 按继续"

                    elif mode == 1:
                        # 模式2: 画预设矩形
                        if laser_pos is not None:
                            x, y = laser_pos
                            corners_4 = [(x,y), (x+DRAW_RECT_W,y), (x+DRAW_RECT_W,y+DRAW_RECT_H), (x,y+DRAW_RECT_H)]
                            inner_corners = corners_4
                            outer_corners = []
                            corners, corner_indices = interpolate_path(corners_4, STEP_PX)
                            total_pts = len(corners)
                            state_msg = "画框: 1/{}".format(total_pts)
                            print("  画框 {}x{}: {}点".format(DRAW_RECT_W, DRAW_RECT_H, total_pts))
                        else:
                            state = 2
                            state_msg = "未找到激光! 按继续"

                    elif mode == 2:
                        # 模式3: 描边（快照优先）
                        if snap_inner is None:
                            time.sleep_ms(400)
                            snap_inner, snap_outer = detect_rects(img, TRACE_BINARY_THRESHOLD, TRACE_RECT_THRESHOLD, TRACE_DETECT_FRAMES)
                        if snap_inner is not None:
                            # === 完全复用15的拟合逻辑 ===
                            def area(c):
                                s, n = 0, len(c)
                                for j in range(n):
                                    s += c[j][0]*c[(j+1)%n][1] - c[j][1]*c[(j+1)%n][0]
                                return abs(s)/2

                            inner_s = sort_clockwise(snap_inner)
                            fit_inner = fit_parallelogram(inner_s)
                            if snap_outer is not None:
                                outer_s = sort_clockwise(snap_outer)
                                fit_outer = fit_parallelogram(outer_s)
                                outer_corners = fit_outer
                                fit_mid = [((fit_inner[k][0]+fit_outer[k][0])/2,(fit_inner[k][1]+fit_outer[k][1])/2) for k in range(4)]
                            else:
                                fit_mid = fit_inner
                                outer_corners = []
                            inner_corners = fit_inner
                            corners, corner_indices = interpolate_path(fit_mid, TRACE_STEP_PX)
                            total_pts = len(corners)
                            state_msg = "描边: 1/{}".format(total_pts)
                            print("  描边{}: {}点".format("(中线)" if snap_outer else "", total_pts))
                        else:
                            state = 2
                            state_msg = "未检测到矩形! 按继续"

                    elif mode == 3:
                        # 模式4: 清除快照 → 重新识别 → 描边
                        snap_inner = None
                        snap_outer = None
                        time.sleep_ms(400)
                        snap_inner, snap_outer = detect_rects(img, TRACE_BINARY_THRESHOLD, TRACE_RECT_THRESHOLD, TRACE_DETECT_FRAMES)
                        if snap_inner is not None:
                            inner_s = sort_clockwise(snap_inner)
                            fit_inner = fit_parallelogram(inner_s)
                            if snap_outer is not None:
                                outer_s = sort_clockwise(snap_outer)
                                fit_outer = fit_parallelogram(outer_s)
                                outer_corners = fit_outer
                                fit_mid = [((fit_inner[k][0]+fit_outer[k][0])/2,(fit_inner[k][1]+fit_outer[k][1])/2) for k in range(4)]
                            else:
                                fit_mid = fit_inner
                                outer_corners = []
                            inner_corners = fit_inner
                            corners, corner_indices = interpolate_path(fit_mid, TRACE_STEP_PX)
                            total_pts = len(corners)
                            state_msg = "重识+描边: 1/{}".format(total_pts)
                            print("  重识+描边{}: {}点".format("(中线)" if snap_outer else "", total_pts))
                        else:
                            state = 2
                            state_msg = "重识失败! 按继续"

                else:
                    # === 执行中/完成 → 停止 + 切下一个模式 ===
                    state = 0
                    mode = (mode + 1) % 4
                    state_msg = "{} [按执行]".format(MODE_NAMES[mode])
                    corners = []
                    corner_indices = set()
                    rect_center = None
                    inner_corners = []
                    outer_corners = []
                    print(">>> 停止! 切换到: {}".format(MODE_NAMES[mode]))

            key_hold_frames = 0

        # ---- 执行逻辑 ----
        if state == 1:
            if mode == 0:
                # 模式1: 持续居中
                if rect_center is None:
                    pass  # 检测失败，不动作
                elif laser_pos is None:
                    pass  # 找不到激光
                else:
                    rx, ry = rect_center
                    lx, ly = laser_pos
                    x_err = lx - rx
                    y_err = ly - ry
                    send_error(uart, x_err, y_err)
                    if step_count == 0:
                        print("  居中: 激光({:.0f},{:.0f}) 目标({:.0f},{:.0f}) err=({:.0f},{:.0f})".format(
                            lx, ly, rx, ry, x_err, y_err))
                    step_count += 1
                    if step_count % 30 == 0:
                        print("  居中追踪中... err=({:.0f},{:.0f})".format(x_err, y_err))
                    if abs(x_err) < 6 and abs(y_err) < 6:
                        state = 2
                        state_msg = "居中完成! 短按返回"
                        print("  居中完成")

            elif mode >= 1:
                # 模式2/3/4: 逐点追踪
                if len(corners) == 0:
                    pass  # 路径为空
                elif laser_pos is None:
                    pass
                elif current_corner < len(corners):
                    tx, ty = corners[current_corner]
                    lx, ly = laser_pos
                    x_err, y_err = lx - tx, ly - ty
                    send_error(uart, x_err, y_err)
                    if step_count == 0:
                        prev_pt = corners[current_corner - 1] if current_corner > 0 else (0, 0)
                        print("  点{}/{}: 目标({:.0f},{:.0f}) 激光({:.0f},{:.0f}) err({:.0f},{:.0f})".format(
                            current_corner+1, len(corners), tx, ty, lx, ly, x_err, y_err))
                    step_count += 1

                    if abs(x_err) < TRACE_CORRECT_THRESH and abs(y_err) < TRACE_CORRECT_THRESH:
                        if current_corner in corner_indices and current_corner < len(corners) - 1:
                            state = 3  # 角点暂停
                            step_count = 0
                        else:
                            current_corner += 1
                            step_count = 0
                            if current_corner >= len(corners):
                                state = 2
                                state_msg = "完成! 短按返回"
                                print("*** 完成! ***")
                            else:
                                state_msg = "画图中: {}/{}".format(current_corner+1, len(corners))

                    elif step_count >= TRACE_MAX_STEPS:
                        current_corner += 1
                        step_count = 0
                        if current_corner >= len(corners):
                            state = 2

        # ---- 角点暂停（必须在 state==1 外面！） ----
        if state == 3:
            step_count += 1
            if step_count >= 3:
                state = 1
                current_corner += 1
                step_count = 0
                state_msg = "画图中: {}/{}".format(current_corner+1, len(corners))
                print("  →下一边 点{}/{} 目标({:.0f},{:.0f})".format(
                    current_corner+1, len(corners), corners[current_corner][0], corners[current_corner][1]))
            else:
                send_error(uart, 0, 0)

        # ---- 显示 ----
        # 模式指示
        colors = [(255,255,0), (0,255,255), (255,0,255), (255,128,0)]
        for i, name in enumerate(MODE_NAMES):
            c = (0, 255, 0) if i == mode else (120, 120, 120)
            img.draw_string_advanced(5, 3 + i*22, 18, name, color=c)
            if i == mode:
                img.draw_string_advanced(100, 3 + i*22, 18, "<--", color=(0, 255, 0))

        # 状态
        img.draw_string_advanced(5, 75, 17, state_msg[:40], color=(255, 255, 0))

        # 激光位置
        if laser_pos:
            img.draw_string_advanced(5, 95, 15, "Laser:({:.0f},{:.0f})".format(lx, ly),
                                     color=(0, 200, 0))
        else:
            img.draw_string_advanced(5, 95, 15, "Laser: --", color=(255, 0, 0))

        # 矩形显示
        if inner_corners:
            for i in range(4):
                x1, y1 = inner_corners[i]
                x2, y2 = inner_corners[(i+1)%4]
                img.draw_line(int(x1), int(y1), int(x2), int(y2),
                             color=(255, 0, 0), thickness=1)
        if outer_corners:
            for i in range(4):
                x1, y1 = outer_corners[i]
                x2, y2 = outer_corners[(i+1)%4]
                img.draw_line(int(x1), int(y1), int(x2), int(y2),
                             color=(255, 128, 0), thickness=1)

        # 模式1居中目标
        if mode == 0 and rect_center is not None:
            img.draw_circle(int(rect_center[0]), int(rect_center[1]), 6,
                           color=(0, 255, 0), thickness=2)

        # 操作提示
        if state == 0:
            img.draw_string_advanced(5, 120, 15, "[按]执行 {}".format(MODE_NAMES[mode]),
                                     color=(0, 255, 0))
        elif state == 2:
            img.draw_string_advanced(5, 120, 15, "[按]切换模式",
                                     color=(255, 255, 0))
        elif state == 1:
            img.draw_string_advanced(5, 120, 15, "[按]停止",
                                     color=(255, 128, 128))

        img.draw_string_advanced(5, 145, 18, "fps: {:.0f}".format(clock.fps()),
                                 color=(255, 0, 0))

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
