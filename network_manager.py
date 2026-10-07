"""
ماژول هسته شبکه برای اجرای دستورات netsh و ارتباط با کارت‌های شبکه ویندوز
"""

import subprocess
import re
import ctypes
import ipaddress


def is_admin() -> bool:
    """بررسی اینکه آیا اسکریپت با مجوز ادمین اجرا شده است یا خیر"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_command(cmd: str) -> tuple[bool, str]:
    """اجرای ایمن دستورات خط فرمان با کدگذاری مناسب ویندوز"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            encoding='cp1256',  # پشتیبانی از کاراکترهای ویندوز فارسی/انگلیسی
            errors='ignore'
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or result.stdout.strip()
    except Exception as e:
        return False, str(e)


def get_network_adapters() -> list[str]:
    """استخراج لیست کارت‌های شبکه متصل و فعال"""
    ok, output = run_command('netsh interface show interface')
    adapters = []
    if ok:
        for line in output.splitlines():
            # خطوط جدول netsh را بررسی می‌کنیم
            if "Enabled" in line or "Connected" in line:
                parts = re.split(r'\s{2,}', line.strip())
                if len(parts) >= 4:
                    adapter_name = parts[3].strip()
                    adapters.append(adapter_name)
    # اگر کارتی یافت نشد یا در محیط تست بود، موارد پیش‌فرض اضافه شوند
    return adapters if adapters else ["Wi-Fi", "Ethernet"]


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

    # ۱. استخراج آی‌پی و گیت‌وی
    ok_ip, out_ip = run_command(f'netsh interface ipv4 show addresses "{adapter_name}"')
    if ok_ip:
        if "DHCP:                             Yes" in out_ip or "DHCP: Yes" in out_ip:
            info["is_dhcp"] = True
        elif "DHCP:                             No" in out_ip or "DHCP: No" in out_ip:
            info["is_dhcp"] = False

        ip_match = re.search(r'IP Address:\s+([\d\.]+)', out_ip)
        if ip_match:
            info["ip"] = ip_match.group(1)

        mask_match = re.search(r'Subnet Prefix:\s+[\d\.]+/(\d+)', out_ip)
        gw_match = re.search(r'Default Gateway:\s+([\d\.]+)', out_ip)
        if gw_match:
            info["gateway"] = gw_match.group(1)

    # ۲. استخراج DNSها
    ok_dns, out_dns = run_command(f'netsh interface ipv4 show dnsservers "{adapter_name}"')
    if ok_dns:
        dns_matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', out_dns)
        if len(dns_matches) >= 1:
            info["dns1"] = dns_matches[0]
        if len(dns_matches) >= 2:
            info["dns2"] = dns_matches[1]

    return info


def validate_ipv4(ip_str: str) -> bool:
    """اعتبارسنجی فرمت IPv4"""
    try:
        ipaddress.IPv4Address(ip_str)
        return True
    except ValueError:
        return False


def set_static_ip(adapter: str, ip: str, mask: str, gateway: str) -> tuple[bool, str]:
    """اعمال آی‌پی استاتیک، ساب‌نت ماسک و دیفالت گیت‌وی"""
    if not validate_ipv4(ip) or not validate_ipv4(gateway):
        return False, "فرمت آدرس آی‌پی یا دیفالت گیت‌وی نامعتبر است."

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

    # تنظیم دی‌ان‌اس اصلی
    cmd1 = f'netsh interface ip set dnsservers name="{adapter}" static {dns1} primary'
    ok1, msg1 = run_command(cmd1)
    if not ok1:
        return False, msg1

    # در صورت وجود دی‌ان‌اس دوم
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
