"""Windows console support for the world.execute(me); terminal MV player.

Replaces the POSIX-only termios/tty/select input path:
- enables ANSI escape processing + UTF-8 output on the Windows console
- translates console key events into the same escape sequences the
  player's main loop already understands ('\\x1b[C' / '\\x1b[D' / ...)
"""
import ctypes
import msvcrt
import os
import shutil
import sys
import time

_kernel32 = ctypes.windll.kernel32
_STD_OUTPUT_HANDLE = -11
_ENABLE_PROCESSED_OUTPUT = 0x0001
_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

_ARROW_MAP = {'H': '\x1b[A', 'P': '\x1b[B', 'K': '\x1b[D', 'M': '\x1b[C'}


def setup():
    """Enable ANSI escapes and UTF-8 output. Safe to call when piped."""
    try:
        handle = _kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
        mode = ctypes.c_ulong()
        if _kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            _kernel32.SetConsoleMode(
                handle, mode.value | _ENABLE_PROCESSED_OUTPUT | _ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        pass
    try:
        _kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    for stream in (sys.stdout, sys.stdin):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


def read_keys(timeout):
    """Wait up to ``timeout`` seconds for console input.

    Returns a string of key events using the same encoding as the POSIX
    path in player.py (arrow keys arrive as '\\x1b[C' etc., plain keys as
    themselves). Returns '' when nothing was pressed.
    """
    deadline = time.monotonic() + max(0.0, timeout)
    out = []
    while time.monotonic() < deadline:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ('\x00', '\xe0'):
                ch2 = msvcrt.getwch()
                out.append(_ARROW_MAP.get(ch2, ''))
            else:
                out.append(ch)
            continue
        if out:
            break
        time.sleep(0.005)
    return ''.join(out)


def terminal_size():
    try:
        return os.get_terminal_size(sys.stdout.fileno())
    except OSError:
        return shutil.get_terminal_size((100, 36))
