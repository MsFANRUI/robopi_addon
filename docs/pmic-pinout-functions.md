# STM32F103 PMIC 当前 Pinout 与功能清单

更新日期：2026-11-04。适用芯片为 STM32F103C8T6，固件源为
`hex/roboparty_pmic`（检查时 HEAD `3fca34f`）。左板与右板是两套不同原理图布局，
不可混烧。这里记录**固件实际使用的引脚**；左板网络名还参考了 2026-11-03
提供的双图截图，尚未用完整原理图网表或 PCB 实物逐线复核。

## 固件与验证范围

| 项目 | 左板 `PMIC_LEFT_LAYOUT=ON` | 右板（默认） |
| --- | --- | --- |
| 当前应用版本 | `0.1.4-left` | `0.1.2-right` |
| 引导区 | `0x08000000` 至 `0x08000FFF`，直接跳应用 | 同一区域；检查 W25Q128 中的 OTA 镜像 |
| 应用区 | 从 `0x08001000` 启动 | 从 `0x08001000` 启动；末端预留配置页 |
| 配置页 | `0x0800FC00` | `0x0800FC00` |
| 固件包位置 | `firmware/pmic/candidate/left/` | `firmware/pmic/candidate/right/` |
| 串口 OTA | 不支持，返回 `OTA_ERR;` | 代码实现，尚无完整实板升级验证 |
| 当前验证 | `0.1.4-left` 已在同一块板烧录、回读校验，COM82/A100 串口查询通过；未做带载充电和模拟精度验证 | 构建通过；本清单不把其外设或 OTA 视为实板通过 |

两版镜像均标为 `engineering-candidate`，不是量产放行固件。

2026-11-04 左板实测：CMSIS-DAP `3181740232` 烧入 `0.1.4-left`，应用区
`0x08001000` 回读 41,156 字节与镜像完全一致；COM82 的只读 HIL 为 6/6，
重复 10 轮均通过，A100 `22282` 的只读 HIL 为 6/6。60 秒远端测试完成
`SYS_INFO` 15/15、`CHRG_INFO` 15/15，零空回复和错误。实测 UID 为
`0669FF555553787287104058`；电池状态、模拟量精度与带载输出尚未验证。

## 引脚对照

表中的“未用”只表示当前固件没有分配该 GPIO，**不代表硬件上可自由复用**。
方向以 MCU 为参照；带 `*` 的网络名或极性仍需实物确认。

**左板 PA4、PA5、PA6、PA7 全是普通 GPIO 输出，没有 LED PWM。**
其中 PA4/PA5 分别接 U34 的 `LED_R`/`LED_G`：U34 虽是三色灯封装，
图中只接了红、绿两路，第三路未连接。PA6/PA7 是另外的 `BAT_G`/`BAT_R`
信号。下表右板栏的 TIM3 PWM 属于另一版原理图，不适用于左板。

| MCU 引脚 | 左板网络 / 固件用途 | 右板网络 / 固件用途 | 外设与方向 |
| --- | --- | --- | --- |
| PA0 | `I_IN`，充电电流采样 | 同左 | ADC1 IN0，输入 |
| PA1 | `U_BAT`，电池电压采样 | 同左 | ADC1 IN1，输入 |
| PA2 | `U_IN`，输入电压采样 | 同左 | ADC1 IN2，输入 |
| PA3 | `ICTRL`，充电电流控制 | 同左 | TIM2 CH4 PWM，输出 |
| PA4 | `LED_R`，U34 红灯通道 | `Buzzer`，蜂鸣器 | 左：普通 GPIO 输出；右：GPIO 输出 |
| PA5 | `LED_G`，U34 绿灯通道 | `KEY1`，按键 | 左：普通 GPIO 输出；右：GPIO 输入 |
| PA6 | `BAT_G`，无 BMS 时软件保持关闭 | `B`，RGB 蓝通道 | 左：普通 GPIO 输出；右：TIM3 CH1 PWM |
| PA7 | `BAT_R`，异常指示* | `R`，RGB 红通道 | 左：普通 GPIO 输出；右：TIM3 CH2 PWM |
| PA8 | `FAN`，风扇调速 | 同左 | TIM1 CH1 PWM，输出 |
| PA9 | 无 485/BMS 接口；固件未分配 | `USART1_TX`，BMS 串口发送 | 左：未用；右：USART1 TX |
| PA10 | 无 485/BMS 接口；固件未分配 | `USART1_RX`，BMS 串口接收 | 左：未用；右：USART1 RX |
| PA13 | `SWDIO` | 同左 | SWD 调试，保留 |
| PA14 | `SWCLK` | 同左 | SWD 调试，保留 |
| PB0 | 未用 | `G`，RGB 绿通道 | 右：TIM3 CH3 PWM |
| PB1 | 未用 | `OLED_SCL` | 右：软件 I2C 时钟，输出 |
| PB2 | 未用 | `OLED_SDA` | 右：软件 I2C 数据，双向 |
| PB3 | `EN`，充电使能* | 同左 | GPIO 输出；代码写 1 表示使能 |
| PB4 | 未连接；固件不配置、不读取 | `BATINS`，电池在位* | 左：未用；右：GPIO 输入，代码取反 |
| PB5 | 未用 | 未用 | 当前固件未分配 |
| PB6 | 未用 | `IR_REC`，红外接收 | 右：GPIO 输入，代码取反 |
| PB7 | 未用 | `IR_EM`，红外发射 | 右：GPIO 输出 |
| PB8 | `SCL`，CH224/TMP100 | 同左 | 软件 I2C 时钟，开漏输出 |
| PB9 | `SDA`，CH224/TMP100 | 同左 | 软件 I2C 数据，双向 |
| PB10 | `USART3_TX`，上位机/控制台 | 同左 | USART3 TX，115200 8N1 |
| PB11 | `USART3_RX`，上位机命令 | 同左 | USART3 RX，115200 8N1 |
| PB12 | 未用 | `FLASH_CE`，W25Q128 片选 | 右：SPI2 CS，GPIO 输出 |
| PB13 | 未用 | `SPI_CLK`，W25Q128 时钟 | 右：SPI2 SCK，输出 |
| PB14 | 未用 | `SPI_MISO`，W25Q128 数据入 | 右：SPI2 MISO，输入 |
| PB15 | 未用 | `SPI_MOSI`，W25Q128 数据出 | 右：SPI2 MOSI，输出 |
| PD0 / PD1 | 8 MHz 外部晶振 | 同左 | HSE 输入/输出；系统时钟配置为 72 MHz |
| NRST | 复位 | 同左 | 调试/硬件复位 |
| BOOT0 | 启动选择 | 同左 | 硬件绑带；不是应用 GPIO |

PA11、PA12、PA15 及未列出的封装脚在当前固件中未分配；电源和地脚须按原理图
连接，不能按“未用 GPIO”处理。左板没有 OLED、蜂鸣器、按键、红外和 SPI Flash；
左板 `B:n;` 参数保留协议兼容，但没有蓝灯输出。左板固件中的
`R:n;`、`G:n;` 最终只按 0/非 0 控制 PA4/PA5 关/开，不提供亮度调节。

## 功能清单

| 功能 | 对应接口 / 行为 | 左板状态 | 右板状态 |
| --- | --- | --- | --- |
| RT-Thread 启动 | 8 MHz HSE，经 PLL 至 72 MHz | 左板只建充电和主机线程；实板启动、uptime 递增 | 充电、BMS、UI、主机线程，构建通过 |
| 主机协议 | USART3，ASCII `NAME:DATA;`；`CHRG_INFO`、`SYS_INFO` | 只读查询实测 | 构建通过，完整实板待测 |
| 芯片 SN | `SN_GET:1;` 返回 96-bit UID；`CHRG_SN` 写入被拒绝 | UID 与探针读数一致 | 代码存在，实板待测 |
| 固件版本 | `FW_VER:1;` 返回板型后缀 | 实板返回 `0.1.4-left` | `0.1.2-right` 由构建定义，实板待测 |
| 模拟采样 | PA0/1/2；电流、电池电压、输入电压 | 查询值可返回，精度未校准 | 代码存在，精度未校准 |
| PD 协商 | PB8/9 软件 I2C 操作 CH224、请求 PPS | 代码存在，带载待测 | 同左 |
| 温度 | PB8/9 软件 I2C 读取 TMP100 | 代码存在，温度实测待做 | 同左 |
| 充电控制与保护 | PA3 `ICTRL`、PB3 `EN` | 实板写入使能/电流命令仍返回 0；PB3 输出位和 TIM2 CCR4 均为 0，外部电气量待测 | 原控制逻辑存在，闭环未验证 |
| 电池在位 | 左板无 PB4 信号；右板仍用 PB4 | `BAT_INST:0;` 是兼容占位值，不代表测得的电池状态 | PB4 输入代码存在，实板待测 |
| BMS 通信 | 右板 PA9/10 USART1，Modbus 读 SoC/SoH | 左板不编译、不初始化 USART1；`BAT_SOC`/`BAT_SOH` 返回 `BMS_DISABLED;` | 代码存在，未验证 |
| 风扇 | PA8 PWM；充电线程按温度调节 | 输出极性/转速待测 | 同左 |
| 指示灯 GPIO | 左 PA4/5 控制 U34 红/绿两路，PA6/7 控制 `BAT_G`/`BAT_R` | 四路均为数字输出；`BAT_G` 保持关闭，`BAT_R` 表示异常；点亮极性待测 | 不适用 |
| RGB 灯 | 右 PA7 R、PB0 G、PA6 B | 不适用 | PWM 代码存在，亮度待测 |
| OLED、按键、蜂鸣器 | 右 PB1/2、PA5、PA4 | 不编译 | 代码存在，实板待测 |
| 红外检测 | 右 PB6/PB7 | 不编译；`IR_REC` 返回 0 | 代码存在，实板待测 |
| 配置保存 | `SAVE:1;` 写 STM32 内部 Flash 配置页 | 写入/断电保持待测 | 同左 |
| OTA | 右板外置 W25Q128 暂存后由 bootloader 搬运应用 | 不支持 | 仅代码/工具就绪；升级和断电恢复待测 |

## 放行前仍需核对

- 用正式左右板原理图和 PCB 网表逐脚核对，尤其 `EN`、右板 `BATINS`、LED、风扇的实际电平极性。
- 左板若要恢复充电，先明确电池化学体系、充满条件和保护输入，再验证 ADC 精度、PD 协商、充电曲线、关断与温升；右板另测 BMS。
- 右板 OTA 需做实板成功升级、错误镜像、传输中断和写 Flash 期间断电恢复。
- 每块板用 SWD 回读或等效产测确认镜像、UID、版本和输出功能。

源码定位：`boards/stm32f103_pmic/pinout.h`、`board.c`、`drivers/{adc,pwm,serial,w25q128}.c`，
`common/app/src/{app_main,app_charge,app_bms,app_host,app_config}.c`，以及
`boards/stm32f103_pmic/bootloader/boot_main.c`。包内固件与工具位于
`deb/robopi_addon/firmware/pmic/candidate/` 和 `scripts/robopi-pmic-ota.py`。
