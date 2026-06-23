import time
import os
import sys

from media.sensor import *
from media.display import *
from media.media import *

from ybUtils.YbKey import YbKey
from ybUtils.YbUart import YbUart

sensor = None
    # 鼠标悬停在函数上可以查看允许接收的参数
try:
    print("camera_test")
    sensor = Sensor()
    sensor.reset()
    sensor.set_framesize(width=640,height=480)
    sensor.set_pixformat(Sensor.RGB565)
    Display.init(Display.ST7701, to_ide=True)
    MediaManager.init()
    sensor.run()

    clock=time.clock()

    # 外设初始化
    key = YbKey()
    uart = YbUart(baudrate=115200)

    flag=0
    rect_cx = 0
    rect_cy = 0
    light_cx = 0
    light_cy = 0
    x_error = 0
    y_error = 0


    while True:
        clock.tick();
        os.exitpoint()
        img = sensor.snapshot(chn=CAM_CHN_ID_0)
        img=img.copy(roi=(164,15,384,288))

        if key.is_pressed()==1: #只有在按键按下的时候才开始识别矩形框！之后是一直识别小圆点
            for i in range(5):
                img = sensor.snapshot(chn=CAM_CHN_ID_0)
                img=img.copy(roi=(164,15,384,288))
                img_rect=img.to_grayscale(copy=True)
                img_rect=img_rect.binary([(110, 164)])
                rects=img_rect.find_rects(threshold=5000)
                if not rects==None:
                    for rect in rects:
                        corner=rect.corners()
                        img.draw_line(corner[0][0], corner[0][1], corner[1][0], corner[1][1], color=(0, 255, 0), thickness=3)
                        img.draw_line(corner[2][0], corner[2][1], corner[1][0], corner[1][1], color=(0, 255, 0), thickness=3)
                        img.draw_line(corner[2][0], corner[2][1], corner[3][0], corner[3][1], color=(0, 255, 0), thickness=3)
                        img.draw_line(corner[0][0], corner[0][1], corner[3][0], corner[3][1], color=(0, 255, 0), thickness=3)
                        rect_cx = sum([corner[k][0] for k in range(4)]) / 4
                        rect_cy = sum([corner[k][1] for k in range(4)]) / 4
                if len(rects)==2:
                    Display.show_image(img)
                    flag=1
                    print("{}".format(flag))
#                    time.sleep_ms(3000)
                    break
        if flag==1:
            blobs=img.find_blobs([(75, 100, -29, 50, -17, 5),(38, 100, 18, 79, -23, 19)],False,x_stride=3,y_stride=3,\
                                 pixels_threshold=20,margin=True)
            for blob in blobs:
                img.draw_rectangle(blob.x(),blob.y(),blob.w(),blob.h(),\
                                   color=(0,255,0),thickness=1,fill=False)
                light_cx = blob.x() + blob.w() / 2
                light_cy = blob.y() + blob.h() / 2


                x_error = light_cx - rect_cx
                y_error = light_cy - rect_cy
                send_data = "{},{}\n".format(round(x_error), round(y_error))
                uart.send(send_data)
#                print("send:", send_data)

#            print("fps:{}".format(clock.fps()))
            Display.show_image(img)

        data = uart.read()
        if data is not None:
            print(data)
        img.draw_string_advanced(50,50,20,"fps:{}".format(clock.fps()),color=(255,0,0))
        Display.show_image(img)
#        print("fps:{}".format(clock.fps()))


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
