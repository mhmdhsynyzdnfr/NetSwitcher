"""
NetSwitcher Pro - برنامه دسکتاپ تغییر سریع آی‌پی، گیت‌وی و دی‌ان‌اس با Flet
طراحی: عمودی شبیه ماشین‌حساب ویندوز (ابعاد ۴۴۰ در ۷۶۰ پیکسل)
ورود خودکار به عنوان Administrator در شروع برنامه
تم پالت گرم: نارنجی، کرمی و قهوه‌ای
سازگار با Flet قدیم (0.2x) و جدید (0.80+)
"""

import sys
import os
import ctypes
import subprocess
import re
import ipaddress
import json
import flet as ft

# =====================================================================
# ۱. پالت رنگی
# =====================================================================
COLOR_BG_DARK = "#1a120c"
COLOR_CARD = "#281a12"
COLOR_BORDER = "#483122"
COLOR_ORANGE = "#ea580c"
COLOR_ORANGE_HOVER = "#f97316"
COLOR_CREAM = "#fef3c7"
COLOR_CREAM_MUTED = "#fed7aa"
COLOR_SAND = "#d8c2ad"

CONFIG_FILE = "saved_profiles.json"

DNS_PRESETS = {
    "shecan": {"name": "شکن (ضدتحریم)", "primary": "178.22.122.100", "secondary": "185.51.200.2"},
    "403": {"name": "۴۰۳ آنلاین", "primary": "10.202.10.202", "secondary": "10.202.10.102"},
    "electro": {"name": "الکترو (گیمینگ)", "primary": "78.157.42.101", "secondary": "78.157.42.100"},
    "cloudflare": {"name": "1.1.1.1", "primary": "1.1.1.1", "secondary": "1.0.0.1"},
    "google": {"name": "8.8.8.8", "primary": "8.8.8.8", "secondary": "8.8.4.4"},
}


# =====================================================================
# ۲. توابع سازگاری بین نسخه‌های مختلف Flet
# =====================================================================
def pad_symmetric(horizontal=0, vertical=0):
    try:
        return ft.Padding.symmetric(vertical=vertical, horizontal=horizontal)
    except AttributeError:
        return ft.padding.symmetric(vertical=vertical, horizontal=horizontal)


def border_all(width, color):
    try:
        return ft.Border.all(width, color)
    except AttributeError:
        return ft.border.all(width, color)


def align_center():
    try:
        return ft.Alignment.CENTER
    except AttributeError:
        pass
    try:
        return ft.Alignment(0, 0)
    except Exception:
        return ft.alignment.center


def make_switch(label: str, value: bool = True):
    try:
        return ft.Switch(label=label, value=value, active_color=COLOR_ORANGE)
    except TypeError:
        return ft.Switch(label=label, value=value)


def make_text(text, size=12, color=None, bold=False, align=None):
    kwargs = {"size": size}
    if color:
        kwargs["color"] = color
    if bold:
        kwargs["weight"] = ft.FontWeight.BOLD
    if align is not None:
        kwargs["text_align"] = align
    return ft.Text(text, **kwargs)


# =====================================================================
# ۳. اعتبارسنجی شبکه
# =====================================================================
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


# =====================================================================
# ۴. توابع سیستم‌عامل و ورود خودکار ادمین
# =====================================================================
def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def ensure_admin():
    """اگر برنامه ادمین نباشد، با UAC دوباره اجرا می‌شود و نسخه عادی بسته می‌شود."""
    if not is_admin():
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        try:
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}" {params}', None, 1
            )
            if ret > 32:
                sys.exit(0)
        except Exception as e:
            print("خطا در درخواست مجوز ادمین:", e)


def run_cmd(cmd: str) -> tuple:
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            encoding="cp1256",
            errors="ignore",
        )
        if res.returncode == 0:
            return True, res.stdout.strip()
        return False, res.stderr.strip() or res.stdout.strip()
    except Exception as e:
        return False, str(e)


def get_network_adapters() -> list:
    ok, output = run_cmd("netsh interface show interface")
    adapters = []
    if ok:
        for line in output.splitlines():
            if "Enabled" in line or "Connected" in line:
                parts = re.split(r"\s{2,}", line.strip())
                if len(parts) >= 4:
                    adapters.append(parts[3].strip())
    return adapters if adapters else ["Wi-Fi", "Ethernet"]


def get_adapter_info(adapter_name: str) -> dict:
    info = {
        "is_dhcp": True,
        "ip": "",
        "mask": "255.255.255.0",
        "gateway": "",
        "dns1": "",
        "dns2": "",
    }
    ok_ip, out_ip = run_cmd(f'netsh interface ipv4 show addresses "{adapter_name}"')
    if ok_ip:
        dhcp_match = re.search(r"DHCP enabled:\s*(Yes|No)", out_ip, re.IGNORECASE)
        if dhcp_match:
            info["is_dhcp"] = dhcp_match.group(1).lower() == "yes"

        ip_match = re.search(r"IP Address:\s+([\d\.]+)", out_ip)
        if ip_match:
            info["ip"] = ip_match.group(1)

        mask_match = re.search(r"mask\s+([\d\.]+)\)", out_ip)
        if mask_match:
            info["mask"] = mask_match.group(1)

        gw_match = re.search(r"Default Gateway:\s+([\d\.]+)", out_ip)
        if gw_match:
            info["gateway"] = gw_match.group(1)

    ok_dns, out_dns = run_cmd(f'netsh interface ipv4 show dnsservers "{adapter_name}"')
    if ok_dns:
        dns_matches = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", out_dns)
        if len(dns_matches) >= 1:
            info["dns1"] = dns_matches[0]
        if len(dns_matches) >= 2:
            info["dns2"] = dns_matches[1]

    return info


def set_static_ip(adapter: str, ip: str, mask: str, gateway: str) -> tuple:
    cmd = f'netsh interface ip set address name="{adapter}" static {ip} {mask} {gateway} 1'
    return run_cmd(cmd)


def set_dhcp_ip(adapter: str) -> tuple:
    return run_cmd(f'netsh interface ip set address name="{adapter}" source=dhcp')


def set_static_dns(adapter: str, dns1: str, dns2: str = "") -> tuple:
    ok1, msg1 = run_cmd(f'netsh interface ip set dnsservers name="{adapter}" static {dns1} primary')
    if not ok1:
        return False, msg1
    if dns2:
        ok2, msg2 = run_cmd(f'netsh interface ip add dnsservers name="{adapter}" {dns2} index=2')
        if not ok2:
            return False, msg2
    return True, "DNS ثبت شد."


def set_dhcp_dns(adapter: str) -> tuple:
    return run_cmd(f'netsh interface ip set dnsservers name="{adapter}" source=dhcp')


def flush_dns_cache():
    run_cmd("ipconfig /flushdns")


# =====================================================================
# ۵. دکمه‌های پایدار با Container
# =====================================================================
def make_btn(text: str, on_click, is_primary: bool = True, width=None, height: int = 40):
    return ft.Container(
        content=make_text(
            text,
            size=12,
            color="white" if is_primary else COLOR_CREAM,
            bold=True,
            align=ft.TextAlign.CENTER,
        ),
        bgcolor=COLOR_ORANGE if is_primary else COLOR_CARD,
        border=None if is_primary else border_all(1, COLOR_BORDER),
        border_radius=8,
        padding=pad_symmetric(horizontal=12, vertical=8),
        alignment=align_center(),
        width=width,
        height=height,
        on_click=on_click,
    )


def make_card(content):
    return ft.Container(
        bgcolor=COLOR_CARD,
        padding=10,
        border_radius=8,
        border=border_all(1, COLOR_BORDER),
        content=content,
    )


def make_field(label, hint="", value="", width=400, disabled=False):
    return ft.TextField(
        label=label,
        hint_text=hint,
        value=value,
        disabled=disabled,
        width=width,
        text_align=ft.TextAlign.LEFT,
        bgcolor=COLOR_CARD,
        border_color=COLOR_BORDER,
        color=COLOR_CREAM,
    )


# =====================================================================
# ۶. رابط کاربری
# =====================================================================
def main(page: ft.Page):
    page.title = "NetSwitcher"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = COLOR_BG_DARK
    page.rtl = True
    page.padding = 14
    page.scroll = ft.ScrollMode.AUTO

    try:
        page.window.width = 440
        page.window.height = 760
        page.window.resizable = False
    except Exception:
        try:
            page.window_width = 440
            page.window_height = 760
            page.window_resizable = False
        except Exception:
            pass

    active_tab = {"name": "ip"}

    def notify(msg: str, is_error: bool = False):
        snack = ft.SnackBar(
            content=ft.Text(msg, color="white"),
            bgcolor="#991b1b" if is_error else "#166534",
        )
        try:
            if hasattr(page, "show_dialog"):
                page.show_dialog(snack)
            elif hasattr(page, "open"):
                page.open(snack)
            else:
                page.overlay.append(snack)
                snack.open = True
                page.update()
        except Exception:
            pass

    # ---------------- پروفایل‌ها
    saved_profiles = []
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_profiles = json.load(f)
        except Exception:
            saved_profiles = []
    if not saved_profiles:
        saved_profiles = [
            {"name": "مودم خانه (DHCP)", "dhcp": True, "dns_auto": True},
            {"name": "شبکه اداری (استاتیک)", "dhcp": False, "ip": "192.168.1.150", "mask": "255.255.255.0", "gateway": "192.168.1.1", "dns_auto": False, "dns1": "8.8.8.8", "dns2": "1.1.1.1"},
            {"name": "شکن ضدتحریم", "dhcp": True, "dns_auto": False, "dns1": "178.22.122.100", "dns2": "185.51.200.2"},
        ]

    # ---------------- کارت شبکه
    adapters = get_network_adapters() or ["Wi-Fi", "Ethernet"]
    DropdownOptionClass = getattr(ft, "DropdownOption", None) or getattr(ft.dropdown, "Option", None)
    dropdown_opts = [DropdownOptionClass(a) for a in adapters]

    adapter_dropdown = ft.Dropdown(
        label="کارت شبکه فعال",
        options=dropdown_opts,
        value=adapters[0],
        width=320,
        bgcolor=COLOR_CARD,
        border_color=COLOR_BORDER,
        color=COLOR_CREAM,
    )

    # ---------------- فیلدها
    dhcp_switch = make_switch("دریافت خودکار آی‌پی از مودم (DHCP)", True)
    ip_input = make_field("آدرس آی‌پی (IP Address)", "192.168.1.150", disabled=True)
    subnet_input = make_field("ساب‌نت ماسک (Subnet Mask)", value="255.255.255.0", disabled=True)
    gateway_input = make_field("پیش‌فرض گیت‌وی (Default Gateway)", "192.168.1.1", disabled=True)

    dns_auto_switch = make_switch("دریافت خودکار DNS از روتر", True)
    dns1_input = make_field("دی‌ان‌اس اول (Preferred DNS)", "178.22.122.100 یا 8.8.8.8", disabled=True)
    dns2_input = make_field("دی‌ان‌اس دوم (Alternate DNS)", "185.51.200.2 یا 1.1.1.1", disabled=True)

    new_profile_input = make_field("نام کانفیگ جدید", "یک نام دلخواه وارد کنید...", width=280)

    status_text = ft.Text("✅ دسترسی کامل Administrator فعال است", color=COLOR_SAND, size=11)

    # ---------------- رویدادها
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
            return
        try:
            info = get_adapter_info(name)
        except Exception as ex:
            status_text.value = f"⚠️ خطا در خواندن مشخصات: {ex}"
            page.update()
            return

        dhcp_switch.value = info.get("is_dhcp", True)
        ip_input.value = info.get("ip", "")
        subnet_input.value = info.get("mask", "255.255.255.0")
        gateway_input.value = info.get("gateway", "")
        dns_auto_switch.value = not bool(info.get("dns1"))
        dns1_input.value = info.get("dns1", "")
        dns2_input.value = info.get("dns2", "")

        ip_input.disabled = subnet_input.disabled = gateway_input.disabled = bool(dhcp_switch.value)
        dns1_input.disabled = dns2_input.disabled = bool(dns_auto_switch.value)
        status_text.value = f"مشخصات {name} با موفقیت بارگذاری شد."
        page.update()

    if hasattr(adapter_dropdown, "on_select"):
        adapter_dropdown.on_select = load_current_adapter_state
    else:
        adapter_dropdown.on_change = load_current_adapter_state

    def apply_dns_preset(preset_key):
        p = DNS_PRESETS.get(preset_key)
        if not p:
            return
        dns_auto_switch.value = False
        dns1_input.value = p["primary"]
        dns2_input.value = p["secondary"]
        dns1_input.disabled = dns2_input.disabled = False
        page.update()
        notify(f"دی‌ان‌اس {p['name']} درج شد.")

    def apply_network_changes(e=None):
        adapter = adapter_dropdown.value
        if not adapter:
            notify("هیچ کارت شبکه‌ای انتخاب نشده است.", is_error=True)
            return

        # اعتبارسنجی
        if not dhcp_switch.value:
            if not valid_ip(ip_input.value):
                notify("آدرس آی‌پی نامعتبر است.", is_error=True)
                return
            if not valid_mask(subnet_input.value):
                notify("ساب‌نت ماسک نامعتبر است.", is_error=True)
                return
            if not valid_ip(gateway_input.value):
                notify("آدرس گیت‌وی نامعتبر است.", is_error=True)
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

        status_text.value = "در حال اعمال تنظیمات روی کارت شبکه..."
        page.update()

        try:
            if dhcp_switch.value:
                ok, msg = set_dhcp_ip(adapter)
            else:
                ok, msg = set_static_ip(
                    adapter,
                    ip_input.value.strip(),
                    subnet_input.value.strip(),
                    gateway_input.value.strip(),
                )
            if not ok:
                raise RuntimeError(msg or "خطا در تنظیم آی‌پی")

            if dns_auto_switch.value:
                ok, msg = set_dhcp_dns(adapter)
            else:
                ok, msg = set_static_dns(
                    adapter,
                    dns1_input.value.strip(),
                    dns2_input.value.strip(),
                )
            if not ok:
                raise RuntimeError(msg or "خطا در تنظیم DNS")

            flush_dns_cache()
            status_text.value = "✅ تغییرات با موفقیت ذخیره شد!"
            notify("تنظیمات با موفقیت ثبت شدند.")
        except Exception as ex:
            status_text.value = f"⚠️ خطا: {ex}"
            notify(f"خطا در اعمال: {ex}", is_error=True)

        page.update()

    def save_current_config(e=None):
        name = new_profile_input.value.strip()
        if not name:
            notify("لطفاً نام کانفیگ را وارد کنید.", is_error=True)
            return
        saved_profiles.append({
            "name": name,
            "dhcp": bool(dhcp_switch.value),
            "ip": ip_input.value.strip(),
            "mask": subnet_input.value.strip(),
            "gateway": gateway_input.value.strip(),
            "dns_auto": bool(dns_auto_switch.value),
            "dns1": dns1_input.value.strip(),
            "dns2": dns2_input.value.strip(),
        })
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(saved_profiles, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        new_profile_input.value = ""
        switch_tab("settings")
        notify(f"کانفیگ «{name}» ذخیره شد.")

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

    def set_gateway(value):
        gateway_input.value = value
        page.update()

    def clear_cache(e=None):
        flush_dns_cache()
        notify("کش DNS پاک شد.")

    # ---------------- صفحات
    content_area = ft.Container(padding=pad_symmetric(vertical=10))

    def render_ip_view():
        return ft.Column([
            make_text("تغییر آدرس آی‌پی (IP)", 16, COLOR_CREAM, True),
            make_text("تنظیم دستی آی‌پی یا دریافت خودکار (DHCP)", 11, COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=15),
            dhcp_switch,
            ip_input,
            subnet_input,
            ft.Container(height=8),
            make_btn("💾 ذخیره و ثبت آدرس IP", apply_network_changes, True, width=400),
        ], spacing=10)

    def render_gateway_view():
        return ft.Column([
            make_text("تغییر دیفالت گیت‌وی (Default Gateway)", 16, COLOR_CREAM, True),
            make_text("تنظیم آدرس مودم یا روتر جهت اینترنت", 11, COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=15),
            gateway_input,
            make_card(ft.Column([
                make_text("💡 گیت‌وی‌های متداول مودم‌ها:", 11, COLOR_CREAM_MUTED),
                ft.Row([
                    make_btn("192.168.1.1", lambda e: set_gateway("192.168.1.1"), False, height=32),
                    make_btn("192.168.0.1", lambda e: set_gateway("192.168.0.1"), False, height=32),
                    make_btn("10.0.0.1", lambda e: set_gateway("10.0.0.1"), False, height=32),
                ], spacing=6, wrap=True),
            ], spacing=6)),
            ft.Container(height=8),
            make_btn("💾 ذخیره و اعمال گیت‌وی", apply_network_changes, True, width=400),
        ], spacing=10)

    def render_dns_view():
        return ft.Column([
            make_text("تغییر سرورهای دی‌ان‌اس (DNS)", 16, COLOR_CREAM, True),
            make_text("تنظیم DNSهای ضدتحریم یا عمومی جهانی", 11, COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=15),
            dns_auto_switch,
            make_text("پیش‌تنظیم‌های پرکاربرد (یک کلیک جهت درج):", 11, COLOR_CREAM_MUTED),
            ft.Row([
                make_btn("🛡️ شکن", lambda e: apply_dns_preset("shecan"), False, height=32),
                make_btn("⚡ ۴۰۳", lambda e: apply_dns_preset("403"), False, height=32),
                make_btn("🎮 الکترو", lambda e: apply_dns_preset("electro"), False, height=32),
                make_btn("🌐 1.1.1.1", lambda e: apply_dns_preset("cloudflare"), False, height=32),
                make_btn("🔍 8.8.8.8", lambda e: apply_dns_preset("google"), False, height=32),
            ], wrap=True, spacing=6),
            dns1_input,
            dns2_input,
            ft.Container(height=8),
            make_btn("💾 ذخیره و اعمال DNS در شبکه", apply_network_changes, True, width=400),
        ], spacing=10)

    def render_settings_view():
        profile_btns = [
            make_btn(f"📁 {prof.get('name', 'پروفایل')}", (lambda p: lambda e: load_profile(p))(prof), False, height=32)
            for prof in saved_profiles
        ]
        return ft.Column([
            make_text("⚙️ تنظیمات و مدیریت کانفیگ‌ها", 16, COLOR_CREAM, True),
            make_text("ذخیره تنظیمات فعلی و بارگذاری سریع پروفایل‌ها", 11, COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=12),

            make_card(ft.Column([
                make_text("ذخیره تنظیمات کارت به عنوان کانفیگ:", 12, COLOR_CREAM, True),
                ft.Row([
                    new_profile_input,
                    make_btn("💾 ذخیره", save_current_config, True, height=40),
                ], spacing=6),
            ], spacing=6)),

            make_card(ft.Column([
                make_text("پروفایل‌های ذخیره‌شده (کلیک برای لود):", 12, COLOR_CREAM, True),
                ft.Row(profile_btns, wrap=True, spacing=6),
            ], spacing=6)),

            make_card(ft.Row([
                make_text("پاکسازی کش DNS (flushdns):", 11, COLOR_CREAM),
                make_btn("🧹 پاکسازی", clear_cache, False, height=32),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)),
        ], spacing=10)

    def switch_tab(tab_name: str):
        active_tab["name"] = tab_name
        update_tab_styles()
        if tab_name == "ip":
            content_area.content = render_ip_view()
        elif tab_name == "gateway":
            content_area.content = render_gateway_view()
        elif tab_name == "dns":
            content_area.content = render_dns_view()
        elif tab_name == "settings":
            content_area.content = render_settings_view()
        page.update()

    # ---------------- تب‌های بالا
    def make_tab(label, name):
        return ft.Container(
            content=make_text(label, 12, COLOR_SAND, True, ft.TextAlign.CENTER),
            padding=pad_symmetric(horizontal=10, vertical=8),
            border_radius=8,
            expand=True,
            alignment=align_center(),
            on_click=lambda e: switch_tab(name),
        )

    btn_tab_ip = make_tab("🌐 آی‌پی", "ip")
    btn_tab_gateway = make_tab("🚪 گیت‌وی", "gateway")
    btn_tab_dns = make_tab("🛡️ دی‌ان‌اس", "dns")
    btn_tab_settings = make_tab("⚙️ کانفیگ", "settings")

    def update_tab_styles():
        for b, name in [
            (btn_tab_ip, "ip"),
            (btn_tab_gateway, "gateway"),
            (btn_tab_dns, "dns"),
            (btn_tab_settings, "settings"),
        ]:
            is_active = active_tab["name"] == name
            b.bgcolor = COLOR_ORANGE if is_active else COLOR_CARD
            b.content.color = "white" if is_active else COLOR_SAND

    update_tab_styles()

    header_app = ft.Row([
        ft.Row([
            ft.Text("⚡", size=18),
            make_text("NetSwitcher", 16, COLOR_CREAM, True),
        ], spacing=6),
        ft.Container(
            content=make_text("👑 ADMIN", 10, "#86efac", True),
            bgcolor="#14532d",
            padding=pad_symmetric(horizontal=8, vertical=4),
            border_radius=6,
        ),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    adapter_bar = ft.Row([
        adapter_dropdown,
        make_btn("🔄", load_current_adapter_state, False, width=44, height=44),
    ], spacing=6, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    nav_tabs_row = ft.Row([
        btn_tab_ip,
        btn_tab_gateway,
        btn_tab_dns,
        btn_tab_settings,
    ], spacing=6)

    page.add(
        ft.Column([
            header_app,
            ft.Divider(color=COLOR_BORDER, height=10),
            adapter_bar,
            nav_tabs_row,
            ft.Divider(color=COLOR_BORDER, height=10),
            content_area,
            ft.Divider(color=COLOR_BORDER, height=10),
            status_text,
        ], spacing=6)
    )

    switch_tab("ip")
    load_current_adapter_state()


# =====================================================================
# ۷. نقطه ورود
# =====================================================================
if __name__ == "__main__":
    ensure_admin()
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)