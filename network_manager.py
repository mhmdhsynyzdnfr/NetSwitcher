"""
ماژول هسته شبکه برای اجرای دستورات netsh و ارتباط با کارت‌های شبکه ویندوز
"""

import subprocess
import re
import ipaddress
import socket

def run_command(cmd: str) -> tuple[bool, str]:
    """اجرای ایمن دستورات خط فرمان با کدگذاری مناسب ویندوز"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            encoding='utf-8',
            errors='replace'
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or result.stdout.strip()
    except Exception as e:
        return False, str(e)


def get_network_adapters() -> list[str]:
    """استخراج لیست کارت‌های شبکه متصل و فعال"""
    ok, output = run_command('powershell -Command "(Get-NetAdapter | Where-Object {$_.Status -eq \'Up\'}).Name"')
    if ok and output.strip():
        return [line.strip() for line in output.splitlines() if line.strip()]

    ok, output = run_command('netsh interface show interface')
    adapters = []
    if ok:
        for line in output.splitlines():
            if "Enabled" in line or "Connected" in line:
                parts = re.split(r'\s{2,}', line.strip())
                if len(parts) >= 4:
                    adapter_name = parts[3].strip()
                    adapters.append(adapter_name)
    return adapters if adapters else ["Wi-Fi", "Ethernet"]

def get_active_internet_adapter(adapters: list) -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            active_ip = s.getsockname()[0]

        ok, out = run_command(f'powershell -Command "(Get-NetIPAddress -IPAddress \'{active_ip}\').InterfaceAlias"')
        if ok and out:
            name = out.strip().split('\n')[0].strip()
            if name in adapters:
                return name

        for adapter in adapters:
            ok, out_ip = run_command(f'netsh interface ipv4 show addresses "{adapter}"')
            if ok and active_ip in out_ip:
                return adapter
    except Exception:
        pass
    return adapters[0] if adapters else "Wi-Fi"


def get_adapter_info(adapter_name: str) -> dict:
    """دریافت مقادیر فعلی IP، Subnet، Gateway و DNSهای کارت شبکه"""
    info = {
        "is_dhcp": True,
        "ip": "",
        "mask": "255.255.255.0",
        "gateway": "",
        "dns1": "",
        "dns2": ""
    }

    ok_ip, out_ip = run_command(f'netsh interface ipv4 show addresses "{adapter_name}"')
    if ok_ip:
        dhcp_match = re.search(r"DHCP.*?(Yes|No)", out_ip, re.IGNORECASE)
        if dhcp_match: info["is_dhcp"] = dhcp_match.group(1).lower() == "yes"
        ip_match = re.search(r"(?:IP|IPv4).*?:\s*([\d\.]+)", out_ip, re.IGNORECASE)
        if ip_match: info["ip"] = ip_match.group(1)
        mask_match = re.search(r"mask\s+([\d\.]+)\)", out_ip, re.IGNORECASE)
        if mask_match: info["mask"] = mask_match.group(1)
        gw_match = re.search(r"Gateway.*?:\s+([\d\.]+)", out_ip, re.IGNORECASE)
        if gw_match: info["gateway"] = gw_match.group(1)

    ok_dns, out_dns = run_command(f'netsh interface ipv4 show dnsservers "{adapter_name}"')
    if ok_dns:
        dns_matches = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", out_dns)
        if len(dns_matches) >= 1: info["dns1"] = dns_matches[0]
        if len(dns_matches) >= 2: info["dns2"] = dns_matches[1]

    return info


def validate_ipv4(ip_str: str) -> bool:
    """اعتبارسنجی فرمت IPv4"""
    try:
        ipaddress.IPv4Address(ip_str.strip())
        return True
    except ValueError:
        return False

def valid_mask(value: str) -> bool:
    if not validate_ipv4(value): return False
    bits = bin(int(ipaddress.IPv4Address(value.strip())))[2:].zfill(32)
    return "01" not in bits and bits != "0" * 32

def gateway_in_subnet(ip: str, mask: str, gateway: str) -> bool:
    try:
        network = ipaddress.IPv4Interface(f"{ip.strip()}/{mask.strip()}").network
        return ipaddress.IPv4Address(gateway.strip()) in network
    except: return False


def set_static_ip(adapter: str, ip: str, mask: str, gateway: str) -> tuple[bool, str]:
    """اعمال آی‌پی استاتیک، ساب‌نت ماسک و دیفالت گیت‌وی"""
    if not validate_ipv4(ip) or not validate_ipv4(gateway) or not valid_mask(mask):
        return False, "فرمت آدرس آی‌پی، ساب‌نت ماسک یا دیفالت گیت‌وی نامعتبر است."
    if not gateway_in_subnet(ip, mask, gateway):
        return False, "گیت‌وی و آی‌پی باید در یک ساب‌نت باشند."

    cmd = f'netsh interface ip set address name="{adapter}" static {ip} {mask} {gateway} 1'
    return run_command(cmd)


def set_dhcp_ip(adapter: str) -> tuple[bool, str]:
    """بازگردانی دریافت آی‌پی و گیت‌وی به حالت خودکار (DHCP مودم)"""
    cmd = f'netsh interface ip set address name="{adapter}" source=dhcp'
    return run_command(cmd)


def set_static_dns(adapter: str, dns1: str, dns2: str = "") -> tuple[bool, str]:
    """اعمال دی‌ان‌اس اول و دوم"""
    if not validate_ipv4(dns1):
        return False, "آدرس دی‌ان‌اس اول نامعتبر است."

    cmd1 = f'netsh interface ip set dnsservers name="{adapter}" static {dns1} primary'
    ok1, msg1 = run_command(cmd1)
    if not ok1:
        return False, msg1

    if dns2 and validate_ipv4(dns2):
        cmd2 = f'netsh interface ip add dnsservers name="{adapter}" {dns2} index=2'
        run_command(cmd2)

    return True, "DNS با موفقیت اعمال شد."


def set_dhcp_dns(adapter: str) -> tuple[bool, str]:
    """تنظیم دی‌ان‌اس به حالت دریافت خودکار از روتر"""
    cmd = f'netsh interface ip set dnsservers name="{adapter}" source=dhcp'
    return run_command(cmd)


def flush_dns_cache() -> tuple[bool, str]:
    """پاکسازی حافظه موقت کش DNS سیستم‌عامل ویندوز"""
    return run_command('ipconfig /flushdns')