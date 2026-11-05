# STM32F103C8 PMIC Pinout 与功能清单

更新日期：2026-11-05。当前实物只有一颗 STM32F103C8；GD32F503 是源码仓库中的
另一 MCU 目标。安装包只提供当前 STM32F103C8 的一套固件，来源为
[`roboparty_pmic v0.1.7`](https://github.com/Roboparty/roboparty_pmic/releases/tag/v0.1.7)
中的历史 `-left` 命名镜像。后缀不表示板上有第二颗 MCU。

## 固件

| 项目 | 当前硬件 |
| --- | --- |
| MCU | STM32F103C8T6，8 MHz HSE，72 MHz 系统时钟 |
| 应用版本 | `0.1.7-left`，工程候选，尚未烧录实板 |
| 固件位置 | `firmware/pmic/candidate/stm32f103c8/` |
| Bootloader | `boot.bin`，烧录到 `0x08000000` |
| 应用 | `ChargeBAT.bin`，烧录到 `0x08001000` |
| 配置页 | `0x0800FC00` |
| 更新方式 | CMSIS-DAP/SWD；无外置 SPI Flash，不支持串口 OTA |

安装 addon 不会自动烧录 PMIC。可运行
`robopi-pmic-ota verify-bundle --bundle /opt/roboparty/share/pmic/candidate/stm32f103c8/manifest.json`
核对镜像 SHA-256、Flash 边界、向量和内嵌版本号。`robopi-pmic-ota inspect --port /dev/ttyUSB0`
通过 USART3 只读查询芯片 UID 和固件版本。

## 引脚

方向以 MCU 为参照。下表记录固件实际分配；未用脚不代表硬件上可自由复用。
PA4–PA7 为普通 GPIO 输出，没有 LED PWM。

| 引脚 | 当前用途 | 模式 / 行为 |
| --- | --- | --- |
| PA0 | `I_IN` 充电电流采样 | ADC1 IN0 |
| PA1 | `U_BAT` 电池电压采样 | ADC1 IN1；PA6/PA7 按引脚原始电压判断 |
| PA2 | `U_IN` 输入电压采样 | ADC1 IN2 |
| PA3 | `ICTRL` 充电电流控制 | TIM2 CH4 PWM |
| PA4 | 充电绿灯 | 充电使能且电池输出电压 <54V 时拉高 |
| PA5 | 充电红灯 | 充电使能且电池输出电压 >=54V 时拉高 |
| PA6 | `BAT_G` 指示灯 | PA1 引脚电压在 1.39–1.50V 时拉高 |
| PA7 | `BAT_R` 指示灯 | PA1 引脚电压在 1.21–<1.39V 时拉高 |
| PA8 | 风扇 | TIM1 CH1 PWM |
| PA9/PA10 | 未用；无 485/BMS 接口 | 不初始化 USART1 |
| PA13/PA14 | SWDIO/SWCLK | 调试接口，保留 |
| PB3 | `EN` 充电使能 | GPIO 输出，写 1 表示使能 |
| PB4 | 未连接 | 固件不配置、不读取 |
| PB8/PB9 | CH224/TMP100 SCL/SDA | 软件 I2C |
| PB10/PB11 | 主机 TX/RX | USART3，115200 8N1 |
| PD0/PD1 | 8 MHz 晶振 | HSE 输入/输出 |
| NRST/BOOT0 | 复位/启动选择 | 硬件接口 |

PA11、PA12、PA15、PB0–PB2、PB5–PB7、PB12–PB15 等未在当前固件中分配。
电源和地脚仍须依照原理图连接。灯色和实际高电平尚未用外部仪表核验。

## 功能与验证

| 功能 | 当前行为 | 验证状态 |
| --- | --- | --- |
| 自动充电 | 有效 ADC 连续采样、输入 16–<32V、CH224 有电流能力且无故障时使能 PB3/PA3 | 相同控制逻辑的 `0.1.5-left` 在 5V 关闭、20V PD 打开；未接电池包 |
| 充电灯 | PA4 绿灯到 54V；PA5 红灯从 54V 起；禁用充电时均关闭 | `0.1.7-left` 编译和边界单测通过，未实板验证 |
| PA1 电压灯 | 1.39V 归 PA6；1.21–<1.39V 归 PA7；区间外或采样失败均关闭 | 编译和边界单测通过，未实板验证 |
| 主机协议 | USART3，ASCII `NAME:DATA;`；`SN_GET`、`FW_VER`、`CHRG_INFO`、`SYS_INFO` | 旧版本只读 HIL 通过；新镜像未烧录 |
| BMS/电池在位 | 无外置 BMS/485 与 PB4 输入；兼容查询返回占位或 `BMS_DISABLED;` | 代码确认 |
| 风扇/温度 | PA8 PWM；PB8/PB9 读取 TMP100 | 带载行为待测 |
| 配置保存 | `SAVE:1;` 写内部 Flash 配置页 | 断电保持待测 |
| 串口 OTA | 不支持，`OTA_*` 返回 `OTA_ERR;` | 代码确认 |

54V 只切换灯，不是充满截止条件。电池包须有独立充电截止保护。
带载电流、充满截止、ADC 精度、温升、实际灯色和输出电平仍需实板验证。

源码位置：`boards/stm32f103_pmic/{pinout.h,board.c,drivers/adc.c,drivers/pwm.c}`、
`common/app/src/{app_charge.c,app_config.c,app_host.c}` 和
`boards/stm32f103_pmic/bootloader/boot_main.c`。
