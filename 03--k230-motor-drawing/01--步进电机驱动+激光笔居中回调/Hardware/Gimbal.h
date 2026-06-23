#ifndef __GIMBAL_H
#define __GIMBAL_H

#include "stm32f10x.h"

void Gimbal_Init(void);

void Gimbal_MoveYawAngle(float angle, uint16_t delay_us);
void Gimbal_MovePitchAngle(float angle, uint16_t delay_us);

void Gimbal_SetYawAngle(float target_angle, uint16_t delay_us);
void Gimbal_SetPitchAngle(float target_angle, uint16_t delay_us);

void Gimbal_SetAngle(float yaw_angle, float pitch_angle, uint16_t delay_us);

void Gimbal_DrawRectangle(int32_t width_steps, int32_t height_steps, uint16_t delay_us);

#endif
