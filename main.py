"""
NetSwitcher Pro - تغییر سریع آی‌پی، گیت‌وی و دی‌ان‌اس با کتابخانه Flet
توسعه داده شده برای ویندوز ۱۰ و ۱۱ (بدون نیاز به مراجعه به Control Panel)
"""

import flet as ft
from network_manager import (
    get_network_adapters,
    get_adapter_info,
    set_static_ip,
    set_dhcp_ip,
    set_static_dns,
    set_dhcp_dns,
    flush_dns_cache,
    is_admin
)
from presets import DNS_PRESETS, DEFAULT_PROFILES
from admin_helper import elevate_privileges


def main(page: ft.Page):
    # تنظیمات پنجره اصلی
    page.title = "SwIP"
    page.window.width = 540
    page.window.height = 760
    page.window.resizable = False
    page.window.maximizable = False
    page.theme_mode = ft.ThemeMode.DARK
    page.rtl = True  # پشتیبانی کامل از چینش راست‌به‌چپ زبان فارسی
    page.padding = 20
    page.scroll = ft.ScrollMode.ADAPTIVE

    # بررسی دسترسی Administrator در ابتدای اجرا
    admin_status = is_admin()

    # عناصر فرم
    adapters = get_network_adapters()
    selected_adapter = adapters[0] if adapters else "Wi-Fi"

    adapter_dropdown = ft.Dropdown(
        label="کارت شبکه فعال",
        options=[ft.dropdown.Option(a) for a in adapters],
        value=selected_adapter,
        width=480,
        prefix_icon=ft.Icons.SETTINGS_ETHERNET,
    )

    # سوییچ حالت DHCP
    dhcp_switch = ft.Switch(
        label="دریافت خودکار آی‌پی از مودم (DHCP)",
        value=True,
        active_color=ft.Colors.CYAN_400,
    )

    # فیلدهای ورودی آی‌پی
    ip_input = ft.TextField(
        label="آدرس آی‌پی (IP Address)",
        hint_text="مثال: 192.168.1.150",
        prefix_icon=ft.Icons.ROUTER,
        disabled=True,
        width=480,
    )

    subnet_input = ft.TextField(
        label="ساب‌نت ماسک (Subnet Mask)",
        value="255.255.255.0",
        prefix_icon=ft.Icons.GRID_VIEW,
        disabled=True,
        width=480,
    )

    gateway_input = ft.TextField(
        label="پیش‌فرض گیت‌وی (Default Gateway)",
        hint_text="مثال: 192.168.1.1",
        prefix_icon=ft.Icons.DNS,
        disabled=True,
        width=480,
    )

    # فیلدهای ورودی DNS
    dns_auto_switch = ft.Switch(
        label="دریافت خودکار DNS از مودم",
        value=True,
        active_color=ft.Colors.CYAN_400,
    )

    dns1_input = ft.TextField(
        label="دی‌ان‌اس اول (Preferred DNS)",
        hint_text="مثال: 178.22.122.100 (شکن) یا 8.8.8.8",
        prefix_icon=ft.Icons.SECURITY,
        disabled=True,
        width=480,
    )

    dns2_input = ft.TextField(
        label="دی‌ان‌اس دوم (Alternate DNS)",
        hint_text="مثال: 185.51.200.2 یا 1.1.1.1",
        prefix_icon=ft.Icons.SECURITY_OUTLINED,
        disabled=True,
        width=480,
    )

    status_text = ft.Text(
        value="آماده به کار",
        color=ft.Colors.GREY_400,
        size=13,
    )

    # به‌روزرسانی فعال بودن فیلدها با تغییر سوییچ‌ها
    def on_dhcp_toggle(e):
        is_auto = dhcp_switch.value
        ip_input.disabled = is_auto
        subnet_input.disabled = is_auto
        gateway_input.disabled = is_auto
        page.update()

    def on_dns_auto_toggle(e):
        is_auto = dns_auto_switch.value
        dns1_input.disabled = is_auto
        dns2_input.disabled = is_auto
        page.update()

    dhcp_switch.on_change = on_dhcp_toggle
    dns_auto_switch.on_change = on_dns_auto_toggle

    # بارگذاری وضعیت فعلی کارت شبکه انتخاب شده
    def load_current_adapter_state():
        info = get_adapter_info(adapter_dropdown.value)
        dhcp_switch.value = info["is_dhcp"]
        ip_input.value = info.get("ip", "")
        subnet_input.value = info.get("mask", "255.255.255.0")
        gateway_input.value = info.get("gateway", "")

        has_custom_dns = bool(info.get("dns1"))
        dns_auto_switch.value = not has_custom_dns
        dns1_input.value = info.get("dns1", "")
        dns2_input.value = info.get("dns2", "")

        on_dhcp_toggle(None)
        on_dns_auto_toggle(None)
        status_text.value = f"تنظیمات فعلی کارت {adapter_dropdown.value} فراخوانی شد."
        page.update()

    adapter_dropdown.on_change = lambda e: load_current_adapter_state()

    # دکمه‌های پیش‌تنظیم DNS سریع (Quick Presets)
    def apply_dns_preset(preset_key):
        preset = DNS_PRESETS.get(preset_key)
        if preset:
            dns_auto_switch.value = False
            on_dns_auto_toggle(None)
            dns1_input.value = preset["primary"]
            dns2_input.value = preset["secondary"]
            page.snack_bar = ft.SnackBar(
                ft.Text(f"دی‌ان‌اس {preset['name']} درج شد. برای اعمال نهایی دکمه ذخیره را بزنید."),
                bgcolor=ft.Colors.INDIGO_900
            )
            page.snack_bar.open = True
            page.update()

    dns_preset_chips = ft.Row(
        wrap=True,
        spacing=8,
        controls=[
            ft.ActionChip(
                label=ft.Text("🛡️ شکن (ضد تحریم)"),
                on_click=lambda e: apply_dns_preset("shecan")
            ),
            ft.ActionChip(
                label=ft.Text("⚡ ۴۰۳ آنلاین"),
                on_click=lambda e: apply_dns_preset("403")
            ),
            ft.ActionChip(
                label=ft.Text("🎮 الکترو گیمینگ"),
                on_click=lambda e: apply_dns_preset("electro")
            ),
            ft.ActionChip(
                label=ft.Text("🌐 کلودفلر (1.1.1.1)"),
                on_click=lambda e: apply_dns_preset("cloudflare")
            ),
            ft.ActionChip(
                label=ft.Text("🔍 گوگل (8.8.8.8)"),
                on_click=lambda e: apply_dns_preset("google")
            ),
        ]
    )

    # اعمال تغییرات
    def apply_changes(e):
        adapter = adapter_dropdown.value
        status_text.value = "در حال اعمال تغییرات روی شبکه..."
        page.update()

        # ۱. تنظیم آدرس آی‌پی و گیت‌وی
        if dhcp_switch.value:
            ok_ip, msg_ip = set_dhcp_ip(adapter)
        else:
            if not ip_input.value or not gateway_input.value:
                page.snack_bar = ft.SnackBar(
                    ft.Text("خطا: آدرس IP و Gateway نمی‌توانند خالی باشند!"),
                    bgcolor=ft.Colors.RED_800
                )
                page.snack_bar.open = True
                page.update()
                return
            ok_ip, msg_ip = set_static_ip(
                adapter, ip_input.value.strip(), subnet_input.value.strip(), gateway_input.value.strip()
            )

        # ۲. تنظیم دی‌ان‌اس
        if dns_auto_switch.value:
            ok_dns, msg_dns = set_dhcp_dns(adapter)
        else:
            ok_dns, msg_dns = set_static_dns(
                adapter, dns1_input.value.strip(), dns2_input.value.strip()
            )

        # ۳. پاکسازی کش DNS ویندوز
        flush_dns_cache()

        if ok_ip and ok_dns:
            status_text.value = "✅ تغییرات با موفقیت در ویندوز ثبت شدند!"
            page.snack_bar = ft.SnackBar(
                ft.Text("تنظیمات با موفقیت اعمال شدند و کش DNS پاک شد."),
                bgcolor=ft.Colors.GREEN_800
            )
        else:
            status_text.value = f"⚠️ خطا: {msg_ip or msg_dns}"
            page.snack_bar = ft.SnackBar(
                ft.Text(f"خطا در اعمال: {msg_ip or msg_dns}"),
                bgcolor=ft.Colors.RED_800
            )

        page.snack_bar.open = True
        page.update()

    # چیدمان کارت‌ها
    ip_card = ft.Card(
        elevation=2,
        content=ft.Container(
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.NETWORK_CHECK, color=ft.Colors.CYAN_400),
                        ft.Text("تنظیمات آدرس IP و Gateway", weight=ft.FontWeight.BOLD, size=16),
                    ]),
                    dhcp_switch,
                    ip_input,
                    subnet_input,
                    gateway_input,
                ]
            )
        )
    )

    dns_card = ft.Card(
        elevation=2,
        content=ft.Container(
            padding=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.DNS_ROUNDED, color=ft.Colors.CYAN_400),
                        ft.Text("تنظیمات سرورهای DNS", weight=ft.FontWeight.BOLD, size=16),
                    ]),
                    dns_auto_switch,
                    ft.Text("پیش‌تنظیمات آماده (یک کلیک):", size=12, color=ft.Colors.GREY_400),
                    dns_preset_chips,
                    dns1_input,
                    dns2_input,
                ]
            )
        )
    )

    admin_warning = ft.Banner(
        bgcolor=ft.Colors.AMBER_900,
        leading=ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER_200, size=36),
        content=ft.Text(
            "برنامه با مجوز Administrator اجرا نشده است. برای اعمال تغییرات در کارت شبکه ویندوز، دسترسی ادمین الزامی است.",
            color=ft.Colors.AMBER_100
        ),
        actions=[
            ft.TextButton(
                "ارتقا به Admin (Run as Admin)",
                on_click=lambda e: elevate_privileges()
            )
        ]
    )

    if not admin_status:
        page.banner = admin_warning
        admin_warning.open = True

    # دکمه‌های پایینی
    action_buttons = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.OutlinedButton(
                "بازیابی تنظیمات کارت",
                icon=ft.Icons.REFRESH,
                on_click=lambda e: load_current_adapter_state(),
            ),
            ft.ElevatedButton(
                "ذخیره و اعمال در شبکه",
                icon=ft.Icons.CHECK_CIRCLE,
                bgcolor=ft.Colors.CYAN_600,
                color=ft.Colors.WHITE,
                on_click=apply_changes,
            ),
        ]
    )

    # اضافه کردن عناصر به صفحه
    page.add(
        ft.Row([
            ft.Icon(ft.Icons.SPEED, size=32, color=ft.Colors.CYAN_400),
            ft.Column([
                ft.Text("NetSwitcher Pro", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("مدیریت سریع کارت شبکه، IP، Gateway و DNS", size=12, color=ft.Colors.GREY_400),
            ], spacing=2)
        ]),
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        adapter_dropdown,
        ip_card,
        dns_card,
        action_buttons,
        ft.Container(
            padding=ft.padding.only(top=10),
            content=ft.Row([
                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.GREY_500),
                status_text,
            ], alignment=ft.MainAxisAlignment.CENTER)
        )
    )

    # بارگذاری اطلاعات کارت در شروع
    load_current_adapter_state()


if __name__ == "__main__":
    ft.app(target=main)
