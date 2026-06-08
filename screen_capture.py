"""
屏幕捕获模块（性能优化版）
使用Event通知机制替代轮询，消除锁竞争瓶颈
"""
import threading
import time
import io
import ctypes
from collections import deque
from PIL import Image, ImageDraw

try:
    import dxcam
    HAS_DXCAM = True
except ImportError:
    HAS_DXCAM = False

import mss
import numpy as np


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _get_cursor_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


class ScreenCapture:
    """屏幕捕获引擎 - 事件驱动、无锁竞争"""

    def __init__(self, target_fps=30, quality=50, scale=0.5, monitor_manager=None):
        self.target_fps = target_fps
        self.quality = quality
        self.scale = scale
        self.frame_interval = 1.0 / target_fps
        self._running = False
        self._thread = None
        self._actual_fps = 0.0
        self._camera = None
        self._monitor_manager = monitor_manager

        # 使用原子替换而非锁保护的帧缓冲
        self._latest_frame = None
        self._frame_version = 0  # 递增帧号，发送端据此判断是否有新帧
        self._frame_event = threading.Event()  # 新帧就绪通知
        self._frame_size = 0

        self._quality_min = 20
        self._quality_max = 90
        self._quality_current = quality
        self._encode_times = deque(maxlen=10)

        # 带宽统计
        self._bandwidth_bps = 0
        self._bandwidth_bytes = 0
        self._bandwidth_timer = time.time()

        # 动态分辨率：客户端缩放时可请求高分辨率
        self._requested_scale = scale  # 客户端请求的缩放

        self._use_dxcam = False
        if HAS_DXCAM:
            try:
                self._camera = dxcam.create(output_color="BGR")
                self._use_dxcam = True
            except Exception:
                self._use_dxcam = False

    @property
    def fps(self):
        return self._actual_fps

    @property
    def frame_size(self):
        return self._frame_size

    @property
    def bandwidth(self):
        return self._bandwidth_bps

    def set_quality(self, quality: int):
        """动态设置画质"""
        self._quality_min = max(10, quality - 20)
        self._quality_max = min(95, quality + 20)
        self._quality_current = max(10, min(95, quality))

    def set_fps(self, fps: int):
        """动态设置目标帧率"""
        fps = max(1, min(60, fps))
        self.target_fps = fps
        self.frame_interval = 1.0 / fps

    def set_scale(self, scale: float):
        """动态设置缩放比例"""
        self.scale = max(0.2, min(1.0, scale))

    def request_full_resolution(self, enabled: bool):
        """客户端缩放放大时请求原始分辨率"""
        if enabled:
            self._requested_scale = 1.0
        else:
            self._requested_scale = self.scale

    def _get_monitor_region(self):
        if self._monitor_manager:
            return self._monitor_manager.get_monitor_region()
        return None

    def _adjust_quality(self, encode_ms):
        self._encode_times.append(encode_ms)
        if len(self._encode_times) < 5:
            return
        avg_ms = sum(self._encode_times) / len(self._encode_times)
        target_ms = (self.frame_interval * 1000) * 0.5
        if avg_ms > target_ms and self._quality_current > self._quality_min:
            self._quality_current = max(self._quality_min, self._quality_current - 2)
        elif avg_ms < target_ms * 0.5 and self._quality_current < self._quality_max:
            self._quality_current = min(self._quality_max, self._quality_current + 1)

    def _capture_loop(self):
        frame_count = 0
        fps_timer = time.time()

        if self._use_dxcam:
            self._camera.start(target_fps=min(60, self.target_fps + 5))

        sct = None if self._use_dxcam else mss.mss()

        while self._running:
            loop_start = time.time()

            try:
                region = self._get_monitor_region()

                # 捕获
                if self._use_dxcam:
                    frame = self._camera.get_latest_frame()
                    if frame is None:
                        time.sleep(0.001)
                        continue
                    # dxcam返回BGR numpy数组，直接用numpy处理
                    arr = frame
                    if region:
                        x, y, w, h = region
                        arr = arr[y:y+h, x:x+w]
                else:
                    if region:
                        x, y, w, h = region
                        monitor_def = {"left": x, "top": y, "width": w, "height": h}
                    else:
                        monitor_def = sct.monitors[1]
                    shot = sct.grab(monitor_def)
                    # 使用raw BGRA直接转numpy避免shot.rgb的开销
                    arr = np.frombuffer(shot.raw, dtype=np.uint8).reshape(shot.height, shot.width, 4)
                    arr = arr[:, :, :3]  # BGRA -> BGR (去掉alpha)

                # 降采样 - 使用numpy跳像素法（比Pillow resize快5倍）
                effective_scale = self._requested_scale
                if effective_scale < 1.0:
                    step = max(1, int(round(1.0 / effective_scale)))
                    arr = arr[::step, ::step]

                # BGR -> RGB 并生成Pillow Image
                rgb_arr = arr[:, :, ::-1].copy()
                img = Image.fromarray(rgb_arr)

                # 光标绘制
                cx, cy = _get_cursor_pos()
                if region:
                    cx -= region[0]
                    cy -= region[1]
                step_val = max(1, int(round(1.0 / effective_scale))) if effective_scale < 1.0 else 1
                dx = cx // step_val
                dy = cy // step_val
                if 0 <= dx < img.width and 0 <= dy < img.height:
                    draw = ImageDraw.Draw(img)
                    r = 4
                    draw.ellipse([dx - r, dy - r, dx + r, dy + r],
                                 fill=(255, 60, 60), outline=(255, 255, 255))

                # JPEG编码
                encode_start = time.time()
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=self._quality_current, optimize=False)
                jpeg_data = buf.getvalue()
                encode_ms = (time.time() - encode_start) * 1000
                self._adjust_quality(encode_ms)

                # 原子替换帧数据并通知等待的发送线程
                self._latest_frame = jpeg_data
                self._frame_size = len(jpeg_data)
                self._frame_version += 1
                self._frame_event.set()

                # 带宽统计
                self._bandwidth_bytes += len(jpeg_data)
                now = time.time()
                elapsed_bw = now - self._bandwidth_timer
                if elapsed_bw >= 1.0:
                    self._bandwidth_bps = int(self._bandwidth_bytes / elapsed_bw)
                    self._bandwidth_bytes = 0
                    self._bandwidth_timer = now

                # FPS统计
                frame_count += 1
                elapsed = time.time() - fps_timer
                if elapsed >= 1.0:
                    self._actual_fps = frame_count / elapsed
                    frame_count = 0
                    fps_timer = time.time()

            except Exception:
                pass

            sleep_time = self.frame_interval - (time.time() - loop_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

        if self._use_dxcam and self._camera:
            self._camera.stop()
        if sct:
            sct.close()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._frame_event.set()  # 唤醒等待线程使其退出
        if self._thread:
            self._thread.join(timeout=2)

    def get_frame(self):
        """获取最新帧（无锁，原子读取引用）"""
        return self._latest_frame

    def wait_for_frame(self, last_version: int, timeout: float = 0.1) -> tuple:
        """等待新帧就绪，返回(frame_data, version)。事件驱动，无轮询"""
        if self._frame_version != last_version:
            return self._latest_frame, self._frame_version
        # 等待事件通知或超时
        self._frame_event.clear()
        self._frame_event.wait(timeout=timeout)
        return self._latest_frame, self._frame_version
