"""
文件传输模块
支持浏览目录、下载文件到手机、电脑推送文件到手机端
"""
import os
import mimetypes
import hashlib
import threading
from pathlib import Path

# 默认共享目录（用户桌面）
DEFAULT_SHARE_DIR = os.path.join(os.path.expanduser("~"), "Desktop")

# 上传文件临时存储目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")


class FileManager:
    """文件管理器，处理文件浏览、下载和上传"""

    def __init__(self, share_dirs=None):
        # 可浏览的共享目录列表
        self._share_dirs = share_dirs or [DEFAULT_SHARE_DIR]
        self._lock = threading.Lock()
        # 确保上传目录存在
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        # 待推送到手机的文件队列
        self._push_queue = []

    @property
    def share_dirs(self):
        return list(self._share_dirs)

    def add_share_dir(self, path: str):
        """添加共享目录"""
        abs_path = os.path.abspath(path)
        if os.path.isdir(abs_path) and abs_path not in self._share_dirs:
            self._share_dirs.append(abs_path)

    def remove_share_dir(self, path: str):
        """移除共享目录"""
        abs_path = os.path.abspath(path)
        if abs_path in self._share_dirs and len(self._share_dirs) > 1:
            self._share_dirs.remove(abs_path)

    def _is_path_allowed(self, filepath: str) -> bool:
        """检查路径是否在允许的共享目录中"""
        abs_path = os.path.abspath(filepath)
        for share_dir in self._share_dirs:
            if abs_path.startswith(os.path.abspath(share_dir)):
                return True
        return False

    def list_directory(self, path: str = None) -> dict:
        """列出目录内容"""
        # 默认列出所有共享目录的根
        if path is None:
            return {
                "type": "root",
                "dirs": [
                    {"name": os.path.basename(d) or d, "path": d}
                    for d in self._share_dirs
                ]
            }

        abs_path = os.path.abspath(path)
        if not self._is_path_allowed(abs_path):
            return {"error": "访问被拒绝", "type": "error"}

        if not os.path.isdir(abs_path):
            return {"error": "目录不存在", "type": "error"}

        items = []
        try:
            for entry in os.scandir(abs_path):
                try:
                    stat = entry.stat()
                    item = {
                        "name": entry.name,
                        "path": entry.path.replace("\\", "/"),
                        "is_dir": entry.is_dir(),
                        "size": stat.st_size if not entry.is_dir() else 0,
                        "mtime": int(stat.st_mtime),
                    }
                    if not entry.is_dir():
                        item["ext"] = os.path.splitext(entry.name)[1].lower()
                    items.append(item)
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError) as e:
            return {"error": f"无法读取目录: {str(e)}", "type": "error"}

        # 排序：目录优先，然后按名称
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        return {
            "type": "listing",
            "path": abs_path.replace("\\", "/"),
            "parent": os.path.dirname(abs_path).replace("\\", "/"),
            "items": items,
        }

    def get_file_info(self, filepath: str) -> dict:
        """获取文件详情"""
        if not self._is_path_allowed(filepath):
            return {"error": "访问被拒绝"}

        abs_path = os.path.abspath(filepath)
        if not os.path.isfile(abs_path):
            return {"error": "文件不存在"}

        stat = os.stat(abs_path)
        mime_type, _ = mimetypes.guess_type(abs_path)

        return {
            "name": os.path.basename(abs_path),
            "path": abs_path.replace("\\", "/"),
            "size": stat.st_size,
            "mtime": int(stat.st_mtime),
            "mime_type": mime_type or "application/octet-stream",
        }

    def get_file_path(self, filepath: str) -> str:
        """获取文件绝对路径（下载用），验证权限"""
        abs_path = os.path.abspath(filepath)
        if not self._is_path_allowed(abs_path):
            return None
        if not os.path.isfile(abs_path):
            return None
        return abs_path

    def save_uploaded_file(self, filename: str, data: bytes) -> dict:
        """保存手机上传的文件"""
        safe_name = os.path.basename(filename)
        save_path = os.path.join(UPLOAD_DIR, safe_name)

        # 同名文件自动重命名
        if os.path.exists(save_path):
            name, ext = os.path.splitext(safe_name)
            counter = 1
            while os.path.exists(save_path):
                save_path = os.path.join(UPLOAD_DIR, f"{name}_{counter}{ext}")
                counter += 1

        with open(save_path, "wb") as f:
            f.write(data)

        return {
            "success": True,
            "path": save_path.replace("\\", "/"),
            "size": len(data),
        }

    def push_file_to_client(self, filepath: str) -> dict:
        """将电脑文件加入推送队列"""
        abs_path = os.path.abspath(filepath)
        if not os.path.isfile(abs_path):
            return {"error": "文件不存在"}

        with self._lock:
            self._push_queue.append(abs_path)

        return {"success": True, "file": os.path.basename(abs_path)}

    def get_push_queue(self) -> list:
        """获取并清空推送队列"""
        with self._lock:
            queue = list(self._push_queue)
            self._push_queue.clear()
        return queue

    @staticmethod
    def format_size(size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024*1024):.1f} MB"
        else:
            return f"{size / (1024*1024*1024):.2f} GB"
