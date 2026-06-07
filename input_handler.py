import sys
import time
import platform
import threading
import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

IS_WINDOWS = platform.system() == 'Windows'
IS_MAC = platform.system() == 'Darwin'

_clipboard_lock = threading.Lock()


def _get_clipboard_win():
    import ctypes
    import ctypes.wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    CF_UNICODETEXT = 13

    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.GetClipboardData.restype = ctypes.c_void_p

    if not user32.OpenClipboard(0):
        return None
    try:
        h_data = user32.GetClipboardData(CF_UNICODETEXT)
        if not h_data:
            return None
        p_data = kernel32.GlobalLock(h_data)
        if not p_data:
            return None
        try:
            text = ctypes.wstring_at(p_data)
            return text
        finally:
            kernel32.GlobalUnlock(h_data)
    finally:
        user32.CloseClipboard()


def _set_clipboard_win(text):
    import ctypes
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

    text_bytes = text.encode('utf-16-le') + b'\x00\x00'
    buf_size = len(text_bytes)

    if not user32.OpenClipboard(0):
        return False
    user32.EmptyClipboard()

    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, buf_size)
    if not h_mem:
        user32.CloseClipboard()
        return False
    p_mem = kernel32.GlobalLock(h_mem)
    ctypes.memmove(p_mem, text_bytes, buf_size)
    kernel32.GlobalUnlock(h_mem)

    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
    user32.CloseClipboard()
    return True


def _clipboard_paste(text):
    """保存当前剪贴板 -> 写入新文字 -> Ctrl+V粘贴 -> 恢复原剪贴板"""
    with _clipboard_lock:
        if IS_WINDOWS:
            old_clip = _get_clipboard_win()
            if not _set_clipboard_win(text):
                return False
            time.sleep(0.02)
            pyautogui.hotkey('ctrl', 'v', _pause=False)
            time.sleep(0.05)
            if old_clip is not None:
                _set_clipboard_win(old_clip)
            return True

        elif IS_MAC:
            import subprocess
            result = subprocess.run(['pbpaste'], capture_output=True, text=True)
            old_clip = result.stdout

            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            process.communicate(input=text.encode('utf-8'))
            time.sleep(0.02)
            pyautogui.hotkey('command', 'v', _pause=False)
            time.sleep(0.05)

            if old_clip:
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                process.communicate(input=old_clip.encode('utf-8'))
            return True

        else:
            import subprocess
            try:
                result = subprocess.run(
                    ['xclip', '-selection', 'clipboard', '-o'],
                    capture_output=True, text=True
                )
                old_clip = result.stdout
            except FileNotFoundError:
                old_clip = None

            try:
                process = subprocess.Popen(
                    ['xclip', '-selection', 'clipboard'],
                    stdin=subprocess.PIPE
                )
                process.communicate(input=text.encode('utf-8'))
            except FileNotFoundError:
                try:
                    process = subprocess.Popen(
                        ['xsel', '--clipboard', '--input'],
                        stdin=subprocess.PIPE
                    )
                    process.communicate(input=text.encode('utf-8'))
                except FileNotFoundError:
                    return False

            time.sleep(0.02)
            pyautogui.hotkey('ctrl', 'v', _pause=False)
            time.sleep(0.05)

            if old_clip:
                try:
                    process = subprocess.Popen(
                        ['xclip', '-selection', 'clipboard'],
                        stdin=subprocess.PIPE
                    )
                    process.communicate(input=old_clip.encode('utf-8'))
                except FileNotFoundError:
                    pass
            return True


def _type_text(text):
    """所有文字统一使用剪贴板粘贴方案，确保中文可靠输入"""
    _clipboard_paste(text)


def handle_command(data: dict):
    cmd_type = data.get("type")

    if cmd_type == "move":
        dx = data.get("dx", 0)
        dy = data.get("dy", 0)
        pyautogui.moveRel(dx, dy, _pause=False)

    elif cmd_type == "click":
        button = data.get("button", "left")
        if button in ("left", "right", "middle"):
            pyautogui.click(button=button, _pause=False)

    elif cmd_type == "doubleclick":
        pyautogui.doubleClick(_pause=False)

    elif cmd_type == "scroll":
        delta = data.get("delta", 0)
        pyautogui.scroll(delta, _pause=False)

    elif cmd_type == "hscroll":
        delta = data.get("delta", 0)
        if IS_WINDOWS:
            import ctypes
            MOUSEEVENTF_HWHEEL = 0x01000
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_HWHEEL, 0, 0, int(delta * 120), 0)
        elif IS_MAC:
            import subprocess
            subprocess.run(
                ['osascript', '-e', f'tell application "System Events" to scroll horizontal {delta}'],
                capture_output=True
            )
        else:
            pyautogui.hscroll(delta, _pause=False)

    elif cmd_type == "key":
        key = data.get("key", "")
        if key:
            pyautogui.press(key, _pause=False)

    elif cmd_type == "keydown":
        key = data.get("key", "")
        if key:
            pyautogui.keyDown(key, _pause=False)

    elif cmd_type == "keyup":
        key = data.get("key", "")
        if key:
            pyautogui.keyUp(key, _pause=False)

    elif cmd_type == "text":
        text = data.get("text", "")
        if text:
            _type_text(text)

    elif cmd_type == "hotkey":
        keys = data.get("keys", [])
        if keys:
            pyautogui.hotkey(*keys, _pause=False)
