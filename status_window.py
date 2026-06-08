"""
桌面状态窗口（升级版）
显示连接数、帧率、认证信息
"""
import tkinter as tk
import threading


class StatusWindow:
    """桌面悬浮状态窗口"""

    def __init__(self):
        self._connections = 0
        self._fps = 0.0
        self._auth_info = ""
        self._running = False
        self._root = None

    def _build(self):
        self._root = tk.Tk()
        self._root.title("MyConnect 状态")
        self._root.geometry("260x110+20+20")
        self._root.attributes("-topmost", True)
        self._root.resizable(False, False)
        self._root.configure(bg="#1a1a2e")

        self._title_label = tk.Label(self._root, text="MyConnect v2.0",
                                     font=("Microsoft YaHei", 10, "bold"),
                                     bg="#1a1a2e", fg="#58a6ff")
        self._title_label.pack(pady=(8, 2))

        self._conn_label = tk.Label(self._root, text="连接数: 0",
                                    font=("Microsoft YaHei", 10),
                                    bg="#1a1a2e", fg="#e6edf3")
        self._conn_label.pack(pady=1)

        self._fps_label = tk.Label(self._root, text="帧率: 0.0 FPS",
                                   font=("Microsoft YaHei", 10),
                                   bg="#1a1a2e", fg="#e6edf3")
        self._fps_label.pack(pady=1)

        self._auth_label = tk.Label(self._root, text="",
                                    font=("Microsoft YaHei", 9),
                                    bg="#1a1a2e", fg="#3fb950")
        self._auth_label.pack(pady=1)

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._update_loop()

    def _update_loop(self):
        if not self._running:
            return
        self._conn_label.config(text=f"连接数: {self._connections}")
        self._fps_label.config(text=f"帧率: {self._fps:.1f} FPS")
        if self._auth_info:
            self._auth_label.config(text=self._auth_info)
        self._root.after(500, self._update_loop)

    def _on_close(self):
        self._running = False
        self._root.destroy()

    def update(self, connections: int, fps: float):
        self._connections = connections
        self._fps = fps

    def set_auth_info(self, info: str):
        """设置认证信息显示"""
        self._auth_info = info

    def start(self):
        self._running = True
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        self._build()
        self._root.mainloop()
