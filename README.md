# DER EE DE-5000 IR-UART TTL-Adapter
3D printable IR-UART TTL-Adapter to connect a DER EE DE-5000 LCR Meter to a PC. Created with Rhino 8.

I stumbled across a thread on the eevblog forum about a piece of software to connect the DER EE DE-5000 using a self-made infrared-to-UART TTL bridge.
There was a 3D-printable enclosure. Since I own a DER EE DE-5000 LCR Meter, I redesigned the enclosure a bit to fit the contour of the device.

The enclosure consists of two parts that clamp together. When inserting the adapter, press a bit harder until it snaps.
Inside is a CP2102 UART adapter, an L-53P3C IR phototransistor (long leg connected to GND, short leg connected to RX) and a 4.7k Ohm resistor.
The resistor can have any value between 1k and 10k. I chose the 4.7k one because I have plenty of them.
I used some Kapton tape under the resistor.

The software can be found on the internet. It should also work with TestController (a well-known Java app).
I use 19200 baud 8N1, and on Windows I disabled power saving for this device in the Device Manager.

For printing the enclosure I used PETG and a 0.25 mm nozzle on my Prusa MK4S at 0.12 mm layer height.

<p align="center">
<img src="IMG_20251108_114108.jpg" width="250"> 
<img src="IMG_20251108_104756.jpg" width="250"> 
</p>

<p align="center">
<img src="IMG_20251108_111826.jpg" width="250"> 
<img src="IMG_20251108_101802.jpg" width="250"> 
</p>

<p align="center">
<img src="Bildschirmfoto vom 2025-11-08 10-04-10.jpg" width="250"> 
<img src="Bildschirmfoto vom 2025-11-08 10-16-28.jpg" width="250"> 
</p>

<p align="center">
<img src="NHufV83VG2.png" width="250"> 
</p>

---

## **RN4871 Version (Bluetooth Low Energy)**

After the wired CP2102 version I built a wireless variant based on a Microchip **RN4871** BLE module. Instead of a USB cable, the meter data is now sent over Bluetooth Low Energy, so the meter stays completely galvanically isolated and cable-free from the PC.

<table align="center" border="0" cellspacing="8" cellpadding="0">
  <tr>
    <td><img src="1.jpg" width="250"></td>
    <td><img src="2.jpg" width="250"></td>
    <td><img src="3.jpg" width="250"></td>
  </tr>
  <tr>
    <td><img src="4.jpg" width="250"></td>
    <td><img src="5.jpg" width="250"></td>
    <td><img src="6.jpg" width="250"></td>
  </tr>
  <tr>
    <td><img src="7.jpg" width="250"></td>
    <td><img src="8.png" width="250"></td>
    <td><img src="9.png" width="250"></td>
  </tr>
  <tr>
    <td><img src="10.png" width="250"></td>
    <td><img src="11.jpg" width="250"></td>
    <td><img src="12.jpg" width="250"></td>
  </tr>
</table>

### How it works

The optical front-end uses the same idea as the USB version, but tuned for the RN4871's UART input. The L-53P3C IR phototransistor sits between the RN4871 **RX** pin and **GND**, and a single **680 Ohm** pull-up resistor connects that same RX node to **3.3 V**. When the meter's IR LED sends a data pulse, the phototransistor conducts and pulls the RX line low; between pulses the pull-up brings it back high. That RX node is wired **directly** to the RN4871 RX pin — on the RX side no Schmitt trigger, no inverter and no capacitor are needed.

> ⚠️ **Decoupling capacitors are mandatory (VDD ↔ GND).** The RN4871 needs two bypass capacitors between **VDD (pin 12)** and **GND (pin 11)**: a **100 nF** ceramic (X7R/X5R) right at the pin for high-frequency filtering, plus a larger **4.7 µF – 10 µF** low-ESR capacitor in parallel as an energy reservoir. Keep both as short as possible (< 5 mm) and star the ground to the module's GND pin.

Do not skip these — this cost us a lot of debugging. On start-up and especially during BLE pairing the radio draws very short microsecond current spikes far above the average (well over 50 mA), which a bench supply's slow averaging never even shows. Without a local reservoir those spikes collapse the voltage at the VDD pin, the module browns out and drops into a reboot/crash loop: it never finishes booting, can't be programmed or paired reliably, and Windows pairing fails every time in a way that looks exactly like a firmware bug. Adding the two capacitors was what finally made the whole chain stable.

Getting there took a few detours. An inverting Schmitt trigger turned out to be a polarity dead-end (it mostly reacted to ambient light instead of the meter). The RN4871 also has a surprisingly high UART input threshold (roughly 70 % of VCC), so the pull-up value matters: 470 Ohm keeps the phototransistor too close to saturation, 1k is already too slow, and **680 Ohm is the sweet spot** for clean edges at 9600 baud 8N1.

The DE-5000 sends its IR data at **9600 baud 8N1**, but the RN4871's UART defaults to 115200 baud out of the box. So the module has to be reconfigured once to 9600 baud (command mode: `SB,09`, then reboot) so that its transparent UART matches the meter — otherwise the incoming serial stream is garbled.

The RN4871 runs in transparent UART mode and forwards the raw serial stream over BLE. On the PC side the data flows like this:

**RN4871 (BLE) → BLE-to-COM bridge (Windows) → com0com virtual COM pair → DER EE PC software**

Since I'm not a software developer, I let Claude code a BLE-to-COM-port bridge for the Windows side. It connects to the RN4871, receives the BLE notifications and feeds them into a com0com virtual serial port pair, so the original DER EE PC software just sees a normal COM port and displays the measured value (for example 219.0 Ω) exactly as it would over the cable.

The matching enclosure for this version is included as `DE-5000_IR_RN4871_housing.stp`, `DE-5000_IR_RN4871_housing.stl`, `DE-5000_IR_RN4871_housing-cover.stp`, `DE-5000_IR_RN4871_housing-cover.stl` and also in the `DE-5000_IR_RN4871.3dm`.

---

## **Programming Adapter (Pogo-Pin Fixture)**

Getting the firmware onto the module and setting its baud rate turned out to be one of the trickiest parts of the whole build. I made several attempts to program the **RN4871** (and the even smaller **RN4871U**), but because the module is so tiny and its pads sit so close together, the usual approach of soldering it to a piece of standard perfboard simply did not work — the pad pitch is finer than a 2.54 mm hole grid and the pads are almost impossible to reach reliably by hand.

<table align="center" border="0" cellspacing="8" cellpadding="0">
  <tr>
    <td><img src="13.jpg" width="250"></td>
    <td><img src="14.jpg" width="250"></td>
    <td><img src="15.jpg" width="250"></td>
  </tr>
  <tr>
    <td><img src="16.jpg" width="250"></td>
    <td><img src="17.png" width="250"></td>
    <td><img src="18.png" width="250"></td>
  </tr>
  <tr>
    <td><img src="19.jpg" width="250"></td>
    <td><img src="20.jpg" width="250"></td>
    <td><img src="21.png" width="250"></td>
  </tr>
  <tr>
    <td><img src="22.png" width="250"></td>
    <td><img src="23.jpg" width="250"></td>
    <td><img src="24.jpg" width="250"></td>
  </tr>
</table>

### How it works

So I designed a dedicated programming adapter that holds the module and contacts its pads with **pogo-pins**. The pins are mounted at a slight angle: at the **top** they land exactly on the module's pads, while at the **bottom** they line up with a standard **2 mm PCB grid**. The pogo-pins are soldered to that PCB on the underside, which also mechanically holds the whole adapter together and keeps everything rigid while the module is dropped in. On the RN4871 version the module is kept in position by a small **plastic clamp**.

Two of the module's control lines have to be toggled while flashing: **RESET_N** (active low) and **P2_0** (pin 4 — low = bootloader / programming mode, high or open = normal application). Both got a switch/button on the adapter, so the module can be put into programming mode and reset without any re-wiring.

> ⚠️ The same two decoupling capacitors from the finished build are essential here as well: a **100 nF** and a **10 µF** (0402) between VDD and GND — see image 19. Without them the module browns out during flashing and programming simply fails.

There are two versions of the fixture, one for the **RN4871** and one for the **RN4871U**. The RN4871U version is a bit more advanced: instead of the plastic clamp it has a **lid that is held closed by two mini neodymium magnets**. The files are `RN4871_fixture.stp`, `RN4871_fixture.stl` and `RN4871U_fixture.stp`, `RN4871U_fixture.stl` (plus the lid, `RN4871U_fixture_lid.stl` / `RN4871U_fixture_Lid.stp`), and the editable Rhino sources `RN4871_fixture.3dm` / `RN4871U_fixture.3dm`.

---

## **Software — BLE-to-COM Bridge & Tools**

The RN4871 exposes Microchip's **Transparent UART** service over Bluetooth Low Energy, but Windows does not turn that into a serial port by itself — so the meter's original PC software cannot see it. All the software needed to close that gap lives in [`software/`](software/): a bridge that pipes the BLE data into a virtual COM port, plus the collection of small Python tools I used to flash, configure and debug the module along the way.

Everything is Python 3.8+ and depends only on `bleak` (BLE) and `pyserial`:

```
pip install bleak pyserial
```

> **Note:** all MAC addresses and network hosts in these scripts are placeholders (`AA:BB:CC:DD:EE:FF`, `192.0.2.10`). Pass your own module MAC with `--mac`, and the lab-supply host (only used by the debug tools) via the `BB3_HOST` environment variable. The Microchip RN4870/71 firmware is proprietary and is **not** included — the flashing scripts expect you to supply your own hex file.

### How I got here (the parts that cost time)

This did not work on the first try. The path, roughly in order:

1. **Optical polarity.** The first attempt fed the IR signal through an inverting Schmitt trigger. That was a dead end — it mostly reacted to ambient light and inverted the polarity the wrong way. Dropping it and wiring the phototransistor with a plain 680 Ω pull-up straight into RX (see the hardware section above) was what actually worked.
2. **The pairing crash-loop.** Modules would connect for 2–4 seconds and then reboot roughly every 4 s. It looked exactly like a firmware bug, and I mis-configured several modules chasing it. The real cause (confirmed via the Microchip forum) was **missing VDD decoupling capacitors**: the BLE radio's microsecond current spikes browned out the supply. Adding the 100 nF + 4.7–10 µF caps fixed pairing instantly. This is why those caps are called out as mandatory above.
3. **Peer address type matters.** The RN4870/71 has a known quirk where "public address" central devices (Windows, most Android) pair far less reliably than "random/RPA" ones (iPhone). Windows still works once the caps are in place, but expect a few connect/disconnect retries.
4. **Baud rate.** The module's UART defaults to 115200, while the DE-5000 sends at 9600 — so the RN4871 has to be reconfigured once (`SB,09`, then reboot). See `set_baud_9600_ble.py` / `set_baud_9600.py`.
5. **Pairing alone is not enough.** Even after a successful pair, Windows drops the idle BLE link — an application has to actively **subscribe to the TX characteristic notifications** to keep data flowing. That is exactly what the bridge does.
6. **No automatic COM port.** Windows never creates a serial port for a BLE Transparent-UART device. The fix is a **com0com** virtual COM pair plus the Python bridge that copies every BLE notification into it, so the meter software just sees a normal COM port.

### The BLE side — Transparent UART subscription

The data path on the module is Microchip's Transparent UART (also called the ISSC/Transparent service). It uses three fixed UUIDs, which is the part that is easy to miss when writing your own client:

| Role | UUID | Properties |
|---|---|---|
| **Service** (Transparent UART) | `49535343-FE7D-4AE5-8FA9-9FAFD205E455` | — |
| **TX characteristic** (module → PC) | `49535343-1E4D-4BD9-BA61-23C647249616` | **Notify** (+ Write) |
| **RX characteristic** (PC → module) | `49535343-8841-43F4-A8D4-ECBE34729BB3` | Write / Write-without-response |

To receive the meter data you connect, then call `start_notify()` on the **TX characteristic** — each measurement packet then arrives as a GATT notification. The RX characteristic is only needed if you want to send data *to* the module; for this one-way meter link it stays unused. The Transparent UART service must be enabled on the module (`SS,C0`); if `bleak`'s service discovery does not list the service UUID above, enable it first (see `configure_tx_uart.py`).

### Windows setup, step by step

1. **Module powered and advertising** — 3.3 V on VDD/GND, the two decoupling caps in place, reconfigured to 9600 baud. A Reset press should make it advertise; a generic BLE scanner (e.g. *Bluetooth LE Explorer*) confirms it is visible.
2. **Install com0com** (use the signed build — newer Windows rejects the unsigned driver) from <https://com0com.sourceforge.net/>. Let the installer create the default `CNCA0 ↔ CNCB0` pair.
3. **Name the pair** to two COM numbers, e.g. `COM10 ↔ COM11`, either in the com0com setup GUI or from an Admin prompt:
   ```cmd
   cd "C:\Program Files (x86)\com0com"
   setupc.exe change CNCA0 PortName=COM10
   setupc.exe change CNCB0 PortName=COM11
   ```
   `COM10` is the bridge's end, `COM11` is the end the meter software reads.
4. **Install the Python packages:** `pip install bleak pyserial`.
5. **Find your module's MAC** with a BLE scanner, then **start the bridge**:
   ```cmd
   python software\scripts\ble_to_com_bridge.py --mac AA:BB:CC:DD:EE:FF --com COM10 --baud 9600
   ```
   It scans, connects, subscribes to the TX notifications and forwards them to `COM10`, reconnecting automatically if the link drops. **Leave this window open** while measuring.
6. **Point the meter software at `COM11`** — 9600 8N1, flow control off. The measured values now appear as if the meter were wired over USB.

Common snags: the bridge `--baud` and the meter-software baud must match; make sure the software uses the *other* com0com port (COM11, not COM10); if the module crash-loops, re-check the decoupling caps and the 3.3 V supply.

### The tools in `software/`

The production path only needs `ble_to_com_bridge.py`; the rest are the flashing, configuration and diagnostic helpers built up during the project. A short quick-reference also lives in [`software/scripts/README.md`](software/scripts/README.md).

**Bridge / receiving**
| Script | What it does |
|---|---|
| `scripts/ble_to_com_bridge.py` | **Main tool.** Connects to the module, subscribes to the TX characteristic and forwards every BLE notification into a com0com COM port; auto-reconnect, optional COM→BLE direction. |
| `scripts/windows_receiver.py` | Console-only receiver — prints the BLE stream without com0com, for a quick "are bytes arriving?" check. |
| `scripts/ble_hex_monitor.py` | Dumps the incoming BLE notifications as raw hex, for protocol inspection. |

**Configuration**
| Script | What it does |
|---|---|
| `scripts/set_baud_9600_ble.py` | Sets the module's UART to 9600 baud remotely over BLE (`SB,09` + reboot). |
| `scripts/set_baud_9600.py` | Same, but over the wired CP2102 UART, and verifies by reconnecting at 9600. |
| `scripts/configure_tx_uart.py` | Enables the Transparent UART service / sets the service bitmap (`SS,C0`). |
| `scripts/cmd_after_reboot.py` | Enters command mode inside the ~15 ms window right after `%REBOOT%` (for stubborn modules). |
| `scripts/silent_cmd.py` | Reaches command mode (`$$$`) on a module that is advertising silently. |

**Firmware flashing**
| Script | What it does |
|---|---|
| `scripts/bootloader_test.py` | HCI ping to confirm the module is in the bootloader (P2_0 low + reset). |
| `scripts/update_slow.py` | Flashes firmware over the HCI bootloader, with inter-chunk delays that keep the CP2102 in sync. |
| `scripts/hfiles_combine.py` | Combines the four `H00–H03` firmware files into a single hex (set `RN4871_HEXDIR`). |

**Diagnostics / testing**
| Script | What it does |
|---|---|
| `scripts/raw_monitor.py` | Raw UART monitor — every byte with a timestamp (hex + ASCII). |
| `scripts/uart_loopback.py` | CP2102 loopback test (bridge TX↔RX) to prove the adapter itself is fine. |
| `scripts/uart_trace.py` | Live UART trace plus parallel bench-supply current logging (host via `BB3_HOST`), for connect/brownout diagnosis. |
| `scripts/bb3_watch.py` | Logs voltage/current from a lab supply over SCPI/TCP (development aid; host via `BB3_HOST`). |
| `scripts/de5000_simulator.py` | Emulates the DE-5000's IR data stream, so the whole chain can be tested without the meter. |
| `rn4871_ble_test.py` | BLE scan + connect + GATT service/characteristic discovery. |

The three `.bat` files in `software/` (`start-bridge.bat`, `set-baud-9600.bat`, `monitor-hex.bat`) are just convenience wrappers that call the scripts above on Windows — open them in a text editor and set your own module MAC / COM port at the top.
