"""
认证管理模块
支持固定密码和动态验证码两种认证模式
"""
import random
import string
import time
import json
import os
import threading

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_config.json")

# 默认配置
DEFAULT_CONFIG = {
    "mode": "dynamic",  # "fixed" 固定密码 / "dynamic" 动态验证码
    "fixed_password": "123456",
    "code_length": 6,  # 动态验证码长度
    "code_expire_seconds": 300,  # 验证码有效期（秒）
}


class AuthManager:
    """认证管理器，管理连接密码和动态验证码"""

    def __init__(self):
        self._lock = threading.Lock()
        self._config = dict(DEFAULT_CONFIG)
        self._dynamic_code = ""
        self._code_generated_at = 0
        self._authenticated_tokens = {}  # token -> expire_time
        self._load_config()
        self._generate_code()

    def _load_config(self):
        """从文件加载配置"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self._config.update(saved)
            except Exception:
                pass

    def save_config(self):
        """保存配置到文件"""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _generate_code(self):
        """生成新的动态验证码"""
        with self._lock:
            self._dynamic_code = ''.join(
                random.choices(string.digits, k=self._config["code_length"])
            )
            self._code_generated_at = time.time()
        return self._dynamic_code

    def refresh_code(self):
        """刷新动态验证码"""
        return self._generate_code()

    @property
    def mode(self):
        return self._config["mode"]

    @mode.setter
    def mode(self, value):
        if value in ("fixed", "dynamic"):
            self._config["mode"] = value
            self.save_config()

    @property
    def fixed_password(self):
        return self._config["fixed_password"]

    @fixed_password.setter
    def fixed_password(self, value):
        self._config["fixed_password"] = value
        self.save_config()

    @property
    def current_code(self):
        """获取当前动态验证码，过期则自动刷新"""
        with self._lock:
            elapsed = time.time() - self._code_generated_at
            if elapsed > self._config["code_expire_seconds"]:
                self._generate_code()
            return self._dynamic_code

    def verify(self, password: str) -> bool:
        """验证密码/验证码是否正确"""
        if self._config["mode"] == "fixed":
            return password == self._config["fixed_password"]
        else:
            with self._lock:
                elapsed = time.time() - self._code_generated_at
                if elapsed > self._config["code_expire_seconds"]:
                    return False
                return password == self._dynamic_code

    def generate_token(self) -> str:
        """验证通过后生成会话令牌"""
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        # 令牌有效期24小时
        self._authenticated_tokens[token] = time.time() + 86400
        self._cleanup_tokens()
        return token

    def verify_token(self, token: str) -> bool:
        """验证令牌是否有效"""
        if not token:
            return False
        expire = self._authenticated_tokens.get(token)
        if expire is None:
            return False
        if time.time() > expire:
            del self._authenticated_tokens[token]
            return False
        return True

    def revoke_token(self, token: str):
        """撤销令牌"""
        self._authenticated_tokens.pop(token, None)

    def _cleanup_tokens(self):
        """清理过期令牌"""
        now = time.time()
        expired = [k for k, v in self._authenticated_tokens.items() if now > v]
        for k in expired:
            del self._authenticated_tokens[k]

    def get_display_info(self) -> dict:
        """获取用于状态窗口显示的信息"""
        return {
            "mode": self._config["mode"],
            "code": self.current_code if self._config["mode"] == "dynamic" else None,
            "fixed_password": self._config["fixed_password"] if self._config["mode"] == "fixed" else None,
        }
