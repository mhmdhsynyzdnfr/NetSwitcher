"""
NetSwitcher Pro - Fast IP, Gateway, and DNS switcher desktop app with Flet
Design: Vertical (like Windows Calculator), 440x760 pixels
Warm palette: Orange, Cream, and Brown
"""

import json
import os
import flet as ft

# وارد کردن ماژول‌های پروژه
from network_manager import (
    get_network_adapters, get_active_internet_adapter, get_adapter_info,
    set_static_ip, set_dhcp_ip, set_static_dns, set_dhcp_dns, flush_dns_cache
)
from admin_helper import ensure_admin
from presets import DNS_PRESETS

# =====================================================================
# 1. Color Palette & Config Files
# =====================================================================
COLOR_BG_DARK = "#1a120c"
COLOR_CARD = "#281a12"
COLOR_BORDER = "#483122"
COLOR_ORANGE = "#ea580c"
COLOR_CREAM = "#fef3c7"
COLOR_CREAM_MUTED = "#fed7aa"
COLOR_SAND = "#d8c2ad"

CONFIG_FILE = "saved_profiles.json"
SETTINGS_FILE = "app_settings.json"

# =====================================================================
# 2. Settings & Compatibility Functions
# =====================================================================
def get_setting(key, default):
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get(key, default)
    except Exception:
        return default

def set_setting(key, value):
    try:
        data = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[key] = value
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass

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

# =====================================================================
# 3. UI Components Helpers
# =====================================================================
def make_btn(text: str, on_click, is_primary: bool = True, width=None, height: int = 40):
    return ft.Container(
        content=ft.Text(text, size=12, color="white" if is_primary else COLOR_CREAM, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
        bgcolor=COLOR_ORANGE if is_primary else COLOR_CARD,
        border=None if is_primary else border_all(1, COLOR_BORDER),
        border_radius=8,
        padding=pad_symmetric(horizontal=12, vertical=8),
        alignment=align_center(), width=width, height=height, on_click=on_click,
    )

def make_card(content):
    return ft.Container(bgcolor=COLOR_CARD, padding=10, border_radius=8, border=border_all(1, COLOR_BORDER), content=content)

def make_field(label, hint="", value="", width=400, disabled=False):
    return ft.TextField(label=label, hint_text=hint, value=value, disabled=disabled, width=width, text_align=ft.TextAlign.LEFT, bgcolor=COLOR_CARD, border_color=COLOR_BORDER, color=COLOR_CREAM)


# =====================================================================
# 4. Main App
# =====================================================================
def main(page: ft.Page):
    page.title = "NetSwitcher"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = COLOR_BG_DARK
    page.rtl = False
    page.padding = 14
    page.scroll = ft.ScrollMode.AUTO

    try:
        page.window.width = 440; page.window.height = 760; page.window.resizable = False
    except Exception:
        try:
            page.window_width = 440; page.window_height = 760; page.window_resizable = False
        except Exception: pass

    active_tab = {"name": "ip"}

    def notify(msg: str, is_error: bool = False):
        snack = ft.SnackBar(content=ft.Text(msg, color="white"), bgcolor="#991b1b" if is_error else "#166534")
        try:
            if hasattr(page, "show_dialog"): page.show_dialog(snack)
            elif hasattr(page, "open"): page.open(snack)
            else: page.overlay.append(snack); snack.open = True; page.update()
        except: pass

    saved_profiles = []
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f: saved_profiles = json.load(f)
        except: pass

    adapters = get_network_adapters()
    default_adapter = get_active_internet_adapter(adapters)

    DropdownOptionClass = getattr(ft, "DropdownOption", None) or getattr(ft.dropdown, "Option", None)
    dropdown_opts = [DropdownOptionClass(a) for a in adapters]

    adapter_dropdown = ft.Dropdown(
        label="Active Network Adapter", options=dropdown_opts, value=default_adapter,
        width=320, bgcolor=COLOR_CARD, border_color=COLOR_BORDER, color=COLOR_CREAM,
    )

    dhcp_switch = ft.Switch(label="Obtain IP address automatically (DHCP)", value=True, active_color=COLOR_ORANGE)
    ip_input = make_field("IP Address", "192.168.1.150", disabled=True)
    subnet_input = make_field("Subnet Mask", value="255.255.255.0", disabled=True)
    gateway_input = make_field("Default Gateway", "192.168.1.1", disabled=True)

    dns_auto_switch = ft.Switch(label="Obtain DNS server address automatically", value=True, active_color=COLOR_ORANGE)
    dns1_input = make_field("Preferred DNS", "178.22.122.100 or 8.8.8.8", disabled=True)
    dns2_input = make_field("Alternate DNS", "185.51.200.2 or 1.1.1.1", disabled=True)

    new_profile_input = make_field("New Profile Name", "Enter a custom name...", width=280)
    status_text = ft.Text("✅ Full Administrator access active", color=COLOR_SAND, size=11)

    def on_dhcp_toggle(e=None):
        auto = bool(dhcp_switch.value)
        ip_input.disabled = subnet_input.disabled = gateway_input.disabled = auto
        page.update()

    def on_dns_auto_toggle(e=None):
        dns1_input.disabled = dns2_input.disabled = bool(dns_auto_switch.value)
        page.update()

    dhcp_switch.on_change = on_dhcp_toggle
    dns_auto_switch.on_change = on_dns_auto_toggle

    def load_current_adapter_state(e=None):
        name = adapter_dropdown.value
        if not name: return
        try: info = get_adapter_info(name)
        except Exception as ex: status_text.value = f"⚠️ Error reading properties: {ex}"; page.update(); return

        dhcp_switch.value = info.get("is_dhcp", True)
        ip_input.value = info.get("ip", "")
        subnet_input.value = info.get("mask", "255.255.255.0")
        gateway_input.value = info.get("gateway", "")
        dns_auto_switch.value = not bool(info.get("dns1"))
        dns1_input.value = info.get("dns1", "")
        dns2_input.value = info.get("dns2", "")

        ip_input.disabled = subnet_input.disabled = gateway_input.disabled = bool(dhcp_switch.value)
        dns1_input.disabled = dns2_input.disabled = bool(dns_auto_switch.value)
        status_text.value = f"Properties of {name} loaded successfully."
        page.update()

    if hasattr(adapter_dropdown, "on_select"):
        adapter_dropdown.on_select = load_current_adapter_state
    else:
        adapter_dropdown.on_change = load_current_adapter_state

    def apply_dns_preset(preset_key):
        p = DNS_PRESETS.get(preset_key)
        if not p: return
        dns_auto_switch.value = False
        dns1_input.value = p["primary"]
        dns2_input.value = p["secondary"]
        dns1_input.disabled = dns2_input.disabled = False
        page.update()
        notify(f"DNS {p['name']} inserted.")

    def apply_network_changes(e=None):
        adapter = adapter_dropdown.value
        if not adapter: return notify("No network adapter selected.", is_error=True)

        status_text.value = "Applying settings to network adapter..."
        page.update()

        try:
            if dhcp_switch.value: ok, msg = set_dhcp_ip(adapter)
            else: ok, msg = set_static_ip(adapter, ip_input.value.strip(), subnet_input.value.strip(), gateway_input.value.strip())
            if not ok: raise RuntimeError(msg or "Error setting IP")

            if dns_auto_switch.value: ok, msg = set_dhcp_dns(adapter)
            else: ok, msg = set_static_dns(adapter, dns1_input.value.strip(), dns2_input.value.strip())
            if not ok: raise RuntimeError(msg or "Error setting DNS")

            flush_dns_cache()
            status_text.value = "✅ Changes saved successfully!"
            notify("Settings applied successfully.")
            load_current_adapter_state()
        except Exception as ex:
            status_text.value = f"⚠️ Error: {ex}"
            notify(f"Error applying: {ex}", is_error=True)
        page.update()

    def save_current_config(e=None):
        name = new_profile_input.value.strip()
        if not name: return notify("Please enter a profile name.", is_error=True)
        saved_profiles.append({
            "name": name, "dhcp": bool(dhcp_switch.value), "ip": ip_input.value.strip(),
            "mask": subnet_input.value.strip(), "gateway": gateway_input.value.strip(),
            "dns_auto": bool(dns_auto_switch.value), "dns1": dns1_input.value.strip(), "dns2": dns2_input.value.strip(),
        })
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(saved_profiles, f, ensure_ascii=False, indent=2)
        except: pass
        new_profile_input.value = ""
        switch_tab("settings")
        notify(f"Profile '{name}' saved.")

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
        notify(f"Profile '{prof.get('name')}' loaded. Click Save to apply to network.")

    def set_gateway(value):
        gateway_input.value = value
        page.update()

    def clear_cache(e=None):
        flush_dns_cache()
        notify("DNS cache cleared.")

    def pin_current_tab(e=None):
        set_setting("pinned_tab", active_tab["name"])
        notify("📌 Current tab pinned for app startup.")

    # ---------------- Views & Tabs
    content_area = ft.Container(padding=pad_symmetric(vertical=10))

    def render_ip_view():
        return ft.Column([
            ft.Text("Change IP Address", size=16, color=COLOR_CREAM, weight=ft.FontWeight.BOLD),
            ft.Text("Set IP manually or obtain automatically (DHCP)", size=11, color=COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=15),
            dhcp_switch, ip_input, subnet_input, ft.Container(height=8),
            make_btn("💾 Save & Apply IP", apply_network_changes, True, width=400),
        ], spacing=10)

    def render_gateway_view():
        return ft.Column([
            ft.Text("Change Default Gateway", size=16, color=COLOR_CREAM, weight=ft.FontWeight.BOLD),
            ft.Text("Set modem or router address for internet", size=11, color=COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=15),
            gateway_input,
            make_card(ft.Column([
                ft.Text("💡 Common modem gateways:", size=11, color=COLOR_CREAM_MUTED),
                ft.Row([
                    make_btn("192.168.1.1", lambda e: set_gateway("192.168.1.1"), False, height=32),
                    make_btn("192.168.0.1", lambda e: set_gateway("192.168.0.1"), False, height=32),
                    make_btn("10.0.0.1", lambda e: set_gateway("10.0.0.1"), False, height=32),
                ], spacing=6, wrap=True),
            ], spacing=6)),
            ft.Container(height=8),
            make_btn("💾 Save & Apply Gateway", apply_network_changes, True, width=400),
        ], spacing=10)

    def render_dns_view():
        return ft.Column([
            ft.Text("Change DNS Servers", size=16, color=COLOR_CREAM, weight=ft.FontWeight.BOLD),
            ft.Text("Set Anti-Sanction or Global Public DNS", size=11, color=COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=15),
            dns_auto_switch,
            ft.Text("Popular presets (click to insert):", size=11, color=COLOR_CREAM_MUTED),
            ft.Row([
                make_btn("🛡️ Shecan", lambda e: apply_dns_preset("shecan"), False, height=32),
                make_btn("⚡ 403", lambda e: apply_dns_preset("403"), False, height=32),
                make_btn("🎮 Electro", lambda e: apply_dns_preset("electro"), False, height=32),
                make_btn("🌐 1.1.1.1", lambda e: apply_dns_preset("cloudflare"), False, height=32),
                make_btn("🔍 8.8.8.8", lambda e: apply_dns_preset("google"), False, height=32),
            ], wrap=True, spacing=6),
            dns1_input, dns2_input, ft.Container(height=8),
            make_btn("💾 Save & Apply DNS", apply_network_changes, True, width=400),
        ], spacing=10)

    def render_settings_view():
        profile_btns = [make_btn(f"📁 {p.get('name', 'Profile')}", (lambda x: lambda e: load_profile(x))(p), False, height=32) for p in saved_profiles]
        return ft.Column([
            ft.Text("⚙️ Settings & Profiles", size=16, color=COLOR_CREAM, weight=ft.FontWeight.BOLD),
            ft.Text("Save current settings and quickly load profiles", size=11, color=COLOR_SAND),
            ft.Divider(color=COLOR_BORDER, height=12),
            make_card(ft.Column([
                ft.Text("Save adapter settings as profile:", size=12, color=COLOR_CREAM, weight=ft.FontWeight.BOLD),
                ft.Row([new_profile_input, make_btn("💾 Save", save_current_config, True, height=40)], spacing=6),
            ], spacing=6)),
            make_card(ft.Column([
                ft.Text("Saved Profiles (Click to load):", size=12, color=COLOR_CREAM, weight=ft.FontWeight.BOLD),
                ft.Row(profile_btns, wrap=True, spacing=6) if profile_btns else ft.Text("No profiles saved", size=10, color=COLOR_SAND),
            ], spacing=6)),
            make_card(ft.Row([
                ft.Text("Clear DNS Cache (flushdns):", size=11, color=COLOR_CREAM),
                make_btn("🧹 Clear", clear_cache, False, height=32),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)),
        ], spacing=10)

    def switch_tab(tab_name: str):
        active_tab["name"] = tab_name
        for b, n in [(btn_tab_ip, "ip"), (btn_tab_gateway, "gateway"), (btn_tab_dns, "dns"), (btn_tab_settings, "settings")]:
            is_active = (active_tab["name"] == n)
            b.bgcolor = COLOR_ORANGE if is_active else COLOR_CARD
            b.content.color = "white" if is_active else COLOR_SAND

        if tab_name == "ip": content_area.content = render_ip_view()
        elif tab_name == "gateway": content_area.content = render_gateway_view()
        elif tab_name == "dns": content_area.content = render_dns_view()
        elif tab_name == "settings": content_area.content = render_settings_view()
        page.update()

    def make_tab(label, name):
        return ft.Container(
            content=ft.Text(label, size=10, color=COLOR_SAND, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER, no_wrap=True),
            height=40, border_radius=8, expand=True, alignment=align_center(), on_click=lambda e: switch_tab(name),
        )

    btn_tab_ip = make_tab("🌐 IP", "ip")
    btn_tab_gateway = make_tab("🚪 Gateway", "gateway")
    btn_tab_dns = make_tab("🛡️ DNS", "dns")
    btn_tab_settings = make_tab("⚙️ Config", "settings")
    btn_pin = make_btn("📌", pin_current_tab, False, width=40, height=40)

    header_app = ft.Row([
        ft.Row([ft.Text("⚡", size=18), ft.Text("NetSwitcher", size=16, color=COLOR_CREAM, weight=ft.FontWeight.BOLD)], spacing=6),
        ft.Container(
            content=ft.Text("👑 ADMIN", size=10, color="#86efac", weight=ft.FontWeight.BOLD),
            bgcolor="#14532d", padding=pad_symmetric(horizontal=8, vertical=4), border_radius=6,
        ),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    adapter_bar = ft.Row([
        adapter_dropdown,
        make_btn("🔄", load_current_adapter_state, False, width=44, height=44),
    ], spacing=6, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    nav_tabs_row = ft.Row([btn_tab_ip, btn_tab_gateway, btn_tab_dns, btn_tab_settings, btn_pin], spacing=6)

    page.add(
        ft.Column([
            header_app, ft.Divider(color=COLOR_BORDER, height=10),
            adapter_bar, nav_tabs_row, ft.Divider(color=COLOR_BORDER, height=10),
            content_area, ft.Divider(color=COLOR_BORDER, height=10), status_text,
        ], spacing=6)
    )

    start_tab = get_setting("pinned_tab", "ip")
    switch_tab(start_tab)
    load_current_adapter_state()

if __name__ == "__main__":
    ensure_admin()
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)