#include "Gimbal.h"
#include "StepMotor.h"

#define STEP_ANGLE          1.8f
#define MICROSTEP           16.0f

#define PULSE_PER_ROUND     (360.0f / STEP_ANGLE * MICROSTEP)

static StepMotor YawMotor;
static StepMotor PitchMotor;

static int32_t Angle_To_Pulse(float angle)
{
    return (int32_t)(angle / 360.0f * PULSE_PER_ROUND);
}

void Gimbal_Init(void)
{
    StepMotor_GPIO_Init();

    /*
       Yaw 电机：
       PWM -> PA0
       DIR -> PA1
       DCY -> PA2
       SLP -> PA3
       RST -> PA4
    */
    StepMotor_InitMotor(&YawMotor,
                        GPIOA, GPIO_Pin_0,
                        GPIOA, GPIO_Pin_1,
                        GPIOA, GPIO_Pin_2,
                        GPIOA, GPIO_Pin_3,
                        GPIOA, GPIO_Pin_4);

    /*
       Pitch 电机：
       PWM -> PB0
       DIR -> PB1
       DCY -> PA7
       SLP -> PA6
       RST -> PA5
    */
    StepMotor_InitMotor(&PitchMotor,
                        GPIOB, GPIO_Pin_0,
                        GPIOB, GPIO_Pin_1,
                        GPIOA, GPIO_Pin_7,
                        GPIOA, GPIO_Pin_6,
                        GPIOA, GPIO_Pin_5);
}
void Gimbal_MoveYawAngle(float angle, uint16_t delay_us)
{
    int32_t pulse;

    // Yaw 水平轴取反
    pulse = Angle_To_Pulse(angle);

    StepMotor_MovePulse(&YawMotor, pulse, delay_us);
}

void Gimbal_MovePitchAngle(float angle, uint16_t delay_us)
{
    int32_t pulse;

    // Pitch 先保持取反，因为你前面 y 是先往 0 靠近的
    pulse = Angle_To_Pulse(-angle);

    StepMotor_MovePulse(&PitchMotor, pulse, delay_us);
}

void Gimbal_SetYawAngle(float target_angle, uint16_t delay_us)
{
    int32_t target_pulse;

    // 和 MoveYawAngle 保持一致
    target_pulse = Angle_To_Pulse(target_angle);

    StepMotor_MoveToPulse(&YawMotor, target_pulse, delay_us);
}

void Gimbal_SetPitchAngle(float target_angle, uint16_t delay_us)
{
    int32_t target_pulse;

    // 和 MovePitchAngle 保持一致
    target_pulse = Angle_To_Pulse(-target_angle);

    StepMotor_MoveToPulse(&PitchMotor, target_pulse, delay_us);
}
void Gimbal_SetAngle(float yaw_angle, float pitch_angle, uint16_t delay_us)
{
    Gimbal_SetYawAngle(yaw_angle, delay_us);
    Gimbal_SetPitchAngle(pitch_angle, delay_us);
}
