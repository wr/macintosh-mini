<img height="120" alt="Macintosh Mini PCB" src="https://github.com/user-attachments/assets/03bcea85-d32f-4c79-91d4-0dbffdf8b3bf" />

# Macintosh Mini breakout PCB

KiCad 10 project for the breakout that connects the Mac-shaped clock's front-panel parts (rotary encoder, two pushbuttons, speaker, power switch and battery harness) to the Pi Zero 2 W. The PAM8302A audio amplifier is on the board itself. Current revision: 2026.11, which rebuilds the Pi's audio signal on the board and gives the Pi's supply current its own ground return (see [Design notes](#design-notes)); rev 2026.10 boards work but whine faintly with the Pi running.

Build guide with pin assignments lives in the [maclock guide](../maclock-build/README.md#1-wiring). For the case-side parts you'll print, see the [3D-printed screen bezel](../maclock-screen-bezel/).

Order from [PCBway](https://www.pcbway.com/project/shareproject/W654223ASS41_Untitled_kicad_pcb_95cca7e3.html). You can [use my referral code](https://pcbway.com/g/AsfKU9) to get $5 off your order, if you want.

## Bill of materials

To populate one board. Every part is stocked at LCSC, so PCBway can assemble the whole board. Only the Pi header is through-hole. The DigiKey column is for hand assembly: where DigiKey does not carry the LCSC part, a drop-in equivalent is named.

| Ref | Qty | Part | DigiKey (hand assembly) | Notes |
| --- | --- | --- | --- | --- |
| C1 | 1 | 10 nF X7R 0603 — FH `0603B103K500NT` (LCSC [`C57112`](https://www.lcsc.com/product-detail/C57112.html)) | [`1276-1009-1-ND`](https://www.digikey.com/en/products/result?keywords=1276-1009-1-ND) Samsung `CL10B103KB8NNNC` | Audio low-pass with R3 |
| C2, C3 | 2 | 220 nF X7R 0603 — Samsung `CL10B224KA8NNNC` (LCSC [`C21120`](https://www.lcsc.com/product-detail/C21120.html)) | [`1276-1111-1-ND`](https://www.digikey.com/en/products/result?keywords=1276-1111-1-ND) | Amp input coupling (IN+ and IN−) |
| C4, C8, C10 | 3 | 1 µF X5R 0603 — Samsung `CL10A105KB8NNNC` (LCSC [`C15849`](https://www.lcsc.com/product-detail/C15849.html)) | [`1276-1860-1-ND`](https://www.digikey.com/en/products/result?keywords=1276-1860-1-ND) | Amp supply decoupling (C4); U3 input (C8); U3 output and U2 supply (C10) |
| C5 | 1 | 10 µF X5R 0805 — Samsung `CL21A106KAYNNNE` (LCSC [`C15850`](https://www.lcsc.com/product-detail/C15850.html)) | [`1276-2891-1-ND`](https://www.digikey.com/en/products/result?keywords=1276-2891-1-ND), or [`587-4334-1-ND`](https://www.digikey.com/en/products/result?keywords=587-4334-1-ND) Taiyo Yuden `TMK212BBJ106KGHT` when the Samsung is out of stock | Amp bulk decoupling |
| C6 | 0 | 470 pF C0G 0402 — Samsung `CL05C471JB5NNNC` (LCSC [`C307449`](https://www.lcsc.com/product-detail/C307449.html)) | [`CL05C471JB5NNNC`](https://www.digikey.com/en/products/result?keywords=CL05C471JB5NNNC) | **Not fitted**, left off the BOM and placement file. Optional second filter pole across the amp inputs, between R4 and R5 (see [Design notes](#design-notes)) |
| ENC1 | 1 | Rotary encoder, 5 mm hollow shaft, vertical SMD — Alps Alpine `EC05E1220401` (LCSC [`C116648`](https://www.lcsc.com/product-detail/C116648.html)) | [`4809-EC05E1220401CT-ND`](https://www.digikey.com/en/products/result?keywords=4809-EC05E1220401CT-ND) | The dial. 1.72 mm hex hole, 12 pulse / 12 detent. Sits over a board cutout so the dial's shaft can go deep enough to grip (see [Design notes](#design-notes)). C (middle pin) is common |
| J1 | 1 | Molex PicoBlade 1×2, 1.25 mm, SMD top entry — `53398-0271` (LCSC [`C122410`](https://www.lcsc.com/product-detail/C122410.html)) | [`53398-0271`](https://www.digikey.com/en/products/result?keywords=53398-0271) | **Power switch**, in series with the battery supply; silkscreened "Switch". Takes the Maclock's 2-wire switch plug |
| J2 | 1 | Molex PicoBlade 1×4, 1.25 mm, SMD top entry — `53398-0471` (LCSC [`C17617036`](https://www.lcsc.com/product-detail/C17617036.html)) | [`53398-0471`](https://www.digikey.com/en/products/result?keywords=53398-0471) | **Power input**, silkscreened "Power". Takes the Maclock's 4-wire plug: pin 4 (silk `+`) = battery supply, about 4 V (the clock's charging board passes the cell through, it does not boost it), pin 3 (silk `-`) = GND, pins 1–2 unused |
| J3 | 1 | Molex PicoBlade 1×2, 1.25 mm, SMD top entry — `53398-0271` (LCSC [`C122410`](https://www.lcsc.com/product-detail/C122410.html)) | [`53398-0271`](https://www.digikey.com/en/products/result?keywords=53398-0271) | **Speaker**, silkscreened "Speaker". Same part as J1; polarity does not matter |
| J4 | 1 | 1×7 male pin header, 2.54 mm — XFCN `PZ254V-11-07P` (LCSC [`C492406`](https://www.lcsc.com/product-detail/C492406.html)) | [`35-PRPC007SAAN-RC-ND`](https://www.digikey.com/en/products/result?keywords=35-PRPC007SAAN-RC-ND) Sullins `PRPC007SAAN-RC` | Through-hole, silkscreened "Pi GPIO". Pin order: Dial B, GND, Dial A, 5V, A+, SW2, SW1 |
| R1, R2 | 2 | 1 kΩ ±1% 0402 — UNI-ROYAL `0402WGF1001TCE` (LCSC [`C11702`](https://www.lcsc.com/product-detail/C11702.html)) | [`311-1.00KLRCT-ND`](https://www.digikey.com/en/products/result?keywords=311-1.00KLRCT-ND) Yageo `RC0402FR-071KL` | In series with the SW1 and SW2 button lines |
| R3 | 1 | 1 kΩ ±1% 0402 — same as above | same as above | With C1, the 16 kHz low-pass on the rebuilt PWM audio |
| R4, R5 | 2 | 47 kΩ ±1% 0402 — UNI-ROYAL `0402WGF4702TCE` (LCSC [`C25792`](https://www.lcsc.com/product-detail/C25792.html)) | [`311-47.0KLRCT-ND`](https://www.digikey.com/en/products/result?keywords=311-47.0KLRCT-ND) Yageo `RC0402FR-0747KL` | Amp input resistors, set the gain to about 8 dB |
| R6 | 1 | 100 kΩ ±1% 0402 — UNI-ROYAL `0402WGF1003TCE` (LCSC [`C25741`](https://www.lcsc.com/product-detail/C25741.html)) | [`311-100KLRCT-ND`](https://www.digikey.com/en/products/result?keywords=311-100KLRCT-ND) Yageo `RC0402FR-07100KL` | Pull-up on the amp's shutdown pin (amp always on) |
| SW1, SW2 | 2 | BZCN `TSB001A3518A` side-press SMD tactile, 7.7 × 3.55 mm, 180 gf (LCSC [`C2888448`](https://www.lcsc.com/product-detail/C2888448.html)) | — (nothing at DigiKey fits this land) | The two front buttons |
| U1 | 1 | PAM8302A 2.5 W class-D mono amp, MSOP-8 — Diodes `PAM8302AASCR` (LCSC [`C113367`](https://www.lcsc.com/product-detail/C113367.html)) | [`PAM8302AASCRDICT-ND`](https://www.digikey.com/en/products/result?keywords=PAM8302AASCRDICT-ND) | Bottom side |
| U2 | 1 | Single Schmitt-trigger buffer, SOT-23-5 — TI `SN74LVC1G17DBVR` (LCSC [`C7836`](https://www.lcsc.com/product-detail/C7836.html)) | [`SN74LVC1G17DBVR`](https://www.digikey.com/en/products/result?keywords=SN74LVC1G17DBVR) | Rebuilds the Pi's PWM audio from U3's 3.0 V |
| U3 | 1 | 3.0 V low-noise LDO, SOT-23-5 — TI `TPS7A2030PDBVR` (LCSC [`C963429`](https://www.lcsc.com/product-detail/C963429.html)) | [`TPS7A2030PDBVR`](https://www.digikey.com/en/products/result?keywords=TPS7A2030PDBVR) | Quiet 3.0 V for U2 and the shutdown pull-up |
| — | 1 | Small speaker, 8 Ω, 1 W, 28–40 mm, PicoBlade 1.25 mm 2-pin plug (often sold as "JST 1.25"), e.g. [Adafruit 3923](https://www.adafruit.com/product/3923) | — | Whatever fits behind the Maclock grille |

The schematic carries the same data in each symbol's `Manufacturer`, `MPN` and `LCSC` fields, so any BOM exported from it, or from the PCBway plugin, matches this table.

## Design notes

**Audio input.** The Pi's audio is PWM on GPIO 19, switching between the Pi's own 3.3 V and ground, so it carries whatever noise the Pi's supply and ground do. U2 rebuilds it from U3, a separate low-noise 3.0 V regulator (net `+3V0`), so only the timing of the Pi's signal reaches the amp. U3 runs from the clock's battery, which is about 4 V at full charge and falls as it drains, so it is a 3.0 V part rather than 3.3 V: that keeps it far enough above its dropout to keep filtering as the battery runs down. It works just as well from a real 5 V. R3/C1 then low-pass it at 16 kHz.

**Amplifier.** The filtered signal goes C2 → R4 → PAM8302A IN+, with IN− terminated through the matching R5/C3 pair. R4 adds to the chip's internal 10 kΩ input resistor, which brings its fixed 23.5 dB gain down to about 8 dB; fine volume is a software setting, and `setup.sh` leaves 4 dB of headroom so the startup chime's peaks don't clip. The shutdown pin is pulled up through R6 so the amp is always on (no header GPIO is free for a mute).

C6 is a spare pad, not fitted. R3/C1 is a single pole, which takes only about 24 dB off the Pi's PWM noise near the amp's own 200–300 kHz switching frequency, where a class-D amp can fold it back into the audio band as hiss or a faint whistle. A 470 pF across IN+ and IN− adds a second pole at about 20 kHz (with R4/R5 and the chip's internal 10 kΩ), for roughly 46 dB there, at the cost of about 1 dB at 10 kHz. Rev 2026.10 had the same single pole and none of its measured noise came from this, so solder C6 on only if a board hisses or whistles with the amp warm.

**Grounds.** The Pi, its display and its backlight draw up to about 1 A, and the return current comes back on its own trace (net `GND_PI`) from J4 pin 2 to J2, where the net tie NT1 joins it to the board ground. On rev 2026.10 that current flowed through the amp's ground and the amp shared the Pi's supply copper, which put a faint whine in the speaker: a 1 kHz comb from the backlight PWM, plus drifting tones from the emulator's load. NT1 is copper only, so it is not in the BOM. The amp now takes its supply straight from J1, so it no longer shares the Pi's supply trace, and its 1 µF decoupling capacitor sits right against its supply and ground pins.

**Dial and buttons.** ENC1's A and B go straight to GPIO 11 and GPIO 10, and the buttons through R1/R2 to GPIO 27 and GPIO 26; the Pi's internal pull-ups do the rest (see [`brightness_control.py`](../maclock-build/brightness_control.py)). ENC1's footprint origin is the shaft centre, at the same spot as before, so the dial still lines up with the case.

**ENC1 and the dial.** The Maclock's dial came on an F-Switch `E8E8-3.2C60-9B34`, which is no longer sold, and the clones on LCSC have 1.78 mm bores that leave the dial loose. The dial's hex shaft tapers, from 1.60 mm across the flats at the tip to 1.75 mm about 3 mm up. The bores are straight, so an encoder grips the shaft only near its own top edge. The 3.7 mm tall E8E8 reaches the thick part of the shaft; the 2.7 mm Alps does not, unless the shaft goes further in. The board therefore has Alps' recommended cutout under ENC1, which the part needs anyway because its drum stands slightly below its base. With the shaft about 1 mm into the cutout, the thick part of the shaft fills the Alps' 1.70–1.75 mm lower bore, about as tight as the E8E8 was. That puts the wheel about 1 mm closer to the board than on the E8E8. J3, J1 and J2 moved 1.6, 1.0 and 0.4 mm east to clear the cutout; their solder tabs are 0.48 mm apart, and a rule in `maclock-breakout.kicad_dru` lets their stock courtyards overlap.

**Libraries.** Two project libraries ship with the board, next to the KiCad 10 standard libraries:

- `maclock` — ENC1's symbol, footprint and 3D model (`maclock.3dshapes/`). The footprint follows the land in Alps' EC encoder catalog (EC05E drawing No.3), checked against LCSC's own land for C116648. The cutout is cut wider than Alps' 3.0 mm hole so a 1 mm router can make it, and it runs further on the far side to clear the drum and a second pair of pegs. The 3D model is LCSC's, imported with `easyeda2kicad` and turned so its bore sits on the footprint origin.
- `lcsc` — LCSC's own symbol, footprint and 3D model for SW1/SW2 (C2888448), imported with `easyeda2kicad --full --lcsc_id=C2888448`. easyeda2kicad's conversion artefacts were fixed, nothing else: the plastic-peg holes are NPTH, the bracket pads have no outline stroke (so the copper is LCSC's 1.5 mm), the pins are passive, and the courtyard is one closed outline.

## Fabrication files

Gerbers, drill files, the placement file and the BOM are generated with `kicad-cli` into `production/`, which git ignores:

```sh
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
mkdir -p production/gerbers
$K pcb export gerbers -l "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts" -o production/gerbers/ maclock-breakout.kicad_pcb
$K pcb export drill --format excellon --excellon-separate-th -o production/gerbers/ maclock-breakout.kicad_pcb
(cd production && zip -qj maclock-breakout-gerbers.zip gerbers/* && rm -r gerbers)
$K pcb export pos --format csv --units mm --side both -o production/maclock-breakout-positions.csv maclock-breakout.kicad_pcb
$K sch export bom --fields 'Reference,${QUANTITY},Value,Footprint,Manufacturer,MPN,LCSC' \
  --group-by 'Value,Footprint,MPN' -o production/maclock-breakout-bom.csv maclock-breakout.kicad_sch
```

## License

CC BY-NC-SA 4.0 — see [`LICENSE`](./LICENSE). Free for non-commercial use; derivatives must also be non-commercial.
