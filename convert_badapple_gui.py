#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bad Apple 视频压缩工具 (MicroPython 兼容版)
将 MP4 视频转换为 ESP32-C3 可播放的压缩二进制文件。
格式：每帧前 2 字节（小端）为压缩数据长度，后面紧跟 zlib 压缩数据。
"""

import cv2
import numpy as np
import zlib
import struct
import os
import time

def get_input(prompt, default, converter=str, validator=None):
    """带验证和默认值的交互输入函数。"""
    while True:
        user_input = input(f"{prompt} [默认: {default}]: ").strip()
        if user_input == "":
            return default
        try:
            value = converter(user_input)
            if validator and not validator(value):
                print("输入无效，请重新输入。")
                continue
            return value
        except Exception:
            print("格式错误，请重新输入。")

def confirm_overwrite(filepath):
    """如果文件已存在，询问是否覆盖。"""
    if os.path.exists(filepath):
        choice = input(f"文件 '{filepath}' 已存在，是否覆盖？(y/n): ").strip().lower()
        return choice == 'y'
    return True

def compress_video(video_path: str, target_fps: int, level: int,
                   width: int, height: int, out_path: str,
                   use_otsu: bool = False, use_median: bool = False):
    """压缩视频主函数。"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError("无法打开视频文件")

    orig_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = max(1, int(round(orig_fps / target_fps)))
    out_frames = total_frames // frame_interval
    print(f"原始帧率: {orig_fps:.2f}, 采样间隔: {frame_interval}, 预计输出帧数: {out_frames}")

    with open(out_path, "wb") as f:
        frame_count = 0
        saved_frames = 0
        total_raw = 0
        total_comp = 0
        start_time = time.time()

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                # 灰度化
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                # 可选：中值滤波降噪
                if use_median:
                    gray = cv2.medianBlur(gray, 3)
                # 缩放
                resized = cv2.resize(gray, (width, height))
                # 二值化
                if use_otsu:
                    _, binary = cv2.threshold(resized, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                else:
                    binary = (resized > 128).astype(np.uint8)
                # 打包为每字节8像素
                packed = np.packbits(binary, axis=1)
                raw_bytes = packed.tobytes()
                total_raw += len(raw_bytes)

                comp = zlib.compress(raw_bytes, level=level)
                total_comp += len(comp)

                f.write(struct.pack('<H', len(comp)))
                f.write(comp)

                saved_frames += 1
                # 进度显示
                elapsed = time.time() - start_time
                if saved_frames > 0:
                    eta = (elapsed / saved_frames) * (out_frames - saved_frames)
                    print(f"\r已处理 {saved_frames}/{out_frames} 帧 | 已用 {elapsed:.1f}s | 剩余 {eta:.1f}s", end='')

            frame_count += 1

    cap.release()
    print("\n处理完成！")
    ratio = total_raw / total_comp if total_comp else 0
    print(f"输出帧数: {saved_frames}")
    print(f"原始单色数据大小: {total_raw/1024/1024:.2f} MB")
    print(f"压缩后大小: {total_comp/1024/1024:.2f} MB")
    print(f"压缩比: {ratio:.2f} : 1")

def main():
    print("=" * 50)
    print("   Bad Apple 视频压缩工具 (MicroPython 兼容版)   ")
    print("=" * 50)

    # 1. 选择 MP4 文件
    default_video = "badapple.mp4"
    while True:
        video_path = get_input("请输入 MP4 文件路径", default_video, str)
        if not os.path.exists(video_path):
            print("文件不存在，请重新输入。")
            continue
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("无法打开视频文件。")
            continue
        duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        print(f"🎬 视频时长：{duration:.2f} 秒")
        break

    # 2. 目标帧率
    target_fps = get_input("请输入目标帧率 (FPS)", 20, int, lambda x: 1 <= x <= 120)

    # 3. 压缩级别
    level = get_input("请输入压缩级别 (0-9)", 9, int, lambda x: 0 <= x <= 9)

    # 4. 输出文件名
    default_out = "badapple_gzip.bin"
    out_path = get_input("请输入输出文件名", default_out, str)
    # 确保扩展名为 .bin
    if not out_path.lower().endswith('.bin'):
        out_path += '.bin'
    if not confirm_overwrite(out_path):
        print("操作取消。")
        return

    # 5. 屏幕尺寸
    width = get_input("请输入屏幕宽度", 128, int, lambda x: x > 0)
    height = get_input("请输入屏幕高度", 160, int, lambda x: x > 0)

    # 6. 预处理选项
    print("\n🔧 预处理选项（可提高压缩率）")
    use_otsu = get_input("使用 Otsu 自动阈值？(y/n)", "y", str, lambda x: x.lower() in 'yn').lower() == 'y'
    use_median = get_input("使用中值滤波降噪？(y/n)", "n", str, lambda x: x.lower() in 'yn').lower() == 'y'

    # 执行压缩
    try:
        compress_video(video_path, target_fps, level, width, height, out_path, use_otsu, use_median)
        print(f"文件已保存至: {out_path}")
    except Exception as e:
        print(f"压缩过程中出现错误: {e}")

if __name__ == "__main__":
    main()