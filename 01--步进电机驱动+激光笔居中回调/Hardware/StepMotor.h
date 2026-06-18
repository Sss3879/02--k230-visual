#ifndef __STEPMOTOR_H
#define __STEPMOTOR_H

#include "stm32f10x.h"

typedef struct
{
    GPIO_TypeDef* PWM_GPIOx;
    uint16_t PWM_Pin;

    GPIO_TypeDef* DIR_GPIOx;
    uint16_t DIR_Pin;

    GPIO_TypeDef* DCY_GPIOx;
    uint16_t DCY_Pin;

    GPIO_TypeDef* SLP_GPIOx;
    uint16_t SLP_Pin;

    GPIO_TypeDef* RST_GPIOx;
    uint16_t RST_Pin;

    int32_t current_pulse;
} StepMotor;

void StepMotor_GPIO_Init(void);

void StepMotor_InitMotor(StepMotor* motor,
                         GPIO_TypeDef* pwm_gpiox, uint16_t pwm_pin,
                         GPIO_TypeDef* dir_gpiox, uint16_t dir_pin,
                         GPIO_TypeDef* dcy_gpiox, uint16_t dcy_pin,
                         GPIO_TypeDef* slp_gpiox, uint16_t slp_pin,
                         GPIO_TypeDef* rst_gpiox, uint16_t rst_pin);

void StepMotor_Enable(StepMotor* motor);
void StepMotor_Disable(StepMotor* motor);
void StepMotor_SetDir(StepMotor* motor, uint8_t dir);
void StepMotor_MovePulse(StepMotor* motor, int32_t pulse, uint16_t delay_us);
void StepMotor_MoveToPulse(StepMotor* motor, int32_t target_pulse, uint16_t delay_us);


#endif
