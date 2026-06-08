# MyConnect 手机遥控电脑 v2.0

一款局域网内手机远程控制电脑的工具，对标向日葵/ToDesk，支持屏幕实时投射、鼠标键盘操控、文件传输、剪贴板同步等功能。

A LAN-based remote desktop control tool that allows mobile phones to control PCs, featuring real-time screen streaming, mouse/keyboard control, file transfer, clipboard sync, and more.

---

## 功能特性 / Features

### 🔐 连接认证 / Authentication
- 支持**固定密码**和**动态验证码**两种模式
- 动态验证码每5分钟自动刷新
- 会话令牌机制，避免重复输入
- Supports **fixed password** and **dynamic code** modes
- Dynamic code auto-refreshes every 5 minutes

### 🖥 多显示器 / Multi-Monitor
- 自动枚举所有连接的显示器
- 手机端可选择查看和操控任一屏幕
- Auto-detects all connected monitors
- Switch between screens from mobile

### 📁 文件传输 / File Transfer
- 手机端可浏览电脑指定目录的文件列表
- 支持文件下载到手机
- 支持手机上传文件到电脑
- Browse PC directories from mobile
- Download files to phone / Upload files to PC

### 📋 剪贴板同步 / Clipboard Sync
- 电脑复制的文字自动推送到手机端
- 手机端可将文字同步到电脑剪贴板
- PC clipboard changes auto-pushed to mobile
- Mobile can sync text to PC clipboard

### 🎮 触控操作 / Touch Controls
- **单指拖动**：移动鼠标
- **单指轻触**：左键点击
- **长按**：右键点击（含震动反馈）
- **双指滑动**：滚轮滚动
- **双指缩放**：画面缩放
- Single finger drag = mouse move
- Tap = left click, Long press = right click
- Two finger scroll, Pinch to zoom

### ⌨ 虚拟键盘 / Virtual Keyboard
- 完整虚拟按键区（Ctrl/Alt/Shift/Win + 功能键）
- 常用快捷键一键发送（复制/粘贴/全选/切窗等）
- 支持中文IME输入法
- Full modifier keys + function key bar
- One-tap shortcuts (Copy/Paste/Select All/Alt+Tab)
- CJK IME input support

### 📊 画质帧率调节 / Quality & FPS Control
- 画质滑块：10-90 可调
- 帧率滑块：5-60 FPS 可调
- 缩放比例：0.3-1.0 可调
- 自适应画质算法
- Quality slider: 10-90
- FPS slider: 5-60
- Scale slider: 0.3-1.0
- Adaptive quality algorithm

### 📈 连接信息 / Connection Info
- 实时显示网络延迟（RTT）
- 实时显示带宽占用
- 当前帧率显示
- Real-time latency (RTT) display
- Bandwidth usage monitoring
- Current FPS display

---

## 环境依赖 / Requirements

- Python 3.8+
- Windows 10/11（推荐）
- 手机与电脑在同一局域网

### Python 依赖
```
flask>=2.3.0
flask-sock>=0.7.0
simple-websocket>=0.10.0
mss>=9.0.0
pyautogui>=0.9.54
Pillow>=10.0.0
numpy>=1.24.0
```

可选（推荐安装，性能更好）：
```
pip install dxcam
```

---

## 安装与运行 / Installation & Usage

### 方式一：一键启动
```bash
# 双击 start.bat 即可自动安装依赖并启动
start.bat
```

### 方式二：手动运行
```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python server.py
```

### 手机连接
1. 确保手机和电脑在同一WiFi网络下
2. 服务启动后会显示局域网地址（如 `http://192.168.1.100:9000`）
3. 手机浏览器访问该地址
4. 输入验证码/密码连接

---

## 项目结构 / Project Structure

```
myconnect/
├── server.py            # 主服务端，整合所有模块
├── screen_capture.py    # 屏幕捕获引擎（多显示器+自适应画质）
├── input_handler.py     # 远程输入处理（鼠标/键盘/文本）
├── auth_manager.py      # 认证管理（密码/验证码/令牌）
├── file_manager.py      # 文件传输管理
├── clipboard_sync.py    # 剪贴板双向同步
├── monitor_manager.py   # 多显示器管理
├── status_window.py     # 桌面状态悬浮窗
├── templates/
│   └── index.html       # 手机端完整单页应用
├── requirements.txt     # Python依赖
├── start.bat            # Windows一键启动脚本
└── uploads/             # 手机上传文件存储目录（自动创建）
```

---

## 认证配置 / Auth Configuration

首次运行自动生成 `auth_config.json`：

```json
{
  "mode": "dynamic",
  "fixed_password": "123456",
  "code_length": 6,
  "code_expire_seconds": 300
}
```

- `mode`: `"dynamic"` 动态验证码 / `"fixed"` 固定密码
- `fixed_password`: 固定密码模式时的密码
- `code_length`: 动态验证码位数
- `code_expire_seconds`: 验证码有效期（秒）

---

## 许可 / License

MIT
