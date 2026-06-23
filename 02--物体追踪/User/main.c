#include "stm32f10x.h"
#include "Delay.h"
#include "Gimbal.h"
#include "Light.h"
#include "Key.h"
#include "Serial.h"
#define DEAD_ZONE_X     30
#define DEAD_ZONE_Y     30
#define STEP_DELAY_US   1000

int16_t x_error;
int16_t y_error;
//调大比例系数float yaw_step = 0.015f * abs(x_error);
//转动限幅，想精准在函数里面修改max
//减小 STEP_DELAY_US
float LimitFloat(float value, float min, float max)
{
    if (value < min) return min;
    if (value > max) return max;
    return value;
}

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
		if (Serial_GetDataFlag() == 1)
{
    x_error = Serial_GetXError();
    y_error = Serial_GetYError();

    Serial_Printf("x:%d y:%d\r\n", x_error, y_error);

    if (abs(x_error) > abs(y_error))
    {
        if (abs(x_error) > DEAD_ZONE_X )
        {
            float yaw_step = 0.015f * abs(x_error);//修改

            yaw_step = LimitFloat(yaw_step, 0.5f, 3.0f);//修改这里

            if (x_error > 0)
            {
                Gimbal_MoveYawAngle(-yaw_step, STEP_DELAY_US);
            }
            else
            {
                Gimbal_MoveYawAngle(yaw_step, STEP_DELAY_US);
            }
        }
    }
    else
    {
        if (abs(y_error) > DEAD_ZONE_Y)
        {
            float pitch_step = 0.02f * abs(y_error);

            pitch_step = LimitFloat(pitch_step, 0.5f, 4.0f);

            if (y_error >0)
						{
								Gimbal_MovePitchAngle(-pitch_step, STEP_DELAY_US);
						}
						else 
						{
								Gimbal_MovePitchAngle(pitch_step, STEP_DELAY_US);
						}
        }
    }
}
//				if (Serial_GetDataFlag() == 1)
//				{
//					x_error = Serial_GetXError();
//					y_error = Serial_GetYError();

//					Serial_Printf("x:%d y:%d\r\n", x_error, y_error);

//					if (x_error > DEAD_ZONE)
//					{
//						Gimbal_MoveYawAngle(STEP_ANGLE, STEP_DELAY_US);
//					}
//					else if (x_error < -DEAD_ZONE)
//					{
//						Gimbal_MoveYawAngle(-STEP_ANGLE, STEP_DELAY_US);
//					}

//					if (y_error > DEAD_ZONE)
//					{
//						Gimbal_MovePitchAngle(STEP_ANGLE, STEP_DELAY_US);
//					}
//					else if (y_error < -DEAD_ZONE)
//					{
//						Gimbal_MovePitchAngle(-STEP_ANGLE, STEP_DELAY_US);
//					}
//				}
				
    }
}
