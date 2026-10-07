"""
NetSwitcher Pro - تغییر سریع آی‌پی، گیت‌وی و دی‌ان‌اس با کتابخانه Flet
نسخه اصلاح‌شده: سازگار با Flet قدیمی و جدید (0.2x تا 0.8x)، با اعتبارسنجی ورودی‌ها
"""

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

# سازگاری بین نسخه‌های مختلف Flet
PrimaryButton = getattr(ft, "Button", None) or ft.ElevatedButton
DropdownOption = getattr(ft, "DropdownOption", None) or ft.dropdown.Option


# ---------------------------------------------------------------- اعتبارسنجی
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
    # ماسک معتبر: ابتدا چند ۱ و سپس فقط ۰
    return "01" not in bits and bits != "0" * 32


def gateway_in_subnet(ip: str, mask: str, gateway: str) -> bool:
    try:
        network = ipaddress.IPv4Interface(f"{ip.strip()}/{mask.strip()}").network
        return ipaddress.IPv4Address(gateway.strip()) in network
    except ValueError:
        return False


# ------------------------------------------------------------------- برنامه
def main(page: ft.Page):
    page.title = "NetSwitcher Pro | تغییر سریع آی‌پی و DNS"
    page.theme_mode = "dark"
    page.rtl = True
    page.padding = 20
    page.scroll = "adaptive"

    try:
        page.window.width = 520
        page.window.height = 800
        page.window.resizable = False
    except Exception:
        try:
            page.window_width = 520
            page.window_height = 800
            page.window_resizable = False
        except Exception:
            pass

    def notify(msg: str, is_error: bool = False):
        snack = ft.SnackBar(
            content=ft.Text(msg),
            bgcolor="red" if is_error else "green",
        )
        try:
            if hasattr(page, "show_dialog"):      # Flet جدید
                page.show_dialog(snack)
            elif hasattr(page, "open"):           # Flet 0.2x
                page.open(snack)
            else:
                page.snack_bar = snack
                snack.open = True
                page.update()
        except Exception:
            pass

    admin_status = is_admin()

    # ۱. انتخاب کارت شبکه
    try:
        adapters = get_network_adapters() or []
    except Exception:
        adapters = []
    selected_adapter = adapters[0] if adapters else None

    adapter_dropdown = ft.Dropdown(
        label="کارت شبکه فعال",
        options=[DropdownOption(a) for a in adapters],
        value=selected_adapter,
        width=480,
    )

    # ۲. فیلدهای IP و Gateway (چپ‌چین چون اعداد انگلیسی هستند)
    left = ft.TextAlign.LEFT

    dhcp_switch = ft.Switch(
        label="دریافت خودکار آی‌پی از مودم (DHCP)",
        value=True,
        active_color="cyan",
    )
    ip_input = ft.TextField(
        label="آدرس آی‌پی (IP Address)",
        hint_text="مثال: 192.168.1.150",
        disabled=True, width=480, text_align=left,
    )
    subnet_input = ft.TextField(
        label="ساب‌نت ماسک (Subnet Mask)",
        value="255.255.255.0",
        disabled=True, width=480, text_align=left,
    )
    gateway_input = ft.TextField(
        label="پیش‌فرض گیت‌وی (Default Gateway)",
        hint_text="مثال: 192.168.1.1",
        disabled=True, width=480, text_align=left,
    )

    # ۳. فیلدهای DNS
    dns_auto_switch = ft.Switch(
        label="دریافت خودکار DNS از مودم",
        value=True,
        active_color="cyan",
    )
    dns1_input = ft.TextField(
        label="دی‌ان‌اس اول (Preferred DNS)",
        hint_text="مثال: 178.22.122.100 (شکن) یا 8.8.8.8",
        disabled=True, width=480, text_align=left,
    )
    dns2_input = ft.TextField(
        label="دی‌ان‌اس دوم (Alternate DNS) - اختیاری",
        hint_text="مثال: 185.51.200.2 یا 1.1.1.1",
        disabled=True, width=480, text_align=left,
    )

    status_text = ft.Text("آماده به کار", color="grey", size=13)

    # ------------------------------------------------------------ رویدادها
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
            status_text.value = "هیچ کارت شبکه‌ای پیدا نشد."
            page.update()
            return
        try:
            info = get_adapter_info(name) or {}
        except Exception as ex:
            status_text.value = f"⚠️ خواندن اطلاعات کارت ناموفق بود: {ex}"
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

        status_text.value = f"تنظیمات کارت {name} فراخوانی شد."
        page.update()

    # در Flet جدید on_select و در قدیمی on_change
    if hasattr(adapter_dropdown, "on_select"):
        adapter_dropdown.on_select = load_current_adapter_state
    else:
        adapter_dropdown.on_change = load_current_adapter_state

    # پیش‌تنظیم‌های DNS
    def apply_dns_preset(preset_key):
        preset = DNS_PRESETS.get(preset_key)
        if not preset:
            notify("این پیش‌تنظیم یافت نشد.", is_error=True)
            return
        dns_auto_switch.value = False
        dns1_input.value = preset.get("primary", "")
        dns2_input.value = preset.get("secondary", "")
        dns1_input.disabled = dns2_input.disabled = False
        page.update()
        notify(f"دی‌ان‌اس {preset.get('name', preset_key)} درج شد. برای اعمال نهایی ذخیره را بزنید.")

    def preset_button(label, key):
        return ft.OutlinedButton(label, on_click=lambda e, k=key: apply_dns_preset(k))

    dns_preset_chips = ft.Row(
        wrap=True,
        spacing=8,
        run_spacing=8,
        controls=[
            preset_button("🛡️ شکن", "shecan"),
            preset_button("⚡ ۴۰۳ آنلاین", "403"),
            preset_button("🎮 الکترو", "electro"),
            preset_button("🌐 کلودفلر", "cloudflare"),
            preset_button("🔍 گوگل", "google"),
        ],
    )

    # -------------------------------------------------------- اعمال تغییرات
    save_button = PrimaryButton(
        "💾 ذخیره و اعمال در شبکه",
        style=ft.ButtonStyle(bgcolor="cyan", color="black"),
    )

    def set_busy(busy: bool):
        save_button.disabled = busy
        page.update()

    def validate() -> str | None:
        """در صورت خطا، متن خطا را برمی‌گرداند؛ وگرنه None."""
        if not adapter_dropdown.value:
            return "هیچ کارت شبکه‌ای انتخاب نشده است."

        if not dhcp_switch.value:
            ip, mask, gw = ip_input.value, subnet_input.value, gateway_input.value
            if not valid_ip(ip):
                return "آدرس IP نامعتبر است."
            if not valid_mask(mask):
                return "ساب‌نت ماسک نامعتبر است."
            if not valid_ip(gw):
                return "آدرس Gateway نامعتبر است."
            if not gateway_in_subnet(ip, mask, gw):
                return "Gateway باید در همان رنج IP و ساب‌نت باشد."

        if not dns_auto_switch.value:
            if not valid_ip(dns1_input.value):
                return "دی‌ان‌اس اول نامعتبر است."
            if dns2_input.value.strip() and not valid_ip(dns2_input.value):
                return "دی‌ان‌اس دوم نامعتبر است."
        return None

    def apply_changes(e):
        if not admin_status:
            notify("برای تغییر تنظیمات شبکه باید برنامه را با دسترسی Administrator اجرا کنید.", is_error=True)
            return

        error = validate()
        if error:
            status_text.value = f"⚠️ {error}"
            notify(error, is_error=True)
            page.update()
            return

        adapter = adapter_dropdown.value
        status_text.value = "در حال اعمال تنظیمات شبکه..."
        set_busy(True)

        errors = []
        try:
            # IP و Gateway
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
                errors.append(f"IP: {msg}")

            # DNS
            if dns_auto_switch.value:
                ok, msg = set_dhcp_dns(adapter)
            else:
                ok, msg = set_static_dns(
                    adapter,
                    dns1_input.value.strip(),
                    dns2_input.value.strip(),
                )
            if not ok:
                errors.append(f"DNS: {msg}")

            # پاکسازی کش DNS
            try:
                flush_dns_cache()
            except Exception:
                pass
        except Exception as ex:
            errors.append(str(ex))
        finally:
            set_busy(False)

        if errors:
            text = " | ".join(errors)
            status_text.value = f"⚠️ خطا: {text}"
            notify(f"خطا در اعمال: {text}", is_error=True)
        else:
            status_text.value = "✅ تغییرات با موفقیت در ویندوز ذخیره شد!"
            notify("تنظیمات با موفقیت در کارت شبکه ثبت شد.")
        page.update()

    save_button.on_click = apply_changes

    def do_elevate(e):
        try:
            elevate_privileges()
        except Exception as ex:
            notify(f"ارتقا به Admin ناموفق بود: {ex}", is_error=True)

    # ------------------------------------------------------------ رابط کاربری
    ip_card = ft.Card(
        elevation=2,
        content=ft.Container(
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("⚙️ تنظیمات آدرس IP و Gateway", weight="bold", size=15),
                    dhcp_switch,
                    ip_input,
                    subnet_input,
                    gateway_input,
                ],
            ),
        ),
    )

    dns_card = ft.Card(
        elevation=2,
        content=ft.Container(
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("🌐 تنظیمات سرورهای DNS", weight="bold", size=15),
                    dns_auto_switch,
                    ft.Text("پیش‌تنظیمات آماده (یک کلیک):", size=12, color="grey"),
                    dns_preset_chips,
                    dns1_input,
                    dns2_input,
                ],
            ),
        ),
    )

    admin_alert_box = ft.Container(
        visible=not admin_status,
        bgcolor="#78350f",
        border_radius=10,
        padding=12,
        content=ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("⚠️ هشدار: برنامه با دسترسی Administrator اجرا نشده است.",
                                weight="bold", color="#fef3c7", size=13),
                        ft.Text("برای تغییر کارت شبکه، باید برنامه با دسترسی ادمین باز شود.",
                                color="#fde68a", size=11),
                    ],
                    expand=True,
                    spacing=2,
                ),
                PrimaryButton(
                    "ارتقا به Admin",
                    style=ft.ButtonStyle(bgcolor="#f59e0b", color="black"),
                    on_click=do_elevate,
                ),
            ]
        ),
    )

    action_buttons = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.OutlinedButton("🔄 بازیابی اطلاعات کارت", on_click=load_current_adapter_state),
            save_button,
        ],
    )

    page.add(
        admin_alert_box,
        ft.Column(
            [
                ft.Text("⚡ NetSwitcher Pro", size=22, weight="bold"),
                ft.Text("مدیریت سریع کارت شبکه، IP، Gateway و DNS", size=12, color="grey"),
            ],
            spacing=2,
        ),
        ft.Divider(height=10, color="transparent"),
        adapter_dropdown,
        ip_card,
        dns_card,
        action_buttons,
        ft.Container(
            padding=10,
            content=ft.Row([status_text], alignment=ft.MainAxisAlignment.CENTER),
        ),
    )

    load_current_adapter_state()


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)              # Flet جدید
    else:
        ft.app(target=main)       # Flet قدیمی