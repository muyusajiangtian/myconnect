import tkinter as tk
import threading


class StatusWindow:
    def __init__(self):
        self._connections = 0
        self._fps = 0.0
        self._running = False
        self._root = None

    def _build(self):
        self._root = tk.Tk()
        self._root.title("遥控状态")
        self._root.geometry("220x80+20+20")
        self._root.attributes("-topmost", True)
        self._root.resizable(False, False)

        self._conn_label = tk.Label(self._root, text="连接数: 0", font=("Microsoft YaHei", 11))
        self._conn_label.pack(pady=(10, 2))

        self._fps_label = tk.Label(self._root, text="帧率: 0.0 FPS", font=("Microsoft YaHei", 11))
        self._fps_label.pack(pady=2)

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._update_loop()

    def _update_loop(self):
        if not self._running:
            return
        self._conn_label.config(text=f"连接数: {self._connections}")
        self._fps_label.config(text=f"帧率: {self._fps:.1f} FPS")
        self._root.after(500, self._update_loop)

    def _on_close(self):
        self._running = False
        self._root.destroy()

    def update(self, connections: int, fps: float):
        self._connections = connections
        self._fps = fps

    def start(self):
        self._running = True
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        self._build()
        self._root.mainloop()
