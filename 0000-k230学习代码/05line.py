# bilibili搜索学不会电磁场看教程
# 第一课，我们先简单跑个摄像头程序
import time
import os
import sys

from media.sensor import *
from media.display import *
from media.media import *
import time

sensor = None

try:
    print("camera_test")
    sensor = Sensor()
    sensor.reset()

    # 鼠标悬停在函数上可以查看允许接收的参数
    sensor.set_framesize(width=640,height=480)
    sensor.set_pixformat(Sensor.RGB565)

    Display.init(Display.ST7701, to_ide=True)
    # 初始化媒体管理器
    MediaManager.init()
    # 启动 sensor
    sensor.run()

    clock=time.clock()

    while True:
        clock.tick()
        os.exitpoint()
        img = sensor.snapshot(chn=CAM_CHN_ID_0)



#        img_line = img.to_rgb565(copy=True)
#        img_line.midpoint_pool(2, 2)
#        lines = img_line.find_line_segments((0, 0, 640//2, 480//2), 15, 15)
#        for line in lines:
#            if line.length() > 100:
#                img.draw_line(line.x1()*2, line.y1()*2, line.x2()*2, line.y2()*2, color=(0, 255, 0), thickness=5)

        img_line = img.to_rgb565(copy=True)
        img_line.midpoint_pool(2, 2)

        # 只看画面下半部分，适合循迹
        # 原图 640x480，缩小后是 320x240
        roi = (0, 120, 320, 120)

        lines = img_line.find_line_segments(roi, 15, 15)

        valid_lines = []

        for line in lines:
            if line.length() > 40:
                # 线段中点，注意现在是在缩小图上
                mid_x_small = (line.x1() + line.x2()) // 2
                mid_y_small = (line.y1() + line.y2()) // 2

                valid_lines.append((line, mid_x_small, mid_y_small, line.length()))

        # 按长度排序，优先保留最长的几条线
        valid_lines = sorted(valid_lines, key=lambda x: x[3], reverse=True)

        if len(valid_lines) >= 2:
            # 取最长的两条线，认为是黑线的左右边缘
            line1, mid_x1, mid_y1, len1 = valid_lines[0]
            line2, mid_x2, mid_y2, len2 = valid_lines[1]

            # 两条边缘线的中间，就是路线中心
            center_x_small = (mid_x1 + mid_x2) // 2
            center_y_small = (mid_y1 + mid_y2) // 2

            # 画出两条线
            for item in [valid_lines[0], valid_lines[1]]:
                line = item[0]
                img.draw_line(
                    line.x1() * 2,
                    line.y1() * 2,
                    line.x2() * 2,
                    line.y2() * 2,
                    color=(0, 255, 0),
                    thickness=4
                )

            # 映射回原图
            center_x = center_x_small * 2
            center_y = center_y_small * 2

            img.draw_cross(center_x, center_y, color=(255, 0, 0), size=12)

            error = center_x - 320
            print("two lines error:", error)

        elif len(valid_lines) == 1:
            # 只识别到一条线，先用这一条线的中点
            line, mid_x_small, mid_y_small, length = valid_lines[0]

            img.draw_line(
                line.x1() * 2,
                line.y1() * 2,
                line.x2() * 2,
                line.y2() * 2,
                color=(0, 255, 0),
                thickness=4
            )

            center_x = mid_x_small * 2
            center_y = mid_y_small * 2

            img.draw_cross(center_x, center_y, color=(255, 0, 0), size=12)

            error = center_x - 320
            print("one line error:", error)

        else:
            # 没识别到线
            error = None
            print("no line")

        img.draw_string_advanced(50,50,80,"fps:{}".format(clock.fps()),color=(255,0,0))
        img.compressed_for_ide()
        Display.show_image(img)
        print("fps:{}".format(clock.fps()))


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
