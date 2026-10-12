# 🌐 NetSwitcher 
 
A fast, lightweight, and native-feeling Windows desktop utility to seamlessly switch your IP addresses, Default Gateways, and DNS servers. Built with Python and [Flet](https://flet.dev/).

If you frequently move between different networks (e.g., Home, Office, Gaming) or need to bypass geo-restrictions using custom DNS servers, NetSwitcher allows you to save those configurations as profiles and apply them with a single click.

## ✨ Features

- **1-Click Network Profiles:** Save your custom IP, Subnet, Gateway, and DNS configurations into profiles and load them instantly.
- **DHCP & Static IP Toggle:** Easily switch between obtaining an IP address automatically (DHCP) or setting a static IP.
- **Rich DNS Presets:** Quickly apply popular public or regional DNS servers (e.g., Cloudflare, Google, Electro, Shecan, 403.online).
- **Auto-Elevation (UAC):** The app automatically requests the necessary Administrator privileges on startup to execute network-level changes via Windows `netsh`.
- **DNS Cache Flushing:** A built-in utility to instantly clear the Windows DNS cache (`ipconfig /flushdns`).
- **Modern UI:** A clean, responsive, vertical user interface inspired by native Windows utilities.

## 🛠️ Project Structure

The project is modularized for better maintainability:
- `main.py`: The entry point and Flet UI implementation.
- `network_manager.py`: Core logic for reading/writing Windows network adapters using `netsh` and PowerShell.
- `admin_helper.py`: Utility to ensure the application runs with Administrator privileges.
- `presets.py`: A dictionary of predefined DNS servers and profiles.

## 🚀 Getting Started

### Prerequisites
- **OS:** Windows 10 or Windows 11 (requires `netsh` and `PowerShell`)
- **Python:** Version 3.10 or higher

### Installation & Running

**Option 1: Using `uv` (Recommended for speed)**
```bash
# Clone the repository
git clone https://github.com/mhmdhsynyzdnfr/NetSwitcher.git
cd NetSwitcher

# Run directly (uv will handle dependencies automatically)
uv run main.py