import pyautogui
import subprocess

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


def _type_text_via_clipboard(text):
    """通过剪贴板输入文字，支持中文和特殊字符"""
    try:
        process = subprocess.Popen(
            ['clip.exe'],
            stdin=subprocess.PIPE,
            shell=True
        )
        process.communicate(input=text.encode('utf-16-le'))

        import ctypes
        ctypes.windll.user32.OpenClipboard(0)
        # 用 Ctrl+V 粘贴
        pyautogui.hotkey('ctrl', 'v', _pause=False)
    except Exception:
        # 回退：尝试逐字符输入（仅ASCII有效）
        for ch in text:
            if ord(ch) < 128:
                pyautogui.press(ch, _pause=False)


def _type_text(text):
    """智能文字输入：ASCII用直接输入，含非ASCII用剪贴板"""
    if all(ord(c) < 128 for c in text):
        pyautogui.write(text, interval=0.01, _pause=False)
    else:
        _clipboard_paste(text)


def _clipboard_paste(text):
    """将文字放入剪贴板并粘贴"""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    text_bytes = text.encode('utf-16-le') + b'\x00\x00'
    buf_size = len(text_bytes)

    user32.OpenClipboard(0)
    user32.EmptyClipboard()

    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, buf_size)
    p_mem = kernel32.GlobalLock(h_mem)
    ctypes.memmove(p_mem, text_bytes, buf_size)
    kernel32.GlobalUnlock(h_mem)

    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
    user32.CloseClipboard()

    pyautogui.hotkey('ctrl', 'v', _pause=False)


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

    elif cmd_type == "key":
        key = data.get("key", "")
        if key:
            pyautogui.press(key, _pause=False)

    elif cmd_type == "text":
        text = data.get("text", "")
        if text:
            _type_text(text)

    elif cmd_type == "hotkey":
        keys = data.get("keys", [])
        if keys:
            pyautogui.hotkey(*keys, _pause=False)
