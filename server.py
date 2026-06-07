import json
import time
import threading
import socket
import os
from flask import Flask, render_template
from flask_sock import Sock

from screen_capture import ScreenCapture
from input_handler import handle_command
from status_window import StatusWindow

app = Flask(__name__)
sock = Sock(app)

capture = ScreenCapture(target_fps=30, quality=50, scale=0.6)
status_window = StatusWindow()

clients = set()
clients_lock = threading.Lock()
server_running = True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/shutdown", methods=["POST"])
def shutdown_route():
    _do_shutdown()
    return "OK", 200


@sock.route("/ws/control")
def ws_control(ws):
    global server_running

    with clients_lock:
        clients.add(ws)
    status_window.update(len(clients), capture.fps)

    send_thread = threading.Thread(target=_stream_frames, args=(ws,), daemon=True)
    send_thread.start()

    try:
        while server_running:
            msg = ws.receive(timeout=30)
            if msg is None:
                break
            try:
                data = json.loads(msg)
                if data.get("type") == "shutdown":
                    _do_shutdown()
                    break
                handle_command(data)
            except (json.JSONDecodeError, Exception):
                pass
    except Exception:
        pass
    finally:
        with clients_lock:
            clients.discard(ws)
        status_window.update(len(clients), capture.fps)


def _stream_frames(ws):
    interval = 1.0 / 30
    last_frame_id = None
    try:
        while server_running:
            with clients_lock:
                if ws not in clients:
                    break

            frame = capture.get_frame()
            if frame is not None and frame is not last_frame_id:
                try:
                    ws.send(frame)
                except Exception:
                    break
                last_frame_id = frame

            status_window.update(len(clients), capture.fps)
            time.sleep(interval)
    except Exception:
        pass


def _do_shutdown():
    global server_running
    server_running = False
    print("\n[服务关闭] 收到关闭指令，正在停止...")
    capture.stop()

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

    print("=" * 50)
    print("  手机遥控电脑 - 服务端已启动")
    print("=" * 50)
    print(f"  局域网地址: http://{ip}:{port}")
    print(f"  手机浏览器访问上述地址即可控制电脑")
    print(f"  按 Ctrl+C 或手机端点击[关闭]可停止服务")
    print("=" * 50)
    print()

    capture.start()
    status_window.start()

    try:
        app.run(host="0.0.0.0", port=port, threaded=True)
    except KeyboardInterrupt:
        print("\n[Ctrl+C] 服务已停止")
        capture.stop()


if __name__ == "__main__":
    main()
