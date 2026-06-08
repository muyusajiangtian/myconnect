"""
剪贴板双向同步模块
监控电脑剪贴板变化，推送到手机端；接收手机端剪贴板内容写入电脑
"""
import threading
import time
import ctypes
import ctypes.wintypes
import platform

IS_WINDOWS = platform.system() == "Windows"


class ClipboardSync:
    """剪贴板双向同步管理器"""

    def __init__(self):
        self._running = False
        self._thread = None
        self._last_content = ""
        self._lock = threading.Lock()
        # 回调函数列表，剪贴板变化时通知所有客户端
        self._callbacks = []
        # 记录上次由程序设置的内容，避免回环
        self._last_set_by_us = ""

    def start(self):
        """启动剪贴板监控线程"""
        if self._running:
            return
        self._running = True
        self._last_content = self._get_clipboard() or ""
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def register_callback(self, callback):
        """注册剪贴板变化回调 callback(text: str)"""
        with self._lock:
            self._callbacks.append(callback)

    def unregister_callback(self, callback):
        """取消注册回调"""
        with self._lock:
            self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    def set_clipboard(self, text: str):
        """从手机端设置电脑剪贴板内容"""
        with self._lock:
            self._last_set_by_us = text
            self._last_content = text
        self._write_clipboard(text)

    def get_clipboard(self) -> str:
        """获取当前电脑剪贴板文本"""
        return self._get_clipboard() or ""

    def _monitor_loop(self):
        """轮询检测剪贴板变化"""
        while self._running:
            try:
                current = self._get_clipboard()
                if current and current != self._last_content:
                    with self._lock:
                        # 如果是我们自己设置的，跳过通知
                        if current == self._last_set_by_us:
                            self._last_content = current
                            self._last_set_by_us = ""
                        else:
                            self._last_content = current
                            callbacks = list(self._callbacks)
                    # 通知所有客户端
                    if current != self._last_set_by_us:
                        for cb in callbacks:
                            try:
                                cb(current)
                            except Exception:
                                pass
            except Exception:
                pass
            time.sleep(0.5)

    def _get_clipboard(self) -> str:
        """读取系统剪贴板文本"""
        if not IS_WINDOWS:
            return ""
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            CF_UNICODETEXT = 13

            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            user32.GetClipboardData.restype = ctypes.c_void_p

            if not user32.OpenClipboard(0):
                return ""
            try:
                h_data = user32.GetClipboardData(CF_UNICODETEXT)
                if not h_data:
                    return ""
                p_data = kernel32.GlobalLock(h_data)
                if not p_data:
                    return ""
                try:
                    return ctypes.wstring_at(p_data)
                finally:
                    kernel32.GlobalUnlock(h_data)
            finally:
                user32.CloseClipboard()
        except Exception:
            return ""

    def _write_clipboard(self, text: str):
        """写入系统剪贴板"""
        if not IS_WINDOWS:
            return
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            kernel32.GlobalAlloc.restype = ctypes.c_void_p
            kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

            text_bytes = text.encode("utf-16-le") + b"\x00\x00"
            buf_size = len(text_bytes)

            if not user32.OpenClipboard(0):
                return
            user32.EmptyClipboard()

            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, buf_size)
            if not h_mem:
                user32.CloseClipboard()
                return
            p_mem = kernel32.GlobalLock(h_mem)
            ctypes.memmove(p_mem, text_bytes, buf_size)
            kernel32.GlobalUnlock(h_mem)

            user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            user32.CloseClipboard()
        except Exception:
            pass
