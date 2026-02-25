#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 MIDI 文件转换为 melody.bin，用于 ESP32-C3 的 Bad Apple 播放器。

格式：每个音符占 4 字节（小端序）：
  - uint16：频率值 × 10
  - uint16：持续帧数（以指定的 FPS 计算）

用法（命令行）：
  python midi_to_melody.py 输入.mid -o 输出.bin -f 20

交互模式（直接运行，无参数）：
  python midi_to_melody.py
  然后根据提示选择 MIDI 文件并设置参数。
"""

import argparse
import struct
import sys
import os
import glob

try:
    import mido
except ImportError:
    print("错误：缺少 'mido' 库，请安装：pip install mido")
    sys.exit(1)

# ==================== 交互式输入辅助函数 ====================
def get_input(prompt, default=None, converter=str, validator=None):
    """带默认值和验证的交互输入。"""
    while True:
        if default is not None:
            user_input = input(f"{prompt} [默认: {default}]: ").strip()
        else:
            user_input = input(f"{prompt}: ").strip()
        if user_input == "" and default is not None:
            return default
        try:
            value = converter(user_input)
            if validator and not validator(value):
                print("输入无效，请重新输入。")
                continue
            return value
        except Exception:
            print("格式错误，请重新输入。")

def choose_file_from_dir(extension=".mid", prompt="请选择 MIDI 文件"):
    """列出当前目录下所有指定扩展名的文件，让用户选择编号。"""
    files = glob.glob(f"*{extension}") + glob.glob(f"*{extension.upper()}")
    if not files:
        print(f"当前目录下未找到任何 {extension} 文件。")
        return None
    print(f"\n{prompt}：")
    for i, f in enumerate(files):
        print(f"  [{i}] {f}")
    while True:
        choice = get_input("请输入文件编号", converter=int, validator=lambda x: 0 <= x < len(files))
        if choice is not None:
            return files[choice]

def confirm_overwrite(filepath):
    """如果文件已存在，询问是否覆盖。"""
    if os.path.exists(filepath):
        choice = input(f"文件 '{filepath}' 已存在，是否覆盖？(y/n): ").strip().lower()
        return choice == 'y'
    return True

# ==================== 核心转换函数 ====================
def midi_to_melody_bin(midi_path, bin_path, fps=20, method='highest'):
    """
    将 MIDI 文件转换为二进制旋律文件。
    参数：
        midi_path : 输入 MIDI 文件路径
        bin_path  : 输出二进制文件路径
        fps       : 视频帧率
        method    : 同时发声音符的处理方式（目前仅支持 'highest' 取最高音）
    """
    print(f"正在加载 MIDI 文件：{midi_path}")
    try:
        mid = mido.MidiFile(midi_path)
    except Exception as e:
        print(f"无法打开 MIDI 文件：{e}")
        sys.exit(1)

    ticks_per_beat = mid.ticks_per_beat
    tempo = 500000  # 默认 120 BPM（微秒/拍）

    # 收集所有音符事件 (时间_秒, 音符编号, 是否按下)
    notes = []
    for track in mid.tracks:
        track_time = 0.0
        for msg in track:
            delta = msg.time / ticks_per_beat * (tempo / 1_000_000.0)
            track_time += delta
            if msg.type == 'note_on' and msg.velocity > 0:
                notes.append((track_time, msg.note, True))
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                notes.append((track_time, msg.note, False))
            elif msg.type == 'set_tempo':
                tempo = msg.tempo

    notes.sort(key=lambda x: x[0])
    print(f"共收集到 {len(notes)} 个音符事件")

    # 构建音符段落 (开始时间, 结束时间, 音高)
    active = {}
    segments = []
    for t, note, onoff in notes:
        if onoff:
            if note not in active:
                active[note] = t
        else:
            if note in active:
                start = active.pop(note)
                segments.append((start, t, note))

    if not segments:
        print("警告：MIDI 文件中未找到任何完整的音符段落。")
        return

    print(f"共提取 {len(segments)} 个音符段落")

    # 确定总时长（最后一个音符的结束时间）
    total_duration = max(end for _, end, _ in segments)
    total_frames = int(total_duration * fps) + 1
    print(f"总时长：{total_duration:.2f} 秒，总帧数：{total_frames}")

    # 初始化每帧频率数组，0 表示静音
    frame_freq = [0.0] * total_frames

    # 填充每个音符段落的频率
    for start, end, note in segments:
        start_frame = int(start * fps)
        end_frame = int(end * fps)
        if end_frame > total_frames:
            end_frame = total_frames
        if start_frame >= total_frames:
            continue
        # 将 MIDI 音符编号转换为频率 (A4 = 440Hz)
        freq = 440.0 * (2.0 ** ((note - 69) / 12.0))
        for f in range(start_frame, end_frame):
            # 多个音符同时发声时，保留最高频率
            if method == 'highest' and freq > frame_freq[f]:
                frame_freq[f] = freq

    # 行程编码：合并连续相同频率的帧
    melody = []
    i = 0
    while i < total_frames:
        cur_freq = frame_freq[i]
        cnt = 1
        while i + cnt < total_frames and frame_freq[i + cnt] == cur_freq:
            cnt += 1
        freq_x10 = int(round(cur_freq * 10))
        melody.append((freq_x10, cnt))
        i += cnt

    # 写入二进制文件
    with open(bin_path, 'wb') as f:
        for freq_x10, frames in melody:
            f.write(struct.pack('<HH', freq_x10, frames))

    print(f"旋律二进制文件已保存至：{bin_path}")
    print(f"  片段总数：{len(melody)}")
    print(f"  文件大小：{os.path.getsize(bin_path)} 字节")
    # 预览前5个片段
    print("  前5个片段预览 (频率Hz, 帧数):")
    for j, (f_x10, frames) in enumerate(melody[:5]):
        print(f"    {f_x10/10:.1f} Hz, {frames} 帧")

# ==================== 交互式主函数 ====================
def interactive_main():
    """交互式模式：让用户选择文件和参数"""
    print("\n=== MIDI 转 melody.bin 交互工具 ===\n")

    # 1. 选择输入 MIDI 文件
    midi_file = choose_file_from_dir(".mid", "请选择 MIDI 文件")
    if midi_file is None:
        print("未选择任何文件，退出。")
        return

    # 2. 设置输出文件（默认同目录，同基本名）
    default_out = os.path.splitext(midi_file)[0] + ".bin"
    out_file = get_input("请输入输出文件路径", default_out, str)
    if not confirm_overwrite(out_file):
        print("操作取消。")
        return

    # 3. 设置 FPS
    fps = get_input("请输入视频帧率 (FPS)", 20, int, lambda x: x > 0 and x <= 1000)

    # 4. 设置方法（目前只有 highest）
    method = 'highest'

    # 5. 确认并执行
    print("\n请确认参数：")
    print(f"  MIDI 文件：{midi_file}")
    print(f"  输出文件：{out_file}")
    print(f"  FPS：{fps}")
    print(f"  多音处理：{method}")
    confirm = get_input("是否开始转换？(y/n)", "y", str, lambda x: x.lower() in ['y', 'n'])
    if confirm.lower() != 'y':
        print("已取消。")
        return

    midi_to_melody_bin(midi_file, out_file, fps, method)

# ==================== 命令行入口 ====================
def main():
    if len(sys.argv) == 1:
        interactive_main()
        return

    parser = argparse.ArgumentParser(
        description="将 MIDI 转换为 melody.bin，用于 ESP32-C3 Bad Apple 播放器",
        epilog="示例：%(prog)s badapple.mid -o melody.bin -f 20"
    )
    parser.add_argument('midi_file', nargs='?', help='输入的 MIDI 文件路径（留空则进入交互模式）')
    parser.add_argument('-o', '--output', help='输出的二进制文件路径（默认：输入文件名+.bin）')
    parser.add_argument('-f', '--fps', type=int, default=20, help='视频帧率（默认：20）')
    parser.add_argument('-m', '--method', default='highest',
                        choices=['highest'], help='同时音符的处理方式（默认：highest 最高音）')
    parser.add_argument('--version', action='version', version='midi_to_melody 1.0')

    args = parser.parse_args()

    if args.midi_file:
        if not os.path.exists(args.midi_file):
            print(f"错误：MIDI 文件 '{args.midi_file}' 未找到。")
            sys.exit(1)

        if args.output is None:
            base = os.path.splitext(args.midi_file)[0]
            args.output = base + '.bin'

        if not confirm_overwrite(args.output):
            print("操作取消。")
            return

        midi_to_melody_bin(args.midi_file, args.output, args.fps, args.method)
    else:
        interactive_main()

if __name__ == '__main__':
    main()