"""
多显示器管理模块
枚举系统所有显示器，支持切换当前操控的屏幕
"""
import ctypes
import ctypes.wintypes
import threading
import platform

IS_WINDOWS = platform.system() == "Windows"

# 手动定义 MONITORINFOEXW 结构体（ctypes.wintypes中没有）
if IS_WINDOWS:
    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.DWORD),
            ("rcMonitor", ctypes.wintypes.RECT),
            ("rcWork", ctypes.wintypes.RECT),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("szDevice", ctypes.c_wchar * 32),
        ]


class MonitorInfo:
    """显示器信息"""
    def __init__(self, index, name, x, y, width, height, is_primary=False):
        self.index = index
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.is_primary = is_primary

    def to_dict(self):
        return {
            "index": self.index,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "is_primary": self.is_primary,
        }


class MonitorManager:
    """多显示器管理器"""

    def __init__(self):
        self._monitors = []
        self._current_index = 0
        self._lock = threading.Lock()
        self.refresh()

    def refresh(self):
        """刷新显示器列表"""
        monitors = []
        if IS_WINDOWS:
            monitors = self._enumerate_windows_monitors()

        with self._lock:
            self._monitors = monitors
            if self._current_index >= len(self._monitors):
                self._current_index = 0

    def _enumerate_windows_monitors(self) -> list:
        """枚举Windows显示器"""
        monitors = []

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            rect = lprcMonitor.contents
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(info)
            ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(info))

            x = rect.left
            y = rect.top
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            is_primary = bool(info.dwFlags & 1)
            name = info.szDevice or ""

            monitors.append(MonitorInfo(
                index=len(monitors),
                name=name,
                x=x, y=y,
                width=width, height=height,
                is_primary=is_primary,
            ))
            return True

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.wintypes.RECT),
            ctypes.c_double
        )
        proc = MONITORENUMPROC(callback)
        ctypes.windll.user32.EnumDisplayMonitors(None, None, proc, 0)

        # 按位置排序
        monitors.sort(key=lambda m: (m.x, m.y))
        for i, m in enumerate(monitors):
            m.index = i
            if not m.name or m.name.startswith("\\\\.\\"):
                m.name = f"Monitor {i + 1}" + (" (Primary)" if m.is_primary else "")

        return monitors

    @property
    def monitors(self) -> list:
        """获取显示器列表"""
        with self._lock:
            return list(self._monitors)

    @property
    def current_index(self) -> int:
        return self._current_index

    @current_index.setter
    def current_index(self, value: int):
        with self._lock:
            if 0 <= value < len(self._monitors):
                self._current_index = value

    @property
    def current_monitor(self) -> MonitorInfo:
        """获取当前选择的显示器"""
        with self._lock:
            if self._monitors:
                return self._monitors[self._current_index]
            # 回退：返回默认主屏幕
            return MonitorInfo(0, "默认", 0, 0, 1920, 1080, True)

    def get_monitor_region(self) -> tuple:
        """获取当前显示器的截图区域 (x, y, width, height)"""
        m = self.current_monitor
        return (m.x, m.y, m.width, m.height)

    def get_monitors_info(self) -> list:
        """获取所有显示器信息（用于发送到客户端）"""
        with self._lock:
            return [m.to_dict() for m in self._monitors]
