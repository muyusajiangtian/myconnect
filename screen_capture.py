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
    def __init__(self, target_fps=30, quality=50, scale=0.5):
        self.target_fps = target_fps
        self.quality = quality
        self.scale = scale
        self.frame_interval = 1.0 / target_fps
        self._running = False
        self._thread = None
        self._actual_fps = 0.0
        self._camera = None

        self._frame_lock = threading.Lock()
        self._latest_frame = None

        self._quality_min = 30
        self._quality_max = 70
        self._quality_current = quality
        self._encode_times = deque(maxlen=10)

        if HAS_DXCAM:
            try:
                self._camera = dxcam.create(output_color="BGR")
                self._use_dxcam = True
            except Exception:
                self._use_dxcam = False
        else:
            self._use_dxcam = False

    @property
    def fps(self):
        return self._actual_fps

    def _adjust_quality(self, encode_ms):
        self._encode_times.append(encode_ms)
        if len(self._encode_times) < 5:
            return

        avg_ms = sum(self._encode_times) / len(self._encode_times)
        target_ms = (self.frame_interval * 1000) * 0.4

        if avg_ms > target_ms and self._quality_current > self._quality_min:
            self._quality_current = max(self._quality_min, self._quality_current - 3)
        elif avg_ms < target_ms * 0.6 and self._quality_current < self._quality_max:
            self._quality_current = min(self._quality_max, self._quality_current + 1)

    def _capture_loop(self):
        frame_count = 0
        fps_timer = time.time()

        if self._use_dxcam:
            self._camera.start(target_fps=self.target_fps)

        sct = None if self._use_dxcam else mss.mss()

        while self._running:
            loop_start = time.time()

            try:
                if self._use_dxcam:
                    frame = self._camera.get_latest_frame()
                    if frame is None:
                        time.sleep(0.001)
                        continue
                    img = Image.fromarray(frame[:, :, ::-1])
                else:
                    monitor = sct.monitors[1]
                    shot = sct.grab(monitor)
                    img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)

                if self.scale != 1.0:
                    new_size = (int(img.width * self.scale), int(img.height * self.scale))
                    img = img.resize(new_size, Image.NEAREST)

                cx, cy = _get_cursor_pos()
                dx = int(cx * self.scale)
                dy = int(cy * self.scale)
                draw = ImageDraw.Draw(img)
                r = 5
                draw.ellipse([dx - r, dy - r, dx + r, dy + r], fill=(255, 60, 60), outline=(255, 255, 255))

                encode_start = time.time()
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=self._quality_current, optimize=False)
                jpeg_data = buf.getvalue()
                encode_ms = (time.time() - encode_start) * 1000

                self._adjust_quality(encode_ms)

                with self._frame_lock:
                    self._latest_frame = jpeg_data

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
        if self._thread:
            self._thread.join(timeout=2)

    def get_frame(self):
        with self._frame_lock:
            return self._latest_frame
