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

The matching enclosure for this version is included as `DE-5000_IR_RN4871.stp`, `DE-5000_IR_RN4871.stl` and also in the `DE-5000_IR_RN4871.3dm`.
