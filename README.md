# 🐇 CleverJAM-V2

> **Smart SDR Jammer with Frequency Hopping — Enhanced Edition**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://python.org)
[![GNURadio](https://img.shields.io/badge/GNURadio-3.8%20%7C%203.10-green?logo=gnu)](https://www.gnuradio.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Fork of](https://img.shields.io/badge/Fork%20of-jhonnybonny%2FCleverJAM-red)](https://github.com/jhonnybonny/CleverJAM)

---

## ⚠️ Legal Disclaimer

> **Jamming radio frequencies is illegal in most jurisdictions worldwide.**
> This tool is intended **strictly for controlled lab environments**, security research, RF shielding tests, and educational purposes only.
> The author assumes **no responsibility** for any misuse. Always operate within a Faraday cage or RF-shielded enclosure.

---

## What is CleverJAM-V2?

CleverJAM-V2 is an enhanced fork of [jhonnybonny/CleverJAM](https://github.com/jhonnybonny/CleverJAM), a GNURadio-based noise jammer with frequency hopping capability. This version rebuilds the user experience from the ground up — adding a **device selection dialog**, a **live frequency target editor**, and integrating the separate `clever.py` automation script directly into the main GUI, so everything runs from a single window.

---

## ✨ What's New in V2

| Feature | Original | V2 |
|---|---|---|
| Device selection | Auto-picks first device found | ✅ GUI dialog — choose HackRF / LimeSDR / BladeRF / Manual |
| RTL-SDR warning | Silently fails | ✅ Clearly marked as RX-only, warns before use |
| Auto-Jam | Separate `clever.py` script | ✅ Built into main GUI |
| Frequency targets | Edit `jam.json` manually in a text editor | ✅ Live table editor inside GUI — add, edit, delete, save |
| GNURadio 3.10 | Not supported (`pyqwidget` error) | ✅ Fixed — works on both 3.8 and 3.10 |
| Window layout | Fixed size, requires scrolling | ✅ Opens maximized, splitter between FFT and controls |
| FFT Control Panel | Basic display | ✅ Max Hold, Min Hold, Average, Grid, Autoscale |

---

## Prerequisites

- SDR device capable of **transmitting** (HackRF One, USRP, LimeSDR, BladeRF, etc.)
- **GNURadio 3.8 or 3.10** (`maint-3.10` branch supported)
- Python 3.8+
- `gr-osmosdr`
- PyQt5

> ⚠️ **RTL-SDR is receive-only and cannot transmit.** It will be detected and shown with a warning in the device selector.

---

## Installation

```bash
# Clone this repo
git clone https://github.com/Th3Pr00f/CleverJAM-V2.git
cd CleverJAM-V2

# Install GNURadio dependencies (Debian/Ubuntu)
sudo apt install gnuradio gr-osmosdr python3-pyqt5

# Verify HackRF is connected
hackrf_info
```

---

## Usage

### Manual Jamming — GUI Mode

Launch the tool:

```bash
python3 jam-v2.py
```

A **device selection dialog** appears automatically. It scans for connected SDR hardware and lists all available options with their firmware version and serial number.

Select your TX-capable device and click **🚀 Launch Jammer**.

The main window opens with:
- **6 live sliders** — Sample Rate, RF Gain, IF Gain, Center Frequency, BB Gain, Bandwidth
- **Frequency Display** — live FFT spectrum with Max Hold / Min Hold / Average controls
- **Auto-Jam panel** — built-in frequency hopping editor (see below)

You can also open and edit the GNURadio flowgraph directly:

```bash
gnuradio-companion sources/jam.grc
```

---

### Automatic Jamming — Built-in GUI Editor

CleverJAM-V2 integrates frequency hopping directly into the main window. No need to run a separate script.

#### JSON Format

Targets are stored in `jam.json`. The format is:

```json
{
    "Name1": {
        "Bandwidth": "10MHz",
        "Freq": 924e5
    },
    "Name2": {
        "Bandwidth": "20MHz",
        "Freq": 10e5
    }
}
```

Bandwidth can be written as `10MHz`, `500KHz`, or raw Hz (e.g. `10000000`).

#### Using the GUI Editor

Inside the **Auto-Jam** panel at the bottom of the window:

| Action | How |
|---|---|
| Load existing `jam.json` | Click **⬇ Load** |
| Add a new target | Click **➕ Add Row**, then edit cells |
| Edit a target | Double-click any cell |
| Duplicate a row | Select row → **📋 Duplicate** |
| Delete a row | Select row → **🗑 Delete Row** |
| Save changes | Click **💾 Save JSON** |
| Start hopping | Set delay → click **▶ Start Auto-Jam** |
| Stop hopping | Click **■ Stop** |

The jump log prints each hop in real time:

```
|JUMP| --- Jamming Name1 frequency at 92400000.0 with 10 MHz bandwidth
|JUMP| --- Jamming Name2 frequency at 1000000.0 with 20 MHz bandwidth
```

#### Legacy CLI Mode (original clever.py still works)

```bash
# Keep jam.py running, then in a second terminal:
python3 clever.py --file jam.json -d 1
```

> ❗ For `clever.py` to work, `jam.py` must remain open — it communicates via XML-RPC.

The `-d` argument sets the jump delay in seconds. Run `python3 clever.py -h` for all options.

---

## File Structure

```
CleverJAM-V2/
├── jam-v2.py          ← Main GUI (enhanced — this is what you run)
├── clever.py       ← Original CLI auto-jammer (still works)
├── jam.json        ← Frequency target list (editable in GUI or manually)
├── sources/
│   └── jam.grc     ← GNURadio Companion flowgraph
└── README.md
```

---

## Acknowledgements

- Original project: [jhonnybonny/CleverJAM](https://github.com/jhonnybonny/CleverJAM)
- Built on [GNURadio](https://www.gnuradio.org) and [gr-osmosdr](https://osmocom.org/projects/gr-osmosdr)
