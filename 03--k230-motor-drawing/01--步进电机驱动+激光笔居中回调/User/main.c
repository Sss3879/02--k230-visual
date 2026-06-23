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
        KeyNum = Key_GetNum();

        if (KeyNum == 1)
        {
            // 按下 PB11，激光笔状态翻转
            Light_ON();
        }

        /* ===== 矩形绘制命令（优先级高于误差修正） ===== */
        if (Serial_IsRectCmd == 1)
        {
            Serial_IsRectCmd = 0;
            Serial_Printf("Draw Rect: w=%d h=%d delay=%d\r\n",
                          (int)Serial_RectWidth, (int)Serial_RectHeight, Serial_RectDelay);
            Gimbal_DrawRectangle(Serial_RectWidth, Serial_RectHeight, Serial_RectDelay);
            Serial_Printf("Rect Done\r\n");
        }

        /* ===== 误差修正（激光居中） ===== */
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
    }
}
