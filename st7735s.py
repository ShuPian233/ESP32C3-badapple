from time import sleep_ms
from struct import pack
from machine import Pin, PWM
from micropython import const
import framebuf

# ---------- RGB565 颜色常量 ----------
RED   = const(0xF800)  # 实际应为 0xF800，但原代码可能因小端问题，这里保持原样
GREEN = const(0x07E0)
BLUE  = const(0x001F)
WHITE = const(0xFFFF)
CYAN   = const(0x07FF)
YELLOW = const(0xFFE0)
PURPLE = const(0xF81F)
GREY   = const(0x8410)

# 像素格式常量（直接使用 framebuf 定义）
RGB565 = framebuf.RGB565
GS8    = framebuf.GS8

# 显示模式常量
PART   = const(0x12)   # 部分显示
NORMAL = const(0x13)   # 正常显示
SCROLL = const(0x33)   # 滚动显示
IDLE   = const(0x39)   # 空闲显示

def clamp(aVal: int, aMin: int, aMax: int) -> int:
    """将 aVal 限制在 [aMin, aMax] 范围内"""
    return max(aMin, min(aMax, aVal))

def rgb565(R: int, G: int, B: int) -> int:
    """
    将 R,G,B 分量转换为小端模式的 RGB565 颜色值。
    注意：返回值为整数，实际在 framebuf 中为小端字节序。
    """
    # 公式：RGB565 = (R&0xF8)<<8 | (G&0xFC)<<3 | (B>>3)
    # 转换为小端字节序后，低字节在前，高字节在后
    c = (((R & 0xF8) << 8) | ((G & 0xFC) << 3) | (B >> 3)).to_bytes(2, 'little')
    return (c[0] << 8) + c[1]

class ST7735S(framebuf.FrameBuffer):
    """ST7735S 屏幕驱动，继承 framebuf.FrameBuffer 实现绘图功能。"""

    def __init__(self, spi, *, dc, rst, cs, bl=None, width=128, height=160):
        """
        初始化屏幕。
        :param spi:     已初始化的 SPI 对象
        :param dc:      数据/命令选择引脚
        :param rst:     复位引脚
        :param cs:      片选引脚
        :param bl:      背光引脚（可选，使用 PWM 控制亮度）
        :param width:   屏幕宽度（像素）
        :param height:  屏幕高度（像素）
        """
        self.spi = spi
        self.dc = Pin(dc, Pin.OUT, value=0)
        self.rst = Pin(rst, Pin.OUT, value=1)
        self.cs = Pin(cs, Pin.OUT, value=1)
        if bl is not None:
            self.bl = PWM(Pin(bl), freq=1000, duty_u16=32768)
        else:
            self.bl = None

        self.width = width
        self.height = height
        self.buffer = bytearray(width * height * 2)  # RGB565 每像素2字节
        super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)

        # 硬件复位
        self.rst(1)
        sleep_ms(5)
        self.rst(0)
        sleep_ms(5)
        self.rst(1)
        sleep_ms(5)

        # 初始化命令序列
        self._write(0x11)          # Sleep Out
        sleep_ms(120)               # 等待电源稳定

        # 根据宽高比设置横竖屏 (0x36 命令参数)
        if width > height:
            self._write(0x36, b'\x60')   # 横屏模式
        self._write(0x3A, b'\x55')       # 16位像素格式 (RGB565)
        self._write(0xB4, b'\x00')       # 点反转
        self._write(0x29, None)          # Display On

        sleep_ms(50)
        self.clear()                # 清屏为黑色
        if self.bl:
            self.backlight(128)      # 默认背光 50%

    def deinit(self):
        """释放资源（关闭 PWM）"""
        if self.bl:
            self.bl.deinit()

    def _write(self, command: int, data: bytes = None):
        """
        向屏幕发送命令和可选数据。
        :param command: 命令字节
        :param data:    数据字节串，若为 None 则不发送数据
        """
        self.cs.off()                # 片选使能
        self.dc.off()                # 命令模式
        self.spi.write(bytearray([command]))
        self.cs.on()                 # 释放片选
        if data is not None:
            self.cs.off()
            self.dc.on()              # 数据模式
            self.spi.write(data)
            self.cs.on()

    def clear(self, c: int = 0):
        """用颜色 c 填充整个屏幕（默认黑色）。"""
        self.fill(c)
        self.show()

    def backlight(self, duty: int):
        """
        设置背光亮度。
        :param duty: 亮度 0-255
        """
        if self.bl:
            self.bl.duty_u16((duty % 256) * 257)  # 将 0-255 映射到 0-65535

    def sleep(self):
        """进入睡眠模式（低功耗）。"""
        if self.bl:
            self.backlight(0)
        self._write(0x28)   # Display Off
        self._write(0x10)   # Sleep In

    def wakeup(self):
        """唤醒屏幕。"""
        self._write(0x11)   # Sleep Out
        sleep_ms(120)
        self._write(0x29)   # Display On
        if self.bl:
            self.backlight(128)

    def rotate(self, angle: int):
        """
        顺时针旋转屏幕（0, 90, 180, 270 度）。
        注意：旋转后宽度和高度会互换（90/270度时）。
        """
        # 旋转参数映射表
        rot_param = b'\x00\x60\xC0\xA0'
        idx = (angle // 90) % 4
        # 检查是否需要交换宽高
        if (idx % 2 == 0 and self.height < self.width) or (idx % 2 == 1 and self.height > self.width):
            self.width, self.height = self.height, self.width
            # 重新初始化 FrameBuffer 以适应新尺寸
            super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)
        self._write(0x36, pack('>B', rot_param[idx]))

    def setWindow(self, xs: int, ys: int, xe: int, ye: int):
        """
        设置后续写显存的目标窗口。
        坐标范围：0 ≤ xs ≤ xe < width, 0 ≤ ys ≤ ye < height
        """
        # 确保坐标在有效范围内
        xs = clamp(xs, 0, self.width - 1)
        xe = clamp(xe, xs, self.width - 1)
        ys = clamp(ys, 0, self.height - 1)
        ye = clamp(ye, ys, self.height - 1)
        self._write(0x2A, pack(">HH", xs, xe))   # 列地址
        self._write(0x2B, pack(">HH", ys, ye))   # 行地址

    def setDisMode(self, mode: int, *p):
        """
        设置显示模式。
        :param mode: PART, NORMAL, SCROLL, IDLE 之一
        :param p:    对于 SCROLL 模式，三个参数为 (顶部固定行数, 滚动区行数, 底部固定行数)
                     对于 PART 模式，两个参数为 (部分开始行, 部分结束行)
        """
        if mode == SCROLL:
            # 设置滚动区域
            self._write(mode, pack('>HHH', p[0], p[1], p[2]))
        else:
            self._write(mode)
            if mode == PART:
                # 设置部分显示区域
                p0 = clamp(p[0], 0, max(self.width, self.height) - 1)
                p1 = clamp(p[1], p0, max(self.width, self.height) - 1)
                self._write(0x30, pack(">HH", p0, p1))

    def setScrollStart(self, ys: int):
        """设置滚动开始的行地址。"""
        self._write(0x37, pack('>H', clamp(ys, 0, self.height - 1)))

    def show(self):
        """将整个缓冲区内容发送到屏幕显示。"""
        self.setWindow(0, 0, self.width - 1, self.height - 1)
        self._write(0x2C, self.buffer)

    def showVPart(self, ys: int, ye: int):
        """
        局部刷新垂直区域（从第 ys 行到第 ye 行）。
        用于快速更新屏幕的一部分。
        """
        ys = clamp(ys, 0, self.height - 1)
        ye = clamp(ye, ys, self.height - 1)
        self.setWindow(0, ys, self.width - 1, ye)
        # 计算缓冲区中对应行的切片
        start_byte = ys * self.width * 2
        end_byte = (ye + 1) * self.width * 2
        self._write(0x2C, memoryview(self.buffer)[start_byte:end_byte])

    def showImage(self, xs: int, ys: int, xe: int, ye: int, img_rgb565: bytes):
        """
        直接将 RGB565 格式的图像数据发送到屏幕指定窗口。
        用于快速显示全屏图像，无需经过缓冲区。
        """
        self.setWindow(xs, ys, xe, ye)
        self._write(0x2C, img_rgb565)

    def bufToBmp(self, bmpfile: str):
        """
        将当前缓冲区内容保存为 BMP 文件（RGB565 格式）。
        注意：此方法在 PC 上运行，MicroPython 通常不支持文件写入，但保留作为调试。
        """
        size = 70 + self.width * self.height * 2
        with open(bmpfile, 'wb') as f:
            # BMP 文件头
            f.write(pack('<HIII', 0x4D42, size, 0, 70))
            # 信息头
            f.write(pack('<IIiHHIIQQ', 40, self.width, -self.height, 1, 16, 3, size-70, 0, 0))
            # 颜色掩码（RGB565）
            f.write(pack('<IIII', 0xF800, 0x07E0, 0x001F, 0))
            # 像素数据（小端格式）
            for row in range(self.height):
                for col in range(self.width):
                    p = (row * self.width + col) * 2
                    f.write(pack('<BB', self.buffer[p+1], self.buffer[p]))
            print(f"已保存 BMP 文件: {bmpfile}")

    def drawText(self, text: str, x: int, y: int, fontDB, c: int = WHITE, bc: int = 0, alpha: bool = True):
        """
        在缓冲区上绘制文本（汉字或字符）。
        :param fontDB: 字体对象，需提供 get(ch) 方法返回 (w, h, bitmap)
        :param c:      前景色
        :param bc:     背景色
        :param alpha:  是否透明背景（True 表示背景色有效，False 表示透明）
        """
        # 创建两色调色板
        palette = framebuf.FrameBuffer(bytearray([
            bc & 0xFF, (bc >> 8) & 0xFF,
            c & 0xFF, (c >> 8) & 0xFF
        ]), 2, 1, framebuf.RGB565)
        for ch in text:
            w, h, fbm = fontDB.get(ch)
            if w == 0 or x + w > self.width or y + h > self.height:
                break
            fbuf = framebuf.FrameBuffer(fbm, w, h, framebuf.MONO_HLSB)
            self.blit(fbuf, x, y, bc if alpha else -1, palette)
            x += w

    def drawImage(self, imgw: int, imgh: int, img: bytes, format: int = RGB565, x: int = 0, y: int = 0):
        """
        在缓冲区上绘制图像。
        :param imgw:   图像宽度
        :param imgh:   图像高度
        :param img:    图像数据（字节串）
        :param format: 像素格式，RGB565 或 GS8
        :param x, y:   绘制起始坐标
        """
        fbuf = framebuf.FrameBuffer(bytearray(img), imgw, imgh, format)
        if format == GS8:
            # 构建灰度调色板（256级灰度转 RGB565）
            pbuf = bytearray(256 * 2)
            for i in range(256):
                t = i >> 3  # 将 8 位灰度映射到 5 位
                pbuf[i*2]   = (t << 3) | (t >> 3)      # 低字节
                pbuf[i*2+1] = (t << 5) | t             # 高字节
            palette = framebuf.FrameBuffer(pbuf, 256, 1, framebuf.RGB565)
            self.blit(fbuf, x, y, -1, palette)
        elif format == RGB565:
            self.blit(fbuf, x, y)
        else:
            print("仅支持 GS8 和 RGB565 格式")