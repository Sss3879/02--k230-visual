#include "stm32f10x.h"
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
uint8_t Serial_RxData;
uint8_t Serial_RxFlag;

/* ===== 新增：用于接收 K230 发来的 x_error,y_error ===== */

#define SERIAL_RX_BUF_SIZE 32

char Serial_RxBuffer[SERIAL_RX_BUF_SIZE];   // 接收一整行，例如 "35,-18"
uint8_t Serial_RxIndex = 0;                 // 当前接收到第几个字符

int16_t Serial_XError = 0;                  // K230 发来的 x_error
int16_t Serial_YError = 0;                  // K230 发来的 y_error

uint8_t Serial_DataFlag = 0;                // 收到一帧完整数据标志

/* ===== 矩形绘制命令 ===== */
uint8_t  Serial_IsRectCmd = 0;              // 收到矩形绘制命令标志
int32_t  Serial_RectWidth = 0;              // 矩形宽度（步数）
int32_t  Serial_RectHeight = 0;             // 矩形高度（步数）
uint16_t Serial_RectDelay = 800;            // 步间延时（微秒）


void Serial_Init(void)
{
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);
	
	GPIO_InitTypeDef GPIO_InitStructure;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;
	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_9;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(GPIOA, &GPIO_InitStructure);
	
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IPU;
	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_10;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(GPIOA, &GPIO_InitStructure);
	
	USART_InitTypeDef USART_InitStructure;
	USART_InitStructure.USART_BaudRate = 115200;
	USART_InitStructure.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
	USART_InitStructure.USART_Mode = USART_Mode_Tx | USART_Mode_Rx;
	USART_InitStructure.USART_Parity = USART_Parity_No;
	USART_InitStructure.USART_StopBits = USART_StopBits_1;
	USART_InitStructure.USART_WordLength = USART_WordLength_8b;
	USART_Init(USART1, &USART_InitStructure);
	
	USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);
	
	NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
	
	NVIC_InitTypeDef NVIC_InitStructure;
	NVIC_InitStructure.NVIC_IRQChannel = USART1_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 1;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 1;
	NVIC_Init(&NVIC_InitStructure);
	
	USART_Cmd(USART1, ENABLE);
}

void Serial_SendByte(uint8_t Byte)
{
	USART_SendData(USART1, Byte);
	while (USART_GetFlagStatus(USART1, USART_FLAG_TXE) == RESET);
}

void Serial_SendArray(uint8_t *Array, uint16_t Length)
{
	uint16_t i;
	for (i = 0; i < Length; i ++)
	{
		Serial_SendByte(Array[i]);
	}
}

void Serial_SendString(char *String)
{
	uint8_t i;
	for (i = 0; String[i] != '\0'; i ++)
	{
		Serial_SendByte(String[i]);
	}
}

uint32_t Serial_Pow(uint32_t X, uint32_t Y)
{
	uint32_t Result = 1;
	while (Y --)
	{
		Result *= X;
	}
	return Result;
}

void Serial_SendNumber(uint32_t Number, uint8_t Length)
{
	uint8_t i;
	for (i = 0; i < Length; i ++)
	{
		Serial_SendByte(Number / Serial_Pow(10, Length - i - 1) % 10 + '0');
	}
}

int fputc(int ch, FILE *f)
{
	Serial_SendByte(ch);
	return ch;
}

void Serial_Printf(char *format, ...)
{
	char String[100];
	va_list arg;
	va_start(arg, format);
	vsprintf(String, format, arg);
	va_end(arg);
	Serial_SendString(String);
}

uint8_t Serial_GetRxFlag(void)
{
	if (Serial_RxFlag == 1)
	{
		Serial_RxFlag = 0;
		return 1;
	}
	return 0;
}

uint8_t Serial_GetRxData(void)
{
	return Serial_RxData;
}
uint8_t Serial_GetDataFlag(void)
{
	if (Serial_DataFlag == 1)
	{
		Serial_DataFlag = 0;
		return 1;
	}
	return 0;
}

int16_t Serial_GetXError(void)
{
	return Serial_XError;
}

int16_t Serial_GetYError(void)
{
	return Serial_YError;
}
void USART1_IRQHandler(void)
{
	char ch;

	if (USART_GetITStatus(USART1, USART_IT_RXNE) == SET)
	{
		/* 先保留你原来的单字节接收逻辑 */
		Serial_RxData = USART_ReceiveData(USART1);
		Serial_RxFlag = 1;

		ch = Serial_RxData;

		/* ===== 新增：接收 K230 的一整行数据 ===== */
		if (ch == '\n')
		{
			/* 收到换行符，说明一帧结束 */
			Serial_RxBuffer[Serial_RxIndex] = '\0';

			/* 检测是否为矩形绘制命令: "R,width,height,delay" */
			if (Serial_RxBuffer[0] == 'R')
			{
				char *comma1 = strchr(Serial_RxBuffer, ',');
				if (comma1 != NULL)
				{
					char *comma2 = strchr(comma1 + 1, ',');
					if (comma2 != NULL)
					{
						char *comma3 = strchr(comma2 + 1, ',');
						if (comma3 != NULL)
						{
							*comma1 = '\0';
							*comma2 = '\0';
							*comma3 = '\0';

							Serial_RectWidth  = atoi(comma1 + 1);
							Serial_RectHeight = atoi(comma2 + 1);
							Serial_RectDelay  = (uint16_t)atoi(comma3 + 1);
						}
						else
						{
							/* 兼容2参数格式: "R,width,height" 无delay */
							*comma1 = '\0';
							*comma2 = '\0';

							Serial_RectWidth  = atoi(comma1 + 1);
							Serial_RectHeight = atoi(comma2 + 1);
							Serial_RectDelay  = 800;   /* 默认800us */
						}

						Serial_IsRectCmd = 1;
					}
				}
			}
			else
			{
				/* 查找逗号，例如 "35,-18" */
				char *comma = strchr(Serial_RxBuffer, ',');

				if (comma != NULL)
				{
					/* 把逗号位置变成字符串结束符 */
					*comma = '\0';

					/* 解析两个整数 */
					Serial_XError = atoi(Serial_RxBuffer);
					Serial_YError = atoi(comma + 1);

					/* 标记收到完整一帧 */
					Serial_DataFlag = 1;
				}
			}

			/* 清空缓冲区，准备接收下一帧 */
			Serial_RxIndex = 0;
			memset(Serial_RxBuffer, 0, SERIAL_RX_BUF_SIZE);
		}
		else if (ch != '\r')
		{
			/* 普通字符存进缓冲区 */
			if (Serial_RxIndex < SERIAL_RX_BUF_SIZE - 1)
			{
				Serial_RxBuffer[Serial_RxIndex++] = ch;
			}
			else
			{
				/* 防止数组越界 */
				Serial_RxIndex = 0;
				memset(Serial_RxBuffer, 0, SERIAL_RX_BUF_SIZE);
			}
		}

		USART_ClearITPendingBit(USART1, USART_IT_RXNE);
	}
}
