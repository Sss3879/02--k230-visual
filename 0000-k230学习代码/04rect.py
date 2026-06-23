import time
import os
import sys

from media.sensor import *
from media.display import *
from media.media import *

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

    clock=time.clock();

    while True:
        clock.tick();
        os.exitpoint()
        img = sensor.snapshot(chn=CAM_CHN_ID_0)
        img=img.copy(roi=(202,46,432,324))
#        img.draw_string_advanced(50,50,40,"Hello K230\n",color=(255,0,0))#字
#        img.draw_line(50,50,130,130,color=(0,0,255),thickness=10)#线
#        img.draw_rectangle(400,50,150,100,color=(0,0,255),thickness=4,fill=False)#方框
#        img.draw_keypoints([[320,240,0]],color=(255,0,255),thickness=4,fill=False,size=15)#带指向的圆
#        img.draw_circle(220,140,25,color=(255,0,255),thickness=4,fill=False)#圆
#        img.set_pixel(220,140,25,(255,255,0)#点

        img_rect=img.to_grayscale(copy=True);
        img_rect=img_rect.binary([((108, 255))]);
        rects=img_rect.find_rects(threshold=5000);


        for rect in rects:
            corner=rect.corners()
            img.draw_line(corner[0][0], corner[0][1], corner[1][0], corner[1][1], color=(0, 255, 0), thickness=4)
            img.draw_line(corner[1][0], corner[1][1], corner[2][0], corner[2][1], color=(0, 255, 0), thickness=4)
            img.draw_line(corner[2][0], corner[2][1], corner[3][0], corner[3][1], color=(0, 255, 0), thickness=4)
            img.draw_line(corner[3][0], corner[3][1], corner[0][0], corner[0][1], color=(0, 255, 0), thickness=4)



        img.draw_string_advanced(50,50,80,"fps:{}".format(clock.fps()),color=(255,0,0))
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
