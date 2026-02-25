import machine
import st7735s
from time import sleep_ms, ticks_ms, ticks_diff
import framebuf
import os
import deflate
import io
import struct

# ==================== 硬件初始化 ====================
# SPI 总线初始化（使用硬件 SPI1）
spi = machine.SPI(1, baudrate=30_000_000, polarity=0, phase=0,
                  sck=machine.Pin(2), mosi=machine.Pin(3))
# 屏幕对象创建，引脚按实际连接配置
lcd = st7735s.ST7735S(spi, dc=6, rst=10, cs=7, bl=11, width=128, height=160)
lcd.backlight(255)  # 背光最亮

# 蜂鸣器引脚和 PWM 初始化
BUZZER_PIN = 9
BUZZER_DUTY = 560   # 音量值 0-1023，可根据需要调节
buzzer = machine.PWM(machine.Pin(BUZZER_PIN), freq=440, duty=0)

# ==================== 视频参数 ====================
WIDTH, HEIGHT = 128, 160
# 单色图像每帧字节数：每行像素数补齐到8的倍数，再乘以高度
MONO_SIZE = HEIGHT * ((WIDTH + 7) // 8)   # 2560 字节
FPS = 20                                   # 目标帧率
FRAME_MS = 1000 // FPS                     # 每帧间隔时间（毫秒）

# 双缓冲：两个缓冲区分别用于显示和后台解压
buf1 = bytearray(MONO_SIZE)
buf2 = bytearray(MONO_SIZE)
fb1 = framebuf.FrameBuffer(buf1, WIDTH, HEIGHT, framebuf.MONO_HLSB)
fb2 = framebuf.FrameBuffer(buf2, WIDTH, HEIGHT, framebuf.MONO_HLSB)

# 压缩数据缓冲区，预留足够空间（压缩后最大不会超过原始数据+64）
MAX_COMP_SIZE = MONO_SIZE + 64
comp_buf = bytearray(MAX_COMP_SIZE)

# 调色板：将单色(0/1)映射为 RGB565 颜色，0→黑色(0x0000)，1→白色(0xFFFF)
palette = framebuf.FrameBuffer(bytearray(b'\x00\x00\xFF\xFF'), 2, 1, framebuf.RGB565)

# ==================== 文件路径 ====================
VIDEO_FILE = 'badapple_gzip.bin'   # 压缩视频文件
MELODY_FILE = 'melody.bin'         # 旋律文件（每个音符4字节：频率×10 + 持续帧数）

# 检查视频文件是否存在
try:
    stat = os.stat(VIDEO_FILE)
    print(f"📁 视频文件大小：{stat[6]} 字节")
except OSError:
    print(f"❌ 错误：文件 {VIDEO_FILE} 未找到")
    raise

# ==================== 旋律流式读取 ====================
def open_melody():
    """打开旋律文件，返回文件对象；若失败返回 None"""
    try:
        f = open(MELODY_FILE, "rb")
        return f
    except OSError:
        print("⚠️ 未找到旋律文件，将静音播放")
        return None

def read_next_note(melody_file):
    """
    从旋律文件读取下一个音符。
    返回 (freq_hz, frames) 元组，若文件结束则返回 None。
    文件格式：每4字节为小端 uint16 频率×10，uint16 持续帧数。
    """
    data = melody_file.read(4)
    if len(data) < 4:
        return None
    freq_x10, frames = struct.unpack('<HH', data)
    freq = freq_x10 / 10.0
    return (freq, frames)

# ==================== 视频播放主循环 ====================
while True:
    # 1. 打开视频文件
    try:
        vf = open(VIDEO_FILE, 'rb')
    except OSError:
        print("❌ 无法打开视频文件")
        break

    # 2. 打开旋律文件（流式）
    mf = open_melody()
    if mf:
        # 预读第一个音符
        current_note = read_next_note(mf)
        if current_note is None:
            mf.close()
            mf = None
    else:
        current_note = None

    # 3. 初始化音频状态
    current_freq = 0
    remaining_frames = 0
    if current_note:
        current_freq, remaining_frames = current_note

    # 4. 预读第一帧视频到 buf2
    len_data = vf.read(2)
    if len(len_data) < 2:
        print("❌ 视频文件为空")
        vf.close()
        if mf:
            mf.close()
        break
    frame_len = len_data[0] | (len_data[1] << 8)

    # 使用 memoryview 避免数据复制
    mv = memoryview(comp_buf)
    n = vf.readinto(mv[:frame_len])
    if n < frame_len:
        print("❌ 读取第一帧失败")
        vf.close()
        if mf:
            mf.close()
        break

    # 解压第一帧到 buf2
    try:
        buf = io.BytesIO(mv[:frame_len])
        with deflate.DeflateIO(buf, deflate.ZLIB) as d:
            d.readinto(buf2)
    except Exception as e:
        print("❌ 解压第一帧失败:", e)
        buf2[:] = b'\x00' * MONO_SIZE  # 黑屏

    # 5. 设置初始显示缓冲区
    display_fb = fb2   # 当前显示用的 FrameBuffer
    decode_fb = fb1    # 后台解压用的 FrameBuffer

    print("🎬 开始播放...")

    # 6. 逐帧播放
    while True:
        # ---------- 音频更新（每帧一次）----------
        if mf:
            if remaining_frames <= 0:
                # 读取下一个音符
                next_note = read_next_note(mf)
                if next_note is None:
                    # 文件结束，回到开头（循环播放旋律）
                    mf.seek(0)
                    next_note = read_next_note(mf)
                if next_note:
                    current_freq, remaining_frames = next_note
                else:
                    current_freq = 0
                    remaining_frames = 0
            if remaining_frames > 0:
                remaining_frames -= 1
                if current_freq > 0:
                    buzzer.freq(int(current_freq))
                    buzzer.duty(BUZZER_DUTY)
                else:
                    buzzer.duty(0)
        else:
            # 无旋律文件，保持静音
            buzzer.duty(0)

        # ---------- 读取下一帧压缩数据 ----------
        len_data = vf.read(2)
        if len(len_data) < 2:
            print("🏁 播放结束")
            break
        frame_len = len_data[0] | (len_data[1] << 8)

        # 读取压缩数据到 comp_buf
        n = vf.readinto(mv[:frame_len])
        if n < frame_len:
            print("⚠️ 文件可能损坏，提前终止")
            break

        # ---------- 后台解压到 decode_buf ----------
        try:
            buf = io.BytesIO(mv[:frame_len])
            with deflate.DeflateIO(buf, deflate.ZLIB) as d:
                d.readinto(decode_fb)  # 直接写入 decode_fb 的底层 buffer
        except Exception as e:
            print("❌ 解压错误:", e)
            decode_fb.fill(0)  # 清屏（黑）

        # ---------- 显示当前帧 ----------
        t_start = ticks_ms()
        # 将当前显示缓冲区的内容发送到屏幕
        lcd.blit(display_fb, 0, 0, -1, palette)
        lcd.show()

        # 帧率控制：确保每帧耗时至少 FRAME_MS
        elapsed = ticks_diff(ticks_ms(), t_start)
        wait = FRAME_MS - elapsed
        if wait > 0:
            sleep_ms(wait)

        # 交换缓冲区：下一帧显示的变成刚解压好的，解压用的变成之前显示的（将被覆盖）
        display_fb, decode_fb = decode_fb, display_fb

    # 7. 关闭文件，停止蜂鸣器
    vf.close()
    if mf:
        mf.close()
    buzzer.duty(0)

    sleep_ms(500)   # 重播前稍等