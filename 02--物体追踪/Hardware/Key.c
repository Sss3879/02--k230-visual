#include "stm32f10x.h"
#include "Delay.h"
#include "Key.h"

void Key_Init(void)
{
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB, ENABLE);
    
    GPIO_InitTypeDef GPIO_InitStructure;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IPU;       // 上拉输入
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_11;          // 只初始化 PB11
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOB, &GPIO_InitStructure);
}

uint8_t Key_GetNum(void)
{
    uint8_t KeyNum = 0;

    // PB11 按下时为低电平
    if (GPIO_ReadInputDataBit(GPIOB, GPIO_Pin_11) == 0)
    {
        Delay_ms(20);   // 消抖

        while (GPIO_ReadInputDataBit(GPIOB, GPIO_Pin_11) == 0);
        // 等待按键松开

        Delay_ms(20);   // 松手消抖

        KeyNum = 1;     // 现在只有一个按键，返回 1
    }
    
    return KeyNum;
}
