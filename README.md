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
* **Auto-Recovery & Fallback:** If your local Modbus connection fails during setup, the integration offers experimental remote activation of the Modbus port directly via your Smart-me API. And if it drops later, it automatically falls back to the Smart-me Cloud API and heals itself back to the local link once the meter answers again — see [Automatic Cloud Fallback](#-automatic-cloud-fallback-auto-heal).
* **Stability First:** The integration honours the Kamstrup meter's timing requirements — a minimum delay between Modbus requests, and a longer one before reopening a connection — and reads the nine values in three batched requests rather than nine. A full poll takes about 5.5 seconds.
* **Fully Asynchronous:** All I/O runs on Home Assistant's event loop — no worker threads are held for the duration of a poll, so startup and the rest of your system stay responsive.
* **Good Neighbour:** The meter's single TCP slot is released between polls, so other tools can still reach it.
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

## 🔁 Automatic Cloud Fallback (Auto-Heal)

If your meter is configured for **Local Modbus TCP**, Home Assistant can keep monitoring it even when the module's Modbus TCP port stops answering. This happens occasionally: the port hangs while the Smart-me cloud API keeps working normally.

How it works:

1. The integration counts **consecutive** Modbus connection failures. After **3 in a row** it automatically switches to the **Smart-me Cloud API**, so your sensors stay available without gaps.
2. While the local link is down it keeps polling the cloud and quietly tests the Modbus port again every 5 minutes (configurable).
3. As soon as the meter answers locally, the integration switches back to the local connection. The switch is invisible to your dashboards and history, because the entity IDs and unique IDs never change.

The fallback is skipped automatically when no cloud credentials are configured, and authentication errors are never masked by it — only genuine connection failures trigger the switch.

### Configuring the fallback

1. Open **Settings → Devices & Services → Smart-me Kamstrup HAN** and click **Configure** on a meter that uses **Local Modbus TCP**.
2. Choose one:
   * **Cloud fallback: API key** — paste a Smart-me API key (generate one on the [Smart-me Portal](https://portalweb.smart-me.com/api/key)).
   * **Cloud fallback: username and password** — use your Smart-me account.
   * **Recovery probe interval** — how often, in seconds (default `300`), Home Assistant tests whether the local link has recovered.
   * **Disable cloud fallback** — stop using the cloud as a fallback.
3. Save. The integration reloads automatically, so the change applies to the next poll.

> The fallback is available **only for Local Modbus TCP entries**. A pure Cloud API entry already uses the cloud and has nothing to fall back from.

| Setting | Default | Meaning |
| :--- | :--- | :--- |
| Failure threshold | 3 | Consecutive Modbus failures before switching to the cloud (fixed) |
| Probe interval | 300 s | How often the local Modbus port is retested while on the cloud fallback |

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

* **One Connection at a Time (Modbus TCP):** The HAN module exclusively allows *one* active TCP connection at a time on port 502. The integration opens a connection per poll and closes it again, so the meter stays reachable for your other tools for ~54 of every 60 seconds. If a second client (a test instance, a script) polls the same meter, both will see dropped requests.
* **Polling Delay (Modbus TCP):** The meter requires a minimum 2.5-second delay *between requests* — not between registers. The integration groups the nine values into three contiguous register blocks, so a complete poll costs two delays: **about 5.5 seconds**, measured against real hardware.
* **Reconnect Delay (Modbus TCP):** After a connection closes, the meter needs roughly 12 seconds before it will serve the first request on a new one. This never matters in steady state, but it means the very first poll after setup takes ~17 seconds. Requests are retried, so a dropped one costs a delay rather than a failed update.
* **Cloud API Rate Limits:** When polling the cloud API continuously, stay at or above a 30-second interval to avoid being throttled.

---

## 🤝 Contributions and Bugs
This project is Open Source and created to share domain knowledge and tools with the Home Assistant community. If you experience a bug or have ideas for improvements, please create an [Issue](https://github.com/hostrup/homeassistant-smartme-han/issues) or a Pull Request. Your help is highly appreciated!
