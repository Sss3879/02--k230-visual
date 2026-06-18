#include "StepMotor.h"
#include "Delay.h"

void StepMotor_GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStructure;

    // 1. 开启 GPIOA 和 GPIOB 时钟
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB, ENABLE);

    // 2. GPIO 通用配置：推挽输出，50MHz
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;

    // 3. 只初始化 GPIOA 上实际用到的引脚
    // PA0 PA1 PA2 PA3 PA4 PA5 PA6 PA7
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_0 |
                                  GPIO_Pin_1 |
                                  GPIO_Pin_2 |
                                  GPIO_Pin_3 |
                                  GPIO_Pin_4 |
                                  GPIO_Pin_5 |
                                  GPIO_Pin_6 |
                                  GPIO_Pin_7;

    GPIO_Init(GPIOA, &GPIO_InitStructure);

    // 4. 只初始化 GPIOB 上实际用到的引脚
    // PB0 PB1
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_0 |
                                  GPIO_Pin_1;

    GPIO_Init(GPIOB, &GPIO_InitStructure);
}

void StepMotor_InitMotor(StepMotor* motor,
                         GPIO_TypeDef* pwm_gpiox, uint16_t pwm_pin,
                         GPIO_TypeDef* dir_gpiox, uint16_t dir_pin,
                         GPIO_TypeDef* dcy_gpiox, uint16_t dcy_pin,
                         GPIO_TypeDef* slp_gpiox, uint16_t slp_pin,
                         GPIO_TypeDef* rst_gpiox, uint16_t rst_pin)
{
    motor->PWM_GPIOx = pwm_gpiox;
    motor->PWM_Pin = pwm_pin;

    motor->DIR_GPIOx = dir_gpiox;
    motor->DIR_Pin = dir_pin;

    motor->DCY_GPIOx = dcy_gpiox;
    motor->DCY_Pin = dcy_pin;

    motor->SLP_GPIOx = slp_gpiox;
    motor->SLP_Pin = slp_pin;

    motor->RST_GPIOx = rst_gpiox;
    motor->RST_Pin = rst_pin;

    motor->current_pulse = 0;

    GPIO_ResetBits(motor->PWM_GPIOx, motor->PWM_Pin);
    GPIO_ResetBits(motor->DIR_GPIOx, motor->DIR_Pin);

    // DCY 高电平：大扭矩
    GPIO_SetBits(motor->DCY_GPIOx, motor->DCY_Pin);

    // SLP 高电平：退出休眠
    GPIO_SetBits(motor->SLP_GPIOx, motor->SLP_Pin);

    // RST 高电平：正常工作
    GPIO_SetBits(motor->RST_GPIOx, motor->RST_Pin);
}

void StepMotor_Enable(StepMotor* motor)
{
    GPIO_SetBits(motor->SLP_GPIOx, motor->SLP_Pin);
    GPIO_SetBits(motor->RST_GPIOx, motor->RST_Pin);
}

void StepMotor_Disable(StepMotor* motor)
{
    GPIO_ResetBits(motor->SLP_GPIOx, motor->SLP_Pin);
}

void StepMotor_SetDir(StepMotor* motor, uint8_t dir)
{
    if (dir)
    {
        GPIO_SetBits(motor->DIR_GPIOx, motor->DIR_Pin);
    }
    else
    {
        GPIO_ResetBits(motor->DIR_GPIOx, motor->DIR_Pin);
    }
}

void StepMotor_MovePulse(StepMotor* motor, int32_t pulse, uint16_t delay_us)
{
    int32_t i;
    int32_t step;

    if (pulse == 0)
    {
        return;
    }

    if (pulse > 0)
    {
        StepMotor_SetDir(motor, 1);
        step = pulse;
    }
    else
    {
        StepMotor_SetDir(motor, 0);
        step = -pulse;
    }

    for (i = 0; i < step; i++)
    {
        GPIO_SetBits(motor->PWM_GPIOx, motor->PWM_Pin);
        Delay_us(delay_us);

        GPIO_ResetBits(motor->PWM_GPIOx, motor->PWM_Pin);
        Delay_us(delay_us);
    }

    motor->current_pulse += pulse;
}

void StepMotor_MoveToPulse(StepMotor* motor, int32_t target_pulse, uint16_t delay_us)
{
    int32_t error_pulse;

    error_pulse = target_pulse - motor->current_pulse;

    StepMotor_MovePulse(motor, error_pulse, delay_us);
}