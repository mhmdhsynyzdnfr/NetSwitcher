"""
NetSwitcher Pro - تغییر سریع آی‌پی، گیت‌وی و دی‌ان‌اس با کتابخانه Flet
طراحی جدید: نوار کناری سمت چپ (Left Sidebar) + فیلدها و دکمه‌ها در سمت راست
پالت رنگی گرم: نارنجی، کرمی و قهوه‌ای
سازگار با تمام نسخه‌های Flet (0.2x تا 0.8x+)
"""

import json
import os
import ipaddress
import flet as ft
from network_manager import (
    get_network_adapters,
    get_adapter_info,
    set_static_ip,
    set_dhcp_ip,
    set_static_dns,
    set_dhcp_dns,
    flush_dns_cache,
    is_admin,
)
from presets import DNS_PRESETS
from admin_helper import elevate_privileges

# سازگاری کنترل‌ها بین نسخه‌های مختلف Flet
PrimaryButton = getattr(ft, "Button", None) or getattr(ft, "ElevatedButton", None)
DropdownOption = getattr(ft, "DropdownOption", None) or ft.dropdown.Option


# ---------------------------------------------------------------- توابع سازگاری نسخه‌ها
def pad_symmetric(horizontal=0, vertical=0):
    """سازگار با ft.Padding.symmetric (جدید) و ft.padding.symmetric (قدیم)"""
    cls = getattr(ft, "Padding", None)
    if cls is not None and hasattr(cls, "symmetric"):
        return cls.symmetric(horizontal=horizontal, vertical=vertical)
    return ft.padding.symmetric(horizontal=horizontal, vertical=vertical)


def border_all(width, color):
    cls = getattr(ft, "Border", None)
    if cls is not None and hasattr(cls, "all"):
        return cls.all(width, color)
    return ft.border.all(width, color)


def border_only(**kwargs):
    cls = getattr(ft, "Border", None)
    if cls is not None and hasattr(cls, "only"):
        return cls.only(**kwargs)
    return ft.border.only(**kwargs)


# پالت رنگی گرم: نارنجی، کرمی و قهوه‌ای
COLOR_BG_DARK = "#1a120c"       # قهوه‌ای تیره اسپرسو (پس‌زمینه اصلی)
COLOR_SIDEBAR = "#140c07"       # قهوه‌ای سوخته و شاه‌بلوطی (نوار کناری سمت چپ)
COLOR_CARD = "#281a12"          # موکا و شکلاتی گرم (کارت‌ها و پنل‌ها)
COLOR_BORDER = "#483122"        # برنز / قهوه‌ای متوسط (کادرها)
COLOR_ORANGE = "#ea580c"        # نارنجی غنی (دکمه‌ها و عناصر فعال)
COLOR_ORANGE_LIGHT = "#f97316"  # نارنجی روشن
COLOR_CREAM = "#fef3c7"         # کرمی روشن (عناوین و متن‌ها)
COLOR_CREAM_MUTED = "#fed7aa"   # کرمی هلویی ملایم
COLOR_SAND = "#d8c2ad"          # شنی و خاکی (توضیحات و راهنماها)

CONFIG_FILE = "saved_profiles.json"


# ---------------------------------------------------------------- اعتبارسنجی شبکه
def valid_ip(value: str) -> bool:
    try:
        ipaddress.IPv4Address(value.strip())
        return True
    except (ValueError, AttributeError):
        return False


def valid_mask(value: str) -> bool:
    if not valid_ip(value):
        return False
    bits = bin(int(ipaddress.IPv4Address(value.strip())))[2:].zfill(32)
    return "01" not in bits and bits != "0" * 32


def gateway_in_subnet(ip: str, mask: str, gateway: str) -> bool:
    try:
        network = ipaddress.IPv4Interface(f"{ip.strip()}/{mask.strip()}").network
        return ipaddress.IPv4Address(gateway.strip()) in network
    except ValueError:
        return False


# ---------------------------------------------------------------- برنامه اصلی
def main(page: ft.Page):
    page.title = "NetSwitcher Pro | مدیریت هوشمند IP، گیت‌وی و DNS"
    page.theme_mode = "dark"
    page.bgcolor = COLOR_BG_DARK
    # قرار دادن page.rtl = False باعث می‌شود ستون اول (نوار کناری) دقیقا در سمت چپ پنجره قرار گیرد
    page.rtl = False
    page.padding = 0
    page.spacing = 0

    # ابعاد پنجره برنامه
    try:
        page.window.width = 880
        page.window.height = 660
        page.window.resizable = False
    except Exception:
        try:
            page.window_width = 880
            page.window_height = 660
            page.window_resizable = False
        except Exception:
            pass

    # تب فعال جاری: 'ip' | 'gateway' | 'dns' | 'settings'
    active_tab = {"name": "ip"}

    def notify(msg: str, is_error: bool = False):
        snack = ft.SnackBar(
            content=ft.Text(msg, color="white"),
            bgcolor="#991b1b" if is_error else "#2e7d32",
        )
        try:
            if hasattr(page, "show_dialog"):
                page.show_dialog(snack)
            elif hasattr(page, "open"):
                page.open(snack)
            else:
                page.snack_bar = snack
                snack.open = True
                page.update()
        except Exception:
            pass

    admin_status = is_admin()

    # بارگذاری پروفایل‌های ذخیره شده
    saved_profiles = []
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_profiles = json.load(f)
        except Exception:
            saved_profiles = []
    if not saved_profiles:
        saved_profiles = [
            {"name": "مودم خانه (DHCP خودکار)", "dhcp": True, "dns_auto": True},
            {"name": "شبکه اداری (آی‌پی ثابت)", "dhcp": False, "ip": "192.168.1.150", "mask": "255.255.255.0", "gateway": "192.168.1.1", "dns1": "8.8.8.8", "dns2": "1.1.1.1"},
            {"name": "ضد تحریم شکن", "dhcp": True, "dns_auto": False, "dns1": "178.22.122.100", "dns2": "185.51.200.2"},
        ]

    # ۱. کارت شبکه و دراپ‌داون
    try:
        adapters = get_network_adapters() or []
    except Exception:
        adapters = []
    selected_adapter = adapters[0] if adapters else None

    adapter_dropdown = ft.Dropdown(
        label="کارت شبکه فعال",
        options=[DropdownOption(a) for a in adapters],
        value=selected_adapter,
        width=360,
        bgcolor=COLOR_CARD,
        border_color=COLOR_BORDER,
        color=COLOR_CREAM,
    )

    # ۲. فیلدهای بخش IP
    left = ft.TextAlign.LEFT
    dhcp_switch = ft.Switch(
        label="دریافت خودکار آی‌پی از مودم (DHCP)",
        value=True,
        active_color=COLOR_ORANGE,
    )
    ip_input = ft.TextField(
        label="آدرس آی‌پی (IP Address)",
        hint_text="192.168.1.150",
        disabled=True,
        width=480,
        text_align=left,
        bgcolor=COLOR_CARD,
        border_color=COLOR_BORDER,
        color=COLOR_CREAM,
    )
    subnet_input = ft.TextField(
        label="ساب‌نت ماسک (Subnet Mask)",
        value="255.255.255.0",
        disabled=True,
        width=480,
        text_align=left,
        bgcolor=COLOR_CARD,
        border_color=COLOR_BORDER,
        color=COLOR_CREAM,
    )

    # ۳. فیلد بخش Default Gateway
    gateway_input = ft.TextField(
        label="پیش‌فرض گیت‌وی (Default Gateway)",
        hint_text="192.168.1.1",
        disabled=True,
        width=480,
        text_align=left,
        bgcolor=COLOR_CARD,
        border_color=COLOR_BORDER,
        color=COLOR_CREAM,
    )

    # ۴. فیلدهای بخش DNS
    dns_auto_switch = ft.Switch(
        label="دریافت خودکار DNS از مودم",
        value=True,
        active_color=COLOR_ORANGE,
    )
    dns1_input = ft.TextField(
        label="دی‌ان‌اس اول (Preferred DNS)",
        hint_text="178.22.122.100 (شکن) یا 8.8.8.8",
        disabled=True,
        width=480,
        text_align=left,
        bgcolor=COLOR_CARD,
        border_color=COLOR_BORDER,
        color=COLOR_CREAM,
    )
    dns2_input = ft.TextField(
        label="دی‌ان‌اس دوم (Alternate DNS)",
        hint_text="185.51.200.2 یا 1.1.1.1",
        disabled=True,
        width=480,
        text_align=left,
        bgcolor=COLOR_CARD,
        border_color=COLOR_BORDER,
        color=COLOR_CREAM,
    )

    # ۵. فیلد نام برای ذخیره کانفیگ جدید
    new_profile_input = ft.TextField(
        label="نام کانفیگ جدید (مثلاً خانه، شرکت، گیم)",
        hint_text="یک نام دلخواه وارد کنید...",
        width=360,
        bgcolor=COLOR_CARD,
        border_color=COLOR_BORDER,
        color=COLOR_CREAM,
    )

    status_text = ft.Text("آماده به کار", color=COLOR_SAND, size=12)

    # رویدادهای تغییر وضعیت
    def on_dhcp_toggle(e=None):
        auto = bool(dhcp_switch.value)
        ip_input.disabled = auto
        subnet_input.disabled = auto
        gateway_input.disabled = auto
        page.update()

    def on_dns_auto_toggle(e=None):
        auto = bool(dns_auto_switch.value)
        dns1_input.disabled = auto
        dns2_input.disabled = auto
        page.update()

    dhcp_switch.on_change = on_dhcp_toggle
    dns_auto_switch.on_change = on_dns_auto_toggle

    def load_current_adapter_state(e=None):
        name = adapter_dropdown.value
        if not name:
            status_text.value = "هیچ کارت شبکه‌ای یافت نشد."
            page.update()
            return
        try:
            info = get_adapter_info(name) or {}
        except Exception as ex:
            status_text.value = f"⚠️ خطا در خواندن مشخصات کارت: {ex}"
            page.update()
            return

        dhcp_switch.value = info.get("is_dhcp", True)
        ip_input.value = info.get("ip", "") or ""
        subnet_input.value = info.get("mask", "") or "255.255.255.0"
        gateway_input.value = info.get("gateway", "") or ""

        has_custom_dns = bool(info.get("dns1"))
        dns_auto_switch.value = not has_custom_dns
        dns1_input.value = info.get("dns1", "") or ""
        dns2_input.value = info.get("dns2", "") or ""

        ip_input.disabled = subnet_input.disabled = gateway_input.disabled = bool(dhcp_switch.value)
        dns1_input.disabled = dns2_input.disabled = bool(dns_auto_switch.value)

        status_text.value = f"مشخصات کارت {name} بارگذاری شد."
        page.update()

    if hasattr(adapter_dropdown, "on_select"):
        adapter_dropdown.on_select = load_current_adapter_state
    else:
        adapter_dropdown.on_change = load_current_adapter_state

    # اعمال پیش‌تنظیم DNS
    def apply_dns_preset(preset_key):
        preset = DNS_PRESETS.get(preset_key)
        if not preset:
            return
        dns_auto_switch.value = False
        dns1_input.value = preset.get("primary", "")
        dns2_input.value = preset.get("secondary", "")
        dns1_input.disabled = dns2_input.disabled = False
        page.update()
        notify(f"دی‌ان‌اس {preset.get('name', preset_key)} درج شد.")

    # ذخیره و اعمال کلی تغییرات شبکه
    def apply_network_changes(e=None):
        if not admin_status:
            notify("نیاز به اجرای برنامه با دسترسی Administrator است.", is_error=True)
            return

        adapter = adapter_dropdown.value
        if not adapter:
            notify("هیچ کارت شبکه‌ای انتخاب نشده است.", is_error=True)
            return

        # اعتبارسنجی مقادیر
        if not dhcp_switch.value:
            if not valid_ip(ip_input.value):
                notify("آدرس آی‌پی نامعتبر است.", is_error=True)
                return
            if not valid_mask(subnet_input.value):
                notify("ساب‌نت ماسک نامعتبر است.", is_error=True)
                return
            if not valid_ip(gateway_input.value):
                notify("آدرس دیفالت گیت‌وی نامعتبر است.", is_error=True)
                return
            if not gateway_in_subnet(ip_input.value, subnet_input.value, gateway_input.value):
                notify("گیت‌وی و آی‌پی باید در یک ساب‌نت باشند.", is_error=True)
                return

        if not dns_auto_switch.value:
            if not valid_ip(dns1_input.value):
                notify("دی‌ان‌اس اول نامعتبر است.", is_error=True)
                return
            if dns2_input.value.strip() and not valid_ip(dns2_input.value):
                notify("دی‌ان‌اس دوم نامعتبر است.", is_error=True)
                return

        status_text.value = "در حال اعمال تنظیمات روی کارت شبکه ویندوز..."
        page.update()

        try:
            # اعمال IP و Gateway
            if dhcp_switch.value:
                set_dhcp_ip(adapter)
            else:
                set_static_ip(
                    adapter,
                    ip_input.value.strip(),
                    subnet_input.value.strip(),
                    gateway_input.value.strip(),
                )

            # اعمال DNS
            if dns_auto_switch.value:
                set_dhcp_dns(adapter)
            else:
                set_static_dns(
                    adapter,
                    dns1_input.value.strip(),
                    dns2_input.value.strip(),
                )

            flush_dns_cache()
            status_text.value = "✅ تغییرات با موفقیت ذخیره و اعمال شد!"
            notify("تنظیمات با موفقیت در کارت شبکه ثبت شدند.")
        except Exception as ex:
            status_text.value = f"⚠️ خطا: {ex}"
            notify(f"خطا در اعمال: {ex}", is_error=True)

        page.update()

    # ذخیره کانفیگ فعلی
    def save_current_config(e=None):
        name = new_profile_input.value.strip()
        if not name:
            notify("لطفاً یک نام برای کانفیگ وارد کنید.", is_error=True)
            return
        new_prof = {
            "name": name,
            "dhcp": bool(dhcp_switch.value),
            "ip": ip_input.value.strip(),
            "mask": subnet_input.value.strip(),
            "gateway": gateway_input.value.strip(),
            "dns_auto": bool(dns_auto_switch.value),
            "dns1": dns1_input.value.strip(),
            "dns2": dns2_input.value.strip(),
        }
        saved_profiles.append(new_prof)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(saved_profiles, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        new_profile_input.value = ""
        switch_tab("settings")
        notify(f"کانفیگ «{name}» ذخیره گردید.")

    # اعمال یک پروفایل ذخیره شده
    def load_profile(prof):
        dhcp_switch.value = prof.get("dhcp", True)
        ip_input.value = prof.get("ip", "")
        subnet_input.value = prof.get("mask", "255.255.255.0")
        gateway_input.value = prof.get("gateway", "")
        dns_auto_switch.value = prof.get("dns_auto", True)
        dns1_input.value = prof.get("dns1", "")
        dns2_input.value = prof.get("dns2", "")

        ip_input.disabled = subnet_input.disabled = gateway_input.disabled = bool(dhcp_switch.value)
        dns1_input.disabled = dns2_input.disabled = bool(dns_auto_switch.value)
        page.update()
        notify(f"کانفیگ «{prof.get('name')}» بارگذاری شد. برای ثبت در شبکه، دکمه ذخیره را بزنید.")

    # کانتینر اصلی محتوا (سمت راست)
    content_area = ft.Container(expand=True, padding=24)

    # صفحات محتوای سمت راست
    def render_ip_view():
        return ft.Column([
            ft.Text("تغییر آدرس آی‌پی (IP Address)", size=18, weight="bold", color=COLOR_CREAM),
            ft.Text("تنظیم دستی آی‌پی استاتیک یا بازگشت به حالت خودکار مودم (DHCP)", size=12, color=COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=20),
            dhcp_switch,
            ft.Container(height=10),
            ip_input,
            subnet_input,
            ft.Container(height=15),
            PrimaryButton(
                "💾 ذخیره و ثبت آدرس IP",
                style=ft.ButtonStyle(bgcolor=COLOR_ORANGE, color="white"),
                on_click=apply_network_changes,
            )
        ], spacing=10)

    def render_gateway_view():
        return ft.Column([
            ft.Text("تغییر دیفالت گیت‌وی (Default Gateway)", size=18, weight="bold", color=COLOR_CREAM),
            ft.Text("تنظیم آدرس مودم یا روتر جهت برقراری دسترسی به اینترنت", size=12, color=COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=20),
            gateway_input,
            ft.Container(
                bgcolor=COLOR_CARD,
                padding=12,
                border_radius=8,
                border=border_all(1, COLOR_BORDER),
                content=ft.Row([
                    ft.Text("💡 گیت‌وی‌های متداول:", size=11, color=COLOR_CREAM_MUTED),
                    ft.OutlinedButton("192.168.1.1", on_click=lambda e: setattr(gateway_input, "value", "192.168.1.1") or page.update()),
                    ft.OutlinedButton("192.168.0.1", on_click=lambda e: setattr(gateway_input, "value", "192.168.0.1") or page.update()),
                    ft.OutlinedButton("10.0.0.1", on_click=lambda e: setattr(gateway_input, "value", "10.0.0.1") or page.update()),
                    ft.OutlinedButton("172.16.0.1", on_click=lambda e: setattr(gateway_input, "value", "172.16.0.1") or page.update()),
                ], spacing=6, wrap=True)
            ),
            ft.Container(height=15),
            PrimaryButton(
                "💾 ذخیره و اعمال گیت‌وی",
                style=ft.ButtonStyle(bgcolor=COLOR_ORANGE, color="white"),
                on_click=apply_network_changes,
            )
        ], spacing=10)

    def render_dns_view():
        return ft.Column([
            ft.Text("تغییر سرورهای دی‌ان‌اس (DNS Servers)", size=18, weight="bold", color=COLOR_CREAM),
            ft.Text("ست کردن DNSهای ضد تحریم ایرانی یا DNSهای پرسرعت جهانی", size=12, color=COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=20),
            dns_auto_switch,
            ft.Text("پیش‌تنظیم‌های محبوب (یک کلیک جهت درج):", size=12, color=COLOR_CREAM_MUTED),
            ft.Row([
                ft.OutlinedButton("🛡️ شکن", on_click=lambda e: apply_dns_preset("shecan")),
                ft.OutlinedButton("⚡ ۴۰۳", on_click=lambda e: apply_dns_preset("403")),
                ft.OutlinedButton("🎮 الکترو", on_click=lambda e: apply_dns_preset("electro")),
                ft.OutlinedButton("🌐 کلودفلر", on_click=lambda e: apply_dns_preset("cloudflare")),
                ft.OutlinedButton("🔍 گوگل", on_click=lambda e: apply_dns_preset("google")),
            ], wrap=True, spacing=6),
            ft.Container(height=10),
            dns1_input,
            dns2_input,
            ft.Container(height=15),
            PrimaryButton(
                "💾 ذخیره و اعمال DNS در شبکه",
                style=ft.ButtonStyle(bgcolor=COLOR_ORANGE, color="white"),
                on_click=apply_network_changes,
            )
        ], spacing=10)

    def render_settings_view():
        # لیست دکمه‌های پروفایل
        profile_controls = []
        for prof in saved_profiles:
            p_name = prof.get("name", "پروفایل")
            btn = ft.OutlinedButton(
                f"📁 {p_name}",
                on_click=(lambda p: lambda e: load_profile(p))(prof),
            )
            profile_controls.append(btn)

        return ft.Column([
            ft.Text("⚙️ تنظیمات و مدیریت کانفیگ‌ها", size=18, weight="bold", color=COLOR_CREAM),
            ft.Text("ذخیره کانفیگ فعلی، بارگذاری سریع پروفایل‌ها و ابزارهای سیستم‌عامل", size=12, color=COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=15),

            # ۱. ذخیره کانفیگ فعلی
            ft.Container(
                bgcolor=COLOR_CARD,
                padding=14,
                border_radius=10,
                border=border_all(1, COLOR_BORDER),
                content=ft.Column([
                    ft.Text("ذخیره تنظیمات فعلی به عنوان کانفیگ جدید:", weight="bold", color=COLOR_CREAM, size=13),
                    ft.Row([
                        new_profile_input,
                        PrimaryButton(
                            "💾 ذخیره کانفیگ",
                            style=ft.ButtonStyle(bgcolor=COLOR_ORANGE, color="white"),
                            on_click=save_current_config,
                        )
                    ], spacing=10)
                ], spacing=8)
            ),

            # ۲. بارگذاری سریع کانفیگ‌های ذخیره شده
            ft.Container(
                bgcolor=COLOR_CARD,
                padding=14,
                border_radius=10,
                border=border_all(1, COLOR_BORDER),
                content=ft.Column([
                    ft.Text("کانفیگ‌های ذخیره شده (کلیک برای بارگذاری):", weight="bold", color=COLOR_CREAM, size=13),
                    ft.Row(profile_controls, wrap=True, spacing=6),
                ], spacing=8)
            ),

            # ۳. پاکسازی کش DNS و ابزارها
            ft.Container(
                bgcolor=COLOR_CARD,
                padding=14,
                border_radius=10,
                border=border_all(1, COLOR_BORDER),
                content=ft.Row([
                    ft.Text("پاکسازی کش DNS ویندوز (ipconfig /flushdns):", size=12, color=COLOR_CREAM),
                    ft.OutlinedButton("🧹 پاکسازی کش", on_click=lambda e: flush_dns_cache() or notify("کش DNS با موفقیت پاک شد.")),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ),

            # ۴. وضعیت ادمین
            ft.Container(
                bgcolor=COLOR_CARD,
                padding=14,
                border_radius=10,
                border=border_all(1, COLOR_BORDER),
                content=ft.Row([
                    ft.Text("وضعیت ادمین: " + ("دارای دسترسی کامل ادمین ✅" if admin_status else "⚠️ برنامه با دسترسی عادی اجرا شده است"), size=12, color=COLOR_CREAM),
                    PrimaryButton(
                        "ارتقا به Admin (UAC)",
                        visible=not admin_status,
                        style=ft.ButtonStyle(bgcolor=COLOR_ORANGE, color="white"),
                        on_click=lambda e: elevate_privileges(),
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )
        ], spacing=12)

    def switch_tab(tab_name: str):
        active_tab["name"] = tab_name
        update_sidebar_styles()
        if tab_name == "ip":
            content_area.content = render_ip_view()
        elif tab_name == "gateway":
            content_area.content = render_gateway_view()
        elif tab_name == "dns":
            content_area.content = render_dns_view()
        elif tab_name == "settings":
            content_area.content = render_settings_view()
        page.update()

    # دکمه‌های نوار کناری سمت چپ (Left Sidebar)
    btn_tab_ip = ft.Container(
        content=ft.Text("🌐 تغییر آدرس آی‌پی (IP)", size=13, weight="bold"),
        padding=pad_symmetric(horizontal=16, vertical=12),
        border_radius=8,
        on_click=lambda e: switch_tab("ip"),
    )
    btn_tab_gateway = ft.Container(
        content=ft.Text("🚪 تغییر دیفالت گیت‌وی", size=13, weight="bold"),
        padding=pad_symmetric(horizontal=16, vertical=12),
        border_radius=8,
        on_click=lambda e: switch_tab("gateway"),
    )
    btn_tab_dns = ft.Container(
        content=ft.Text("🛡️ تغییر سرورهای DNS", size=13, weight="bold"),
        padding=pad_symmetric(horizontal=16, vertical=12),
        border_radius=8,
        on_click=lambda e: switch_tab("dns"),
    )
    # آیکون و دکمه تنظیمات در پایین نوار کناری
    btn_tab_settings = ft.Container(
        content=ft.Row([
            ft.Text("⚙️ تنظیمات و ذخیره کانفیگ", size=13, weight="bold"),
        ]),
        padding=pad_symmetric(horizontal=16, vertical=12),
        border_radius=8,
        on_click=lambda e: switch_tab("settings"),
    )

    def update_sidebar_styles():
        for b, name in [
            (btn_tab_ip, "ip"),
            (btn_tab_gateway, "gateway"),
            (btn_tab_dns, "dns"),
            (btn_tab_settings, "settings"),
        ]:
            is_active = (active_tab["name"] == name)
            b.bgcolor = COLOR_ORANGE if is_active else "transparent"
            if hasattr(b.content, "controls"):
                for c in b.content.controls:
                    c.color = "white" if is_active else COLOR_SAND
            else:
                b.content.color = "white" if is_active else COLOR_SAND

    update_sidebar_styles()

    # ساخت نوار کناری در سمت چپ پنجره (Sidebar on Left)
    sidebar = ft.Container(
        width=240,
        bgcolor=COLOR_SIDEBAR,
        border=border_only(right=ft.BorderSide(1, COLOR_BORDER)),
        padding=16,
        content=ft.Column([
            # لوگو و برند برنامه
            ft.Column([
                ft.Text("⚡ NetSwitcher Pro", size=18, weight="bold", color=COLOR_CREAM),
                ft.Text("کنترل سریع شبکه دسکتاپ", size=11, color=COLOR_SAND),
            ], spacing=2),
            ft.Divider(color=COLOR_BORDER, height=20),

            # گزینه‌های بالای نوار کناری: تغییر IP، تغییر گیت‌وی، تغییر DNS
            ft.Column([
                btn_tab_ip,
                btn_tab_gateway,
                btn_tab_dns,
            ], spacing=6),

            # فاصله خالی میانی
            ft.Container(expand=True),

            # آیکون و بخش تنظیمات در پایین نوار کناری (برای ذخیره و تغییر کانفیگ)
            ft.Divider(color=COLOR_BORDER, height=20),
            btn_tab_settings,
        ], expand=True)
    )

    # سربرگ بالای بخش راست (انتخاب کارت شبکه و رفرش)
    header_bar = ft.Container(
        padding=pad_symmetric(horizontal=24, vertical=14),
        border=border_only(bottom=ft.BorderSide(1, COLOR_BORDER)),
        content=ft.Row([
            adapter_dropdown,
            ft.OutlinedButton("🔄 بروزرسانی کارت", on_click=load_current_adapter_state),
            ft.Container(expand=True),
            status_text,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    # ستون سمت راست شامل فیلدها، دکمه‌ها و فرم‌ها
    try:
        right_column = ft.Column([header_bar, content_area], expand=True, spacing=0, rtl=True)
    except TypeError:
        right_column = ft.Column([header_bar, content_area], expand=True, spacing=0)

    # اتصال نوار کناری (سمت چپ) و پنل فیلدها (سمت راست)
    page.add(
        ft.Row([
            sidebar,
            right_column,
        ], expand=True, spacing=0)
    )

    # نمایش تب پیش‌فرض
    switch_tab("ip")
    load_current_adapter_state()


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)