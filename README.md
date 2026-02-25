# 🍎 Bad Apple 播放器 for ESP32-C3  (๑•̀ㅂ•́)و✧

<p align="center">
  <img src="https://media.giphy.com/media/3o7abB06u9bNzA8LC8/giphy.gif" alt="Bad Apple" width="320"/>
  <br>
  <em>让你的 ESP32-C3 也来跳 Bad Apple 吧～ ✨</em>
</p>

[![MicroPython](https://img.shields.io/badge/MicroPython-ESP32--C3-blue.svg)](https://micropython.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Bad Apple](https://img.shields.io/badge/Bad%20Apple-影绘-ff69b4.svg)](https://www.bilibili.com/video/BV1Fs411E7R3)

---

## 📖 项目简介

这是一个基于 **ESP32-C3** 和 **ST7735S 屏幕** 的 Bad Apple 影画播放器！  
它可以将经典的 Bad Apple 黑白动画以 **20 FPS** 的流畅度在 128x160 的小屏幕上播放，同时用压电蜂鸣器同步演奏音乐～ ヾ(≧▽≦*)o

项目包含三个部分：

- **视频压缩工具**（PC端 Python 脚本）：将 MP4 转换为 ESP32 可读取的压缩二进制文件。
- **旋律生成工具**（PC端 Python 脚本）：将 MIDI 文件转换为蜂鸣器音符序列。
- **ESP32 播放器固件**（MicroPython）：解压视频数据并显示，同时驱动蜂鸣器。

全部代码都已优化并添加了详细中文注释，非常适合作为你的第一个嵌入式开源项目！(◕‿◕✿)

---

## 🛠️ 硬件准备

| 组件          | 数量 | 说明                         |
|---------------|------|------------------------------|
| ESP32-C3 开发板 | 1    | 4MB Flash 版本（推荐）       |
| ST7735S 屏幕    | 1    | 128x160 像素，SPI 接口        |
| 压电蜂鸣器      | 1    | 无源蜂鸣器（可发不同频率）    |
| 杜邦线          | 若干 | 母对母 / 公对母               |

### 🔌 接线方式（´• ω •`）ﾉ♡

| 屏幕引脚 | ESP32-C3 GPIO | 说明           |
|----------|---------------|----------------|
| GND      | GND           | 电源地         |
| VCC      | 3.3V          | 电源正         |
| SCL      | GPIO2         | SPI 时钟       |
| SDA      | GPIO3         | SPI MOSI       |
| RES      | GPIO10        | 复位           |
| DC       | GPIO6         | 数据/命令选择  |
| CS       | GPIO7         | 片选           |
| BLK      | GPIO11        | 背光（PWM控制）|

**蜂鸣器**：正极 → GPIO9，负极 → GND ✨

> 注：如果屏幕背光不需要 PWM 调光，可将 BLK 直接接 3.3V，此时代码中的 `backlight()` 仍可调用，但无实际效果。

---

## 💻 软件环境

### 1. 安装 Python 依赖（在电脑上）
```bash
pip install opencv-python numpy mido
```

### 2. 为 ESP32-C3 烧录 MicroPython
- 从 [MicroPython 官网](https://micropython.org/download/ESP32_GENERIC_C3/) 下载最新的 .bin 固件。
- 使用 **Thonny** 烧录：
  1. 打开 Thonny，点击菜单 `运行` → `配置解释器`。
  2. 在“解释器”选项卡中，选择“MicroPython (ESP32)”，端口选择你的串口（如 COM3）。
  3. 点击“安装或更新固件”，选择下载的 .bin 文件，按提示完成烧录。
  4. 成功后，Shell 中会出现 `>>>` 提示符。

---

## 📁 文件说明

将以下文件保存到你的电脑，稍后上传到 ESP32-C3：

| 文件名 | 作用 | 是否需要上传到 ESP32 |
|--------|------|----------------------|
| `st7735s.py` | 屏幕驱动（已优化，带可爱注释 (｡♥‿♥｡)） | ✅ 是 |
| `main.py` | 主播放程序（音画同步、双缓冲） | ✅ 是 |
| `convert_badapple_gui.py` | 视频压缩工具（PC端运行） | ❌ 否 |
| `midi_to_melody.py` | MIDI 转旋律工具（PC端运行） | ❌ 否 |
| `badapple_gzip.bin` | 压缩后的视频数据（由工具生成） | ✅ 是 |
| `melody.bin` | 旋律文件（由工具生成，可选） | ✅ 是 |

---

## 🎬 生成视频数据

1. 将你的 Bad Apple MP4 文件（例如 `badapple.mp4`）放在 `convert_badapple_gui.py` 同目录下。
2. 运行压缩工具：
   ```bash
   python convert_badapple_gui.py
   ```
3. 按提示输入参数（可直接回车使用默认值）：
   - MP4 文件路径：`badapple.mp4`
   - 目标帧率：`20`（与播放器一致）
   - 压缩级别：`9`（最高压缩比）
   - 输出文件名：`badapple_gzip.bin`
   - 屏幕宽度：`128`，高度：`160`
   - 使用 Otsu 自动阈值？`y`（推荐）
   - 使用中值滤波？`n`（如画面噪点多可开）

等待处理完成，会显示压缩比和文件大小。生成的 `badapple_gzip.bin` 就是我们要的视频数据～ (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧

---

## 🎵 生成旋律文件（可选）

如果你有 Bad Apple 的 MIDI 文件（如 `badapple.mid`），可以转换为蜂鸣器可读的 `melody.bin`。  
运行转换工具（交互模式）：
```bash
python midi_to_melody.py
```
然后：
- 选择 MIDI 文件（输入编号）
- 设置输出文件名（默认同基本名）
- 设置视频帧率 `20`
- 确认转换

完成后会显示前几个音符的预览。将 `melody.bin` 也上传到 ESP32。

> 如果没有 MIDI 文件，可以创建一个空文件 `melody.bin`（内容为 0 字节），播放器会静音播放。

---

## 📤 上传文件到 ESP32-C3

使用 Thonny 的文件视图（查看 → 文件）：
1. 左侧是你的电脑，右侧是 ESP32 设备。
2. 将以下文件 **拖拽** 到右侧（设备根目录）：
   - `st7735s.py`
   - `main.py`
   - `badapple_gzip.bin`
   - `melody.bin`（如果有）

检查剩余空间：在 Shell 中输入：
```python
import os
print(os.statvfs('/'))
```
剩余空间 = `f_bsize * f_bfree` 字节，确保大于两个文件的总和。

---

## ▶️ 播放！

在 Thonny 中打开 `main.py`，点击运行按钮（绿色三角形）。  
稍等片刻，屏幕上就会出现 Bad Apple 的影子画，蜂鸣器同步响起！ ヾ(≧▽≦*)o

播放结束后会自动循环，按 Ctrl+C 可以中断。

---

## 🧠 项目实现思路

### 1. 视频压缩原理
- 读取 MP4 视频，按目标帧率抽取帧。
- 将每帧转换为灰度图，缩放至屏幕分辨率（128x160）。
- 二值化（阈值或 Otsu），得到黑白图像。
- 使用 `np.packbits` 将每 8 个像素打包为 1 字节（单色图）。
- 用 zlib 压缩打包后的数据，并在每帧前写入 2 字节的长度信息。
- 最终生成一个二进制文件，每帧格式：`[长度(2B)][压缩数据]`。

### 2. ESP32 播放器设计
- **双缓冲**：两个缓冲区 `buf1` 和 `buf2`，一个用于显示，一个用于后台解压下一帧，避免画面撕裂。
- **流水线处理**：每帧循环中，一边解压下一帧，一边显示当前帧，解压和显示并行（受单核限制，实际是交替进行，但通过缓冲区隐藏了解压时间）。
- **帧率控制**：使用 `ticks_ms()` 测量显示耗时，并等待剩余时间以达到目标帧率。
- **音频同步**：旋律文件包含每帧对应的频率，每显示一帧就更新一次蜂鸣器频率，实现音画同步。

### 3. MIDI 转旋律
- 解析 MIDI 文件，提取每个音符的起止时间。
- 将时间轴按视频帧率离散化，每帧取当前活跃音符的最高频率（压电蜂鸣器只能发单音）。
- 行程编码合并连续相同频率的帧，生成 (频率×10, 持续帧数) 序列，写入二进制文件。

---

## 🔧 优化与调试

### 帧率不够？
- 降低目标帧率（重新生成视频，比如 15 FPS）
- 关闭中值滤波（压缩时选 `n`）
- 降低 SPI 速率（修改 `main.py` 中 `baudrate=20_000_000`）

### 内存不足？
- 缩小分辨率：如 96x120，需同步修改 `convert_badapple_gui.py` 和 `main.py` 中的 `WIDTH`、`HEIGHT` 以及 `MONO_SIZE` 计算公式。

### 音画不同步？
- 确保旋律文件的帧率（`-f` 参数）与视频帧率一致。
- 检查 MIDI 转换是否准确（可用播放器试听）。

### 屏幕不亮？
- 检查背光引脚 BLK 是否连接正确。如果直连 3.3V 则无需代码控制，否则检查 `backlight(255)` 是否调用。

### 解压错误？
- 确认视频文件是用 ZLIB 压缩的（脚本默认），且完整上传。

---

## ❓ 常见问题 (＠_＠;)

**Q: 上传文件时提示空间不足？**  
A: 用 `os.statvfs('/')` 查看剩余空间。如果确实不够，可以降低视频分辨率或帧率重新生成。

**Q: 屏幕显示花屏或颜色不对？**  
A: 检查 SPI 接线是否松动，或尝试降低 SPI 速率。也可以运行一个简单的测试程序（如画矩形）确认屏幕驱动正常。

**Q: 蜂鸣器声音太小？**  
A: 修改 `main.py` 中的 `BUZZER_DUTY` 值（范围 0-1023），调大试试。

**Q: 如何自己制作 MIDI 文件？**  
A: 可以用音乐软件导出 MIDI，或搜索“Bad Apple MIDI”下载现成的。注意保留主旋律轨道。

---

## 🌟 致谢

- 原版 Bad Apple 影绘 PV 制作团队 💀
- MicroPython 社区
- 所有提供灵感和帮助的开源项目

特别感谢 **你** 对这个项目的关注！如果喜欢，请给这个仓库点个 ⭐ 吧～ (✿◠‿◠)

---

## 👩‍💻 作者

- **你的名字**（[GitHub](https://github.com/yourusername)）  
  欢迎 issue 和 PR ～ 一起让 Bad Apple 更可爱！

---

## 📄 许可证

本项目采用 MIT 许可证，详情见 [LICENSE](LICENSE) 文件。

---

<p align="center">
  <img src="https://media.giphy.com/media/l0MYEqE2yRk4lZ0FO/giphy.gif" width="200"/>
  <br>
  <strong>Happy Hacking!  (ﾉ´ヮ`)ﾉ*: ･ﾟ</strong>
</p>
