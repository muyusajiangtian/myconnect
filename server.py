"""
MyConnect 服务端（升级版）
整合认证、文件传输、剪贴板同步、多显示器等功能
"""
import json
import time
import threading
import socket
import os
import base64
from flask import Flask, render_template, request, jsonify, send_file, abort

from flask_sock import Sock

from screen_capture import ScreenCapture
from input_handler import handle_command
from status_window import StatusWindow
from auth_manager import AuthManager
from file_manager import FileManager
from clipboard_sync import ClipboardSync
from monitor_manager import MonitorManager

app = Flask(__name__)
sock = Sock(app)

# 初始化各模块
monitor_manager = MonitorManager()
capture = ScreenCapture(target_fps=30, quality=50, scale=0.6, monitor_manager=monitor_manager)
status_window = StatusWindow()
auth_manager = AuthManager()
file_manager = FileManager()
clipboard_sync = ClipboardSync()

clients = set()
clients_lock = threading.Lock()
server_running = True

# 客户端WebSocket连接信息，用于推送剪贴板和文件
client_ws_map = {}  # ws -> {"token": str, "connected_at": float}


# ==================== 页面路由 ====================

@app.route("/")
def index():
    """主页（需要认证后才能使用）"""
    return render_template("index.html")


@app.route("/api/auth/info", methods=["GET"])
def auth_info():
    """获取认证模式信息（不返回密码，仅模式）"""
    return jsonify({"mode": auth_manager.mode})


@app.route("/api/auth/verify", methods=["POST"])
def auth_verify():
    """验证密码/验证码"""
    data = request.get_json()
    password = data.get("password", "")

    if auth_manager.verify(password):
        token = auth_manager.generate_token()
        return jsonify({"success": True, "token": token})
    else:
        return jsonify({"success": False, "message": "验证码/密码错误"}), 401


# ==================== 文件传输路由 ====================

@app.route("/api/files/list", methods=["GET"])
def files_list():
    """列出目录内容"""
    token = request.headers.get("X-Auth-Token", "")
    if not auth_manager.verify_token(token):
        return jsonify({"error": "未授权"}), 401

    path = request.args.get("path", None)
    result = file_manager.list_directory(path)
    return jsonify(result)


@app.route("/api/files/download", methods=["GET"])
def files_download():
    """下载文件"""
    token = request.headers.get("X-Auth-Token", "") or request.args.get("token", "")
    if not auth_manager.verify_token(token):
        return jsonify({"error": "未授权"}), 401

    filepath = request.args.get("path", "")
    abs_path = file_manager.get_file_path(filepath)
    if not abs_path:
        abort(404)

    return send_file(abs_path, as_attachment=True,
                     download_name=os.path.basename(abs_path))


@app.route("/api/files/upload", methods=["POST"])
def files_upload():
    """手机上传文件到电脑"""
    token = request.headers.get("X-Auth-Token", "")
    if not auth_manager.verify_token(token):
        return jsonify({"error": "未授权"}), 401

    if "file" not in request.files:
        return jsonify({"error": "没有文件"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "文件名为空"}), 400

    data = file.read()
    result = file_manager.save_uploaded_file(file.filename, data)
    return jsonify(result)


# ==================== 显示器路由 ====================

@app.route("/api/monitors", methods=["GET"])
def get_monitors():
    """获取显示器列表"""
    token = request.headers.get("X-Auth-Token", "")
    if not auth_manager.verify_token(token):
        return jsonify({"error": "未授权"}), 401

    monitor_manager.refresh()
    return jsonify({
        "monitors": monitor_manager.get_monitors_info(),
        "current": monitor_manager.current_index,
    })


@app.route("/api/monitors/select", methods=["POST"])
def select_monitor():
    """选择显示器"""
    token = request.headers.get("X-Auth-Token", "")
    if not auth_manager.verify_token(token):
        return jsonify({"error": "未授权"}), 401

    data = request.get_json()
    index = data.get("index", 0)
    monitor_manager.current_index = index
    return jsonify({"success": True, "current": monitor_manager.current_index})


# ==================== 画质帧率调节 ====================

@app.route("/api/settings/capture", methods=["POST"])
def update_capture_settings():
    """更新画质和帧率设置"""
    token = request.headers.get("X-Auth-Token", "")
    if not auth_manager.verify_token(token):
        return jsonify({"error": "未授权"}), 401

    data = request.get_json()
    if "quality" in data:
        capture.set_quality(int(data["quality"]))
    if "fps" in data:
        capture.set_fps(int(data["fps"]))
    if "scale" in data:
        capture.set_scale(float(data["scale"]))

    return jsonify({"success": True})


# ==================== 剪贴板路由 ====================

@app.route("/api/clipboard/get", methods=["GET"])
def clipboard_get():
    """获取电脑剪贴板内容"""
    token = request.headers.get("X-Auth-Token", "")
    if not auth_manager.verify_token(token):
        return jsonify({"error": "未授权"}), 401

    return jsonify({"text": clipboard_sync.get_clipboard()})


@app.route("/api/clipboard/set", methods=["POST"])
def clipboard_set():
    """设置电脑剪贴板内容（手机端同步过来）"""
    token = request.headers.get("X-Auth-Token", "")
    if not auth_manager.verify_token(token):
        return jsonify({"error": "未授权"}), 401

    data = request.get_json()
    text = data.get("text", "")
    clipboard_sync.set_clipboard(text)
    return jsonify({"success": True})


# ==================== 关机路由 ====================

@app.route("/shutdown", methods=["POST"])
def shutdown_route():
    token = request.headers.get("X-Auth-Token", "")
    if not auth_manager.verify_token(token):
        return jsonify({"error": "未授权"}), 401
    _do_shutdown()
    return "OK", 200


# ==================== WebSocket ====================

@sock.route("/ws/control")
def ws_control(ws):
    """主WebSocket连接：接收控制指令，推送画面帧和状态"""
    global server_running

    # 等待客户端发送认证令牌
    try:
        auth_msg = ws.receive(timeout=10)
        if auth_msg is None:
            ws.close()
            return
        auth_data = json.loads(auth_msg)
        token = auth_data.get("token", "")
        if not auth_manager.verify_token(token):
            ws.send(json.dumps({"type": "auth_failed", "message": "认证失败"}))
            ws.close()
            return
        ws.send(json.dumps({"type": "auth_ok"}))
    except Exception:
        ws.close()
        return

    # 注册客户端
    with clients_lock:
        clients.add(ws)
        client_ws_map[ws] = {"token": token, "connected_at": time.time()}
    status_window.update(len(clients), capture.fps)

    # 注册剪贴板变化回调
    def on_clipboard_change(text):
        try:
            ws.send(json.dumps({"type": "clipboard_update", "text": text}))
        except Exception:
            pass

    clipboard_sync.register_callback(on_clipboard_change)

    # 启动帧推送线程
    send_thread = threading.Thread(target=_stream_frames, args=(ws,), daemon=True)
    send_thread.start()

    # 启动状态推送线程（延迟、带宽等）
    stats_thread = threading.Thread(target=_stream_stats, args=(ws,), daemon=True)
    stats_thread.start()

    try:
        while server_running:
            msg = ws.receive(timeout=120)
            if msg is None:
                break
            try:
                data = json.loads(msg)
                msg_type = data.get("type")

                if msg_type == "shutdown":
                    _do_shutdown()
                    break
                elif msg_type == "ping":
                    # 心跳/延迟测量
                    ws.send(json.dumps({"type": "pong", "ts": data.get("ts", 0)}))
                elif msg_type == "clipboard_sync":
                    # 手机端剪贴板同步到电脑
                    clipboard_sync.set_clipboard(data.get("text", ""))
                elif msg_type == "set_monitor":
                    # 切换显示器
                    monitor_manager.current_index = data.get("index", 0)
                elif msg_type == "set_quality":
                    capture.set_quality(int(data.get("value", 50)))
                elif msg_type == "set_fps":
                    capture.set_fps(int(data.get("value", 30)))
                elif msg_type == "set_scale":
                    capture.set_scale(float(data.get("value", 0.6)))
                elif msg_type == "request_hd":
                    # 客户端放大画面时请求高清帧
                    capture.request_full_resolution(data.get("enabled", False))
                else:
                    handle_command(data)
            except (json.JSONDecodeError, Exception):
                pass
    except Exception:
        pass
    finally:
        clipboard_sync.unregister_callback(on_clipboard_change)
        with clients_lock:
            clients.discard(ws)
            client_ws_map.pop(ws, None)
        status_window.update(len(clients), capture.fps)


def _stream_frames(ws):
    """帧推送线程 - 事件驱动，无轮询无锁竞争"""
    last_version = 0
    ws_alive = True
    try:
        while server_running and ws_alive:
            # 等待新帧就绪（事件驱动，不占CPU）
            frame, version = capture.wait_for_frame(last_version, timeout=0.05)
            if frame is None or version == last_version:
                continue
            last_version = version
            try:
                ws.send(frame)
            except Exception:
                ws_alive = False
                break
            status_window.update(len(clients), capture.fps)
    except Exception:
        pass


def _stream_stats(ws):
    """每2秒推送连接状态"""
    try:
        while server_running:
            if ws not in client_ws_map:
                break
            try:
                stats = {
                    "type": "stats",
                    "fps": round(capture.fps, 1),
                    "bandwidth": capture.bandwidth,
                    "quality": capture._quality_current,
                    "clients": len(clients),
                    "monitor": monitor_manager.current_index,
                }
                ws.send(json.dumps(stats))
            except Exception:
                break
            time.sleep(2)
    except Exception:
        pass


def _do_shutdown():
    """关闭服务"""
    global server_running
    server_running = False
    print("\n[服务关闭] 收到关闭指令，正在停止...")
    capture.stop()
    clipboard_sync.stop()

    def _kill():
        time.sleep(1)
        os._exit(0)

    threading.Thread(target=_kill, daemon=True).start()


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    port = 9000
    ip = get_local_ip()

    print("=" * 55)
    print("  MyConnect 手机遥控电脑 - 升级版 v2.0")
    print("=" * 55)
    print(f"  局域网地址: http://{ip}:{port}")
    print(f"  手机浏览器访问上述地址即可控制电脑")
    print()

    # 显示认证信息
    auth_info = auth_manager.get_display_info()
    if auth_info["mode"] == "dynamic":
        print(f"  认证模式: 动态验证码")
        print(f"  当前验证码: {auth_info['code']}")
    else:
        print(f"  认证模式: 固定密码")
        print(f"  密码: {auth_info['fixed_password']}")

    print()
    print(f"  显示器数量: {len(monitor_manager.monitors)}")
    print(f"  按 Ctrl+C 或手机端点击[关闭]可停止服务")
    print("=" * 55)
    print()

    capture.start()
    clipboard_sync.start()
    status_window.start()

    try:
        app.run(host="0.0.0.0", port=port, threaded=True)
    except KeyboardInterrupt:
        print("\n[Ctrl+C] 服务已停止")
        capture.stop()
        clipboard_sync.stop()


if __name__ == "__main__":
    main()
