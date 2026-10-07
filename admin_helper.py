"""
مدیریت درخواست ارتقای سطح دسترسی به Administrator در ویندوز
"""

import sys
import os
import ctypes


def is_running_as_admin() -> bool:
    """بررسی وضعیت دسترسی ادمین"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def elevate_privileges():
    """
    در صورت عدم دسترسی ادمین، برنامه مجدداً با درخواست UAC
    و فلگ runas در ویندوز اجرا شده و نمونه قبلی بسته می‌شود.
    """
    if not is_running_as_admin():
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])

        # فراخوانی ShellExecuteW با پارامتر runas
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            f'"{script}" {params}',
            None,
            1  # SW_SHOWNORMAL
        )

        # اگر کاربر دسترسی را تایید کرد، پروسه فعلی بسته شود
        if ret > 32:
            sys.exit(0)
        else:
            print("کاربر دسترسی Administrator را تایید نکرد.")
