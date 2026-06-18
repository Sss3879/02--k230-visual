#include "stm32f10x.h"
#include "Delay.h"
#include "Gimbal.h"
#include "Light.h"
#include "Key.h"
#include "Serial.h"
#define DEAD_ZONE       4
#define STEP_ANGLE      0.5f
#define STEP_DELAY_US   1000

int16_t x_error;
int16_t y_error;

int main(void)
{
		Serial_Init();
		uint8_t KeyNum;

    Key_Init();
    Light_Init();
	
    Gimbal_Init();

    Delay_ms(1000);

    while (1)
    {
////			Serial_Printf("Hello K230\r\n");
//			//数据收发测试
//			if (Serial_GetDataFlag() == 1)
//				{
//					x_error = Serial_GetXError();
//					y_error = Serial_GetYError();
//					Serial_Printf("Hello K230\r\n");

//					Serial_Printf("x:%d y:%d\r\n", x_error, y_error);
//				}
			

					 KeyNum = Key_GetNum();

        if (KeyNum == 1)
        {
            // 按下 PB11，激光笔状态翻转
            Light_ON();
        }
				if (Serial_GetDataFlag() == 1)
				{
					x_error = Serial_GetXError();
					y_error = Serial_GetYError();

					Serial_Printf("x:%d y:%d\r\n", x_error, y_error);

					if (x_error > DEAD_ZONE)
					{
						Gimbal_MoveYawAngle(STEP_ANGLE, STEP_DELAY_US);
					}
					else if (x_error < -DEAD_ZONE)
					{
						Gimbal_MoveYawAngle(-STEP_ANGLE, STEP_DELAY_US);
					}

					if (y_error > DEAD_ZONE)
					{
						Gimbal_MovePitchAngle(STEP_ANGLE, STEP_DELAY_US);
					}
					else if (y_error < -DEAD_ZONE)
					{
						Gimbal_MovePitchAngle(-STEP_ANGLE, STEP_DELAY_US);
					}
				}
				
//        // 水平轴转到 30°
//        Gimbal_SetYawAngle(10.0f, 800);
//        Delay_ms(1000);


//        // 俯仰轴转到 20°
//        Gimbal_SetPitchAngle(20.0f, 800);
//        Delay_ms(1000);

//        // 同时设置目标角度，注意：这个版本不是严格同时动，是先Yaw后Pitch
//        Gimbal_SetAngle(-30.0f, -20.0f, 800);
//        Delay_ms(1000);

//        // 回到零位
//        Gimbal_SetAngle(0.0f, 0.0f, 800);
//        Delay_ms(1000);
    }
}
