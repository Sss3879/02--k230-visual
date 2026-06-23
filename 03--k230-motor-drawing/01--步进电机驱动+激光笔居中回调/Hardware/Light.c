#include "stm32f10x.h"
#include "Light.h"

uint8_t Light_Flag = 0;   // 0表示关闭，1表示打开

void Light_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStructure;

    // 开启 GPIOB 时钟
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB, ENABLE);

    // PB12 配置为推挽输出
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_12;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOB, &GPIO_InitStructure);

    // 默认关闭激光笔
    GPIO_ResetBits(GPIOB, GPIO_Pin_12);
    Light_Flag = 0;
}

void Light_ON(void)
{
    // PB12 输出高电平，激光笔打开
    GPIO_SetBits(GPIOB, GPIO_Pin_12);
    Light_Flag = 1;
}

void Light_OFF(void)
{
    // PB12 输出低电平，激光笔关闭
    GPIO_ResetBits(GPIOB, GPIO_Pin_12);
    Light_Flag = 0;
}

void Light_Turn(void)
{
    if (Light_Flag == 0)
    {
        Light_ON();
    }
    else
    {
        Light_OFF();
    }
}
