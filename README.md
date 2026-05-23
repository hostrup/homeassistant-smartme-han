# Smart-me Kamstrup HAN

[![GitHub Release](https://img.shields.io/github/release/hostrup/homeassistant-smartme-han.svg)](https://github.com/hostrup/homeassistant-smartme-han/releases)
[![License](https://img.shields.io/github/license/hostrup/homeassistant-smartme-han.svg)](LICENSE)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

*An unofficial, yet robust and optimized Home Assistant integration for the Smart-me Kamstrup HAN module.*

This integration allows you to monitor and log data from your Kamstrup electricity meter via a Smart-me HAN module. It supports both **Local Modbus TCP** for lightning-fast and private updates, as well as the **Smart-me Cloud API** as a cloud-based alternative.

---

## 🌟 Features

* **Dual Connection:** Choose between seamless local Modbus TCP (recommended) or Smart-me's Cloud API.
* **Intelligent Configuration:** Fully integrated Home Assistant UI-based setup (`config_flow`) with Danish and English language support.
* **Auto-Recovery & Fallback:** If your local Modbus connection fails during setup, the integration offers experimental remote activation of the Modbus port directly via your Smart-me API.
* **Stability First:** The integration strictly adheres to the Kamstrup meter's technical requirements of a minimum 2.5-second delay for local Modbus calls and executes in a background thread via Home Assistant's `DataUpdateCoordinator`, ensuring your system never freezes.
* **Reconfiguration:** Easily change your IP address, API choice, and credentials via the integration's "Configure" button.

---

## 🛠 Prerequisites & Hardware

To use this integration, you need:
1. A **Kamstrup electricity meter** with an available HAN port.
2. A **Smart-me Kamstrup HAN module**.
3. **Static IP Address:** If you wish to use Local Modbus TCP, the module's MAC address **must** be assigned a static IP address in your router via DHCP reservation (the module does not support mDNS/Zeroconf locally).

---

## 📦 Installation

### Method 1: Via HACS (Recommended)
The absolute easiest way to install is through [HACS](https://hacs.xyz/) (Home Assistant Community Store).

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hostrup&repository=homeassistant-smartme-han&category=integration)

1. Click the badge above to add this custom repository to your HACS.
2. If the badge doesn't work, open HACS, click the three dots in the top right corner, select **Custom repositories**, and add `https://github.com/hostrup/homeassistant-smartme-han` as an **Integration**.
3. Search for "Smart-me Kamstrup HAN" in HACS and click **Download**.
4. **Restart Home Assistant**.

### Method 2: Manual Installation
1. Download the code from the latest release.
2. Copy the `custom_components/smartme_han/` folder to your Home Assistant's `custom_components` folder.
3. Restart Home Assistant.

---

## ⚙️ Setup and Configuration

After restarting, the integration can be added directly from the Home Assistant integrations page.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=smartme_han)

*(Note: The setup link above only works AFTER the integration has been installed and Home Assistant has been restarted).*

When setting up the integration, you are guided through a user-friendly flow:

1. **Select connection type:** Choose between "Cloud API" or "Local Modbus TCP".
2. **Cloud API:**
   * Select login method (API key or Basic Auth).
   * Enter your details. You can generate an API key on the [Smart-me Portal](https://portalweb.smart-me.com/api/key).
3. **Local Modbus TCP (Recommended):**
   * Enter the locked IP address of your module.
   * *Test failing?* The Modbus port (502) on the module might be disabled by default. The integration will catch the error and let you enter your API key to attempt sending an asynchronous activation command to the module via the cloud, after which it tests the local access again.

---

## 📊 Supported Sensors

The integration fetches the following data and creates them as proper `sensor` entities in Home Assistant with corresponding State and Device Classes. This ensures full compatibility with the built-in Energy Dashboard:

| Data point | Unit | Type / Note |
| :--- | :--- | :--- |
| **Current Power (Total)** | W | Bidirectional: Positive = Import, Negative = Export |
| **Energy Import (Total)** | kWh | Accumulated total consumption |
| **Energy Export (Total)** | kWh | Accumulated total production (Solar panels, etc.) |
| **Voltage L1, L2, L3** | V | Voltage per phase |
| **Current L1, L2, L3** | A | Current per phase |

*Technical note: Kamstrup meters do not output phase-related active power (Watt P1/P2/P3) via the HAN port, which is why these are intentionally ignored to ensure a faster and more stable polling loop.*

---

## ⚠️ Known Limitations and Important Information

* **One Connection at a Time (Modbus TCP):** The HAN module exclusively allows *one* active TCP connection at a time on port 502. Concurrent connection attempts will result in timeouts.
* **Polling Delay (Modbus TCP):** There is a strict requirement of a minimum 2.5-second delay between requests to avoid dropping data packets. Fetching all registers therefore takes up to 25 seconds. The integration handles this automatically in the background so the system doesn't freeze.

---

## 🤝 Contributions and Bugs
This project is Open Source and created to share domain knowledge and tools with the Home Assistant community. If you experience a bug or have ideas for improvements, please create an [Issue](https://github.com/hostrup/homeassistant-smartme-han/issues) or a Pull Request. Your help is highly appreciated!
