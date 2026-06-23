"""
============================================================
  摄像头识别矩形 → 激光描边

  流程：
    1. 放一个矩形在摄像头下
    2. 按按键 → 摄像头识别矩形，锁定4个角点（绿色框）
    3. 再按按键 → 激光沿矩形4条边描一圈

  依赖原有 STM32 误差修正协议 "x,y\\n"，不需要改 STM32。
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
BINARY_THRESHOLD = (110, 152)    # 二值化阈值
RECT_THRESHOLD   = 5000          # find_rects 阈值
DETECT_FRAMES    = 10            # 检测矩形时采样帧数
CORRECT_THRESHOLD = 14           # 到达阈值（像素）
MAX_STEPS_PER_POINT = 50         # 每个追踪点最大修正次数
ROI_X = 128                     # ROI 裁剪起始X
ROI_Y = 117                     # ROI 裁剪起始Y
ROI_W = 480                     # ROI 裁剪宽度
ROI_H = 360                     # ROI 裁剪高度


# 激光颜色阈值
LASER_THRESHOLDS = [
    (76, 100, -9, 58, -24, 6),
    (48, 100, 14, 89, -47, 32),
]


def send_error(uart, x_err, y_err):
    msg = "{},{}\n".format(int(x_err), int(y_err))
    uart.send(msg)


def find_laser_center(img):
    """找激光光斑中心"""
    blobs = img.find_blobs(
        LASER_THRESHOLDS, False,
        x_stride=3, y_stride=3,
        pixels_threshold=20, margin=True
    )
    if blobs:
        best = max(blobs, key=lambda b: b.w() * b.h())
        return (best.x() + best.w() / 2, best.y() + best.h() / 2)
    return None


def detect_rectangle(img):
    """在当前画面中检测矩形，返回4个角点 [(x,y),...] 或 None"""
    img_gray = img.to_grayscale(copy=True)
    img_bin = img_gray.binary([BINARY_THRESHOLD])
    rects = img_bin.find_rects(threshold=RECT_THRESHOLD)

    if rects:
        # 取面积最大的矩形
        best = max(rects, key=lambda r: r.magnitude())
        corners = best.corners()  # 4个角点，顺序: [0]=左上?, 需要验证
        return [(c[0], c[1]) for c in corners]
    return None


def scale_corners(corners, scale, center):
    """以 center 为中心缩放角点"""
    cx, cy = center
    result = []
    for x, y in corners:
        sx = cx + (x - cx) * scale
        sy = cy + (y - cy) * scale
        result.append((sx, sy))
    return result


try:
    print("=== 识别矩形 → 激光描边 ===")

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

    # ---- 状态 ----
    # 0=等待检测矩形, 1=矩形已锁定等待画图, 2=画图中, 3=暂停, 4=完成
    state = 0
    state_msg = "按按键检测矩形"
    corners = []           # 目标矩形角点
    corner_indices = set() # 角点索引（到达时暂停消惯性）
    current_corner = 0
    step_count = 0
    laser_pos = None
    key_hold_frames = 0
    draw_count = 0

    # 检测到的矩形信息
    outer_corners = []      # 外圈（橙色）胶布外侧
    inner_corners = []      # 内圈（红色）胶布内侧

    RECT_CENTER_X = 320
    RECT_CENTER_Y = 240

    while True:
        clock.tick()
        os.exitpoint()

        img = sensor.snapshot(chn=CAM_CHN_ID_0)
        img = img.copy(roi=(ROI_X, ROI_Y, ROI_W, ROI_H))
        laser_pos = find_laser_center(img)
        if laser_pos:
            lx, ly = laser_pos
            img.draw_cross(int(lx), int(ly), color=(0, 255, 0), size=8, thickness=2)

        # ---- 按键 ----
        if key.is_pressed() == 1:
            key_hold_frames += 1
        else:
            if key_hold_frames > 0:
                if state == 0:
                    # ---- 检测矩形 ----
                    # 按键震动会导致摄像头微移，延迟等稳定
                    time.sleep_ms(400)
                    print(">>> 开始检测矩形...")
                    found_inner = None
                    found_outer = None

                    def poly_area(c):
                        s = 0
                        n = len(c)
                        for j in range(n):
                            s += c[j][0] * c[(j+1)%n][1]
                            s -= c[j][1] * c[(j+1)%n][0]
                        return abs(s) / 2

                    for i in range(DETECT_FRAMES):
                        img_sample = sensor.snapshot(chn=CAM_CHN_ID_0)
                        img_sample = img_sample.copy(roi=(ROI_X, ROI_Y, ROI_W, ROI_H))
                        img_gray = img_sample.to_grayscale(copy=True)
                        img_bin = img_gray.binary([BINARY_THRESHOLD])
                        rects = img_bin.find_rects(threshold=RECT_THRESHOLD)

                        if rects and len(rects) >= 2:
                            # 取面积最大的2个（过滤激光等小面积噪声）
                            rects_sorted = sorted(rects,
                                key=lambda r: poly_area([(c[0], c[1]) for c in r.corners()]),
                                reverse=True)
                            r0_corners = [(c[0], c[1]) for c in rects_sorted[0].corners()]
                            r1_corners = [(c[0], c[1]) for c in rects_sorted[1].corners()]

                            a0 = poly_area(r0_corners)
                            a1 = poly_area(r1_corners)

                            if a0 < a1:
                                found_inner, found_outer = r0_corners, r1_corners
                            else:
                                found_inner, found_outer = r1_corners, r0_corners

                            print("  从{}个形状中取最大2个: 内圈面积={:.0f}, 外圈面积={:.0f}".format(
                                len(rects), min(a0, a1), max(a0, a1)))
                            break

                        # fallback: 只有1个矩形时也接受（胶布太细或光线问题）
                        if rects and len(rects) == 1 and found_inner is None:
                            found_inner = [(c[0], c[1]) for c in rects[0].corners()]
                            found_outer = None  # 无外圈
                            print("  fallback: 只检测到1个矩形")

                    if found_inner is not None and len(found_inner) == 4:
                        import math

                        # 按角度排序（顺时针）
                        def sort_clockwise(corners_list):
                            cx = sum(c[0] for c in corners_list) / 4
                            cy = sum(c[1] for c in corners_list) / 4
                            return sorted(corners_list,
                                key=lambda c: math.atan2(c[1]-cy, c[0]-cx))

                        # 平行四边形拟合（对边向量平均，以质心为中心）
                        def fit_parallelogram(corners_list):
                            A, B, C, D = corners_list[0], corners_list[1], corners_list[2], corners_list[3]
                            # 对边向量平均 → 保证对边平行相等
                            hx = ((B[0]-A[0]) + (C[0]-D[0])) / 2
                            hy = ((B[1]-A[1]) + (C[1]-D[1])) / 2
                            vx = ((C[0]-B[0]) + (D[0]-A[0])) / 2
                            vy = ((C[1]-B[1]) + (D[1]-A[1])) / 2
                            # 用四角质心定位 → 避免A点偏差拖偏全体
                            cx = (A[0]+B[0]+C[0]+D[0]) / 4
                            cy = (A[1]+B[1]+C[1]+D[1]) / 4
                            return [
                                (cx - hx/2 - vx/2, cy - hy/2 - vy/2),
                                (cx + hx/2 - vx/2, cy + hy/2 - vy/2),
                                (cx + hx/2 + vx/2, cy + hy/2 + vy/2),
                                (cx - hx/2 + vx/2, cy - hy/2 + vy/2),
                            ]

                        inner_sorted = sort_clockwise(found_inner)
                        fit_inner = fit_parallelogram(inner_sorted)

                        if found_outer is not None:
                            # 有外圈 → 内外各自拟合 → 取中线
                            outer_sorted = sort_clockwise(found_outer)
                            fit_outer = fit_parallelogram(outer_sorted)
                            fit_mid = [
                                ((fit_inner[k][0] + fit_outer[k][0]) / 2,
                                 (fit_inner[k][1] + fit_outer[k][1]) / 2)
                                for k in range(4)
                            ]
                            outer_corners = fit_outer
                            mode_str = "中线(胶布本身)"
                        else:
                            # 只有内圈 → 直接用内圈
                            fit_mid = fit_inner
                            fit_outer = None
                            outer_corners = []
                            mode_str = "内圈(无外圈)"

                        inner_corners = fit_inner

                        # === 沿中线插值 → 密集追踪点 ===
                        STEP_PX = 8
                        raw_path = fit_mid + [fit_mid[0]]
                        corners = []
                        corner_indices = set()  # 角点索引（到达时暂停消惯性）
                        for k in range(4):
                            x1, y1 = raw_path[k]
                            x2, y2 = raw_path[k+1]
                            edge_len = ((x2-x1)**2 + (y2-y1)**2) ** 0.5
                            n_pts = max(2, int(edge_len / STEP_PX))
                            start_idx = len(corners)
                            for i in range(n_pts):
                                t = i / (n_pts - 1) if n_pts > 1 else 0
                                corners.append((x1 + (x2-x1)*t, y1 + (y2-y1)*t))
                            corner_indices.add(start_idx + n_pts - 1)  # 边的最后一个点=角点
                        corners.append(fit_mid[0])

                        total_points = len(corners)
                        print("  {}: {}个追踪点, {}个角点".format(mode_str, total_points, len(corner_indices)))

                        state = 1
                        step_count = 0  # 复用为自动倒计时
                        state_msg = "锁定! 3s后自动描边 [按取消]"
                    else:
                        state_msg = "未检测到矩形，调整光线/阈值再试"
                        print("--- 未检测到矩形")

                elif state == 1:
                    # 矩形已锁定，按按键取消（否则自动开始）
                    state = 0
                    state_msg = "已取消，按按键重新检测"
                    corners = []
                    corner_indices = set()
                    inner_corners = []
                    outer_corners = []
                    print("--- 用户取消描边")

                elif state == 4:
                    # 完成后重新开始
                    state = 0
                    state_msg = "按按键检测矩形"
                    corners = []
                    corner_indices = set()
                    inner_corners = []
                    outer_corners = []

            key_hold_frames = 0

        # ---- 矩形锁定后自动开始描边 ----
        if state == 1:
            step_count += 1
            AUTO_START_FRAMES = 30  # 约1秒
            if step_count >= AUTO_START_FRAMES:
                state = 2
                current_corner = 0
                step_count = 0
                total_pts = len(corners)
                state_msg = "画图中: 1/{}".format(total_pts)
                print(">>> 自动开始描边! {}个追踪点".format(total_pts))
            else:
                remain = (AUTO_START_FRAMES - step_count) // 10 + 1
                state_msg = "{}s后自动描边 [按取消]".format(remain)

        # ---- 画图状态机（逐点追踪，连续移动） ----
        if state == 2 and laser_pos is not None and current_corner < len(corners):
            tx, ty = corners[current_corner]
            lx, ly = laser_pos
            x_err = lx - tx
            y_err = ly - ty

            send_error(uart, x_err, y_err)
            step_count += 1

            # 到达当前点
            if abs(x_err) < CORRECT_THRESHOLD and abs(y_err) < CORRECT_THRESHOLD:
                # 到达角点 → 暂停消惯性；普通点 → 直接下一个
                if current_corner in corner_indices and current_corner < len(corners) - 1:
                    state = 3  # 角点暂停
                    step_count = 0
                else:
                    current_corner += 1
                    step_count = 0
                    if current_corner >= len(corners):
                        state = 4
                        draw_count += 1
                        state_msg = "完成! 共画{}个".format(draw_count)
                        print("*** 描边完成! {}个点 ***".format(len(corners)))
                    else:
                        state_msg = "画图中: {}/{}".format(current_corner + 1, len(corners))

            elif step_count >= MAX_STEPS_PER_POINT:
                current_corner += 1
                step_count = 0
                if current_corner >= len(corners):
                    state = 4
                    state_msg = "完成(部分跳过)"

        # 角点暂停（消惯性，防止冲出框）
        if state == 3:
            step_count += 1
            if step_count >= 8:  # 暂停约8帧 (~250ms)
                state = 2
                current_corner += 1
                step_count = 0
                state_msg = "画图中: {}/{}".format(current_corner + 1, len(corners))
            else:
                send_error(uart, 0, 0)  # 暂停时保持位置

        # ---- 显示 ----
        # 画外圈矩形（橙色细线 = 胶布外侧）
        if outer_corners:
            for i in range(4):
                x1, y1 = outer_corners[i]
                x2, y2 = outer_corners[(i + 1) % 4]
                img.draw_line(int(x1), int(y1), int(x2), int(y2),
                             color=(255, 128, 0), thickness=1)

        # 画内圈矩形（红色细线 = 胶布内侧）
        if inner_corners:
            for i in range(4):
                x1, y1 = inner_corners[i]
                x2, y2 = inner_corners[(i + 1) % 4]
                img.draw_line(int(x1), int(y1), int(x2), int(y2),
                             color=(255, 0, 0), thickness=1)

        # 画中线矩形（绿色粗线 = 胶布本身 = 实际绘制路径）
        if corners and len(corners) >= 4:
            for i in range(4):
                x1, y1 = corners[i]
                x2, y2 = corners[(i + 1) % 4]
                img.draw_line(int(x1), int(y1), int(x2), int(y2),
                             color=(0, 255, 0), thickness=2)

        # 高亮当前目标角点
        if state in (2, 3) and current_corner < len(corners):
            tx, ty = corners[current_corner]
            img.draw_circle(int(tx), int(ty), 8,
                           color=(0, 0, 255), thickness=3, fill=True)

        # 激光位置标签
        if laser_pos:
            img.draw_string_advanced(int(lx) + 12, int(ly) - 5, 14,
                "laser", color=(0, 255, 0))

        # 状态信息
        img.draw_string_advanced(5, 3, 20,
            "DETECT & DRAW", color=(0, 255, 255))
        img.draw_string_advanced(5, 26, 17,
            "State: {}".format(state_msg[:45]), color=(255, 255, 0))

        if state == 0:
            img.draw_string_advanced(5, 50, 16,
                "[按]检测矩形", color=(0, 255, 0))
        elif state == 1:
            img.draw_string_advanced(5, 50, 16,
                "[按]描边 胶布中线{}角".format(len(inner_corners) if inner_corners else 0),
                color=(0, 255, 0))
        elif state == 4:
            img.draw_string_advanced(5, 50, 17,
                "DONE! [按]重新开始", color=(0, 255, 0))

        if laser_pos:
            img.draw_string_advanced(5, 72, 15,
                "Laser:({:.0f},{:.0f})".format(lx, ly), color=(0, 200, 0))
        else:
            img.draw_string_advanced(5, 72, 15,
                "Laser: NOT FOUND!", color=(255, 0, 0))

        img.draw_string_advanced(5, 95, 16,
            "Threshold: {} RECT_THRESH:{}".format(BINARY_THRESHOLD, RECT_THRESHOLD),
            color=(180, 180, 180))

        img.draw_string_advanced(5, 120, 16,
            "Drawn: {} rects".format(draw_count), color=(255, 200, 0))

        img.draw_string_advanced(5, 150, 18,
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
