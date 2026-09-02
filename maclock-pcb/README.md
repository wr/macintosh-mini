<img height="120" alt="Macintosh Mini PCB" src="https://github.com/user-attachments/assets/03bcea85-d32f-4c79-91d4-0dbffdf8b3bf" />

# Macintosh Mini breakout PCB

KiCad 10 project for the breakout that connects the Mac-shaped clock's front-panel parts (rotary encoder, two pushbuttons, speaker) to the Pi Zero 2 W's GPIO header. Rev 2 puts the PAM8302A audio amplifier on the board itself, so the Adafruit module is no longer needed.

Build guide with pin assignments lives in the [maclock guide](../maclock-build/README.md#1-wiring). For the case-side parts you'll print, see the [3D-printed screen bezel](../maclock-screen-bezel/).

Order from [PCBway](https://www.pcbway.com/project/shareproject/W654223ASS41_Untitled_kicad_pcb_95cca7e3.html). You can [use my referral code](https://pcbway.com/g/AsfKU9) to get $5 off your order, if you want.

## Bill of materials

To populate one board:

| Ref         | Qty | Part                                      | Footprint                          | Notes                                                |
| ----------- | --- | ----------------------------------------- | ---------------------------------- | ---------------------------------------------------- |
| R1, R2      | 2   | 1 kΩ ±1% — UNI-ROYAL `0402WGF1001TCE` (LCSC [`C11702`](https://www.lcsc.com/product-detail/C11702.html)) | 0402 (1005 metric) SMD | In series with the SW1 and SW2 button lines          |
| R3          | 1   | 1 kΩ ±1% — same as above                  | 0402 (1005 metric) SMD             | With C1, the low-pass that smooths the Pi's PWM audio — about 16 kHz |
| C1          | 1   | 10 nF X7R — 1206 chip ceramic — `1206B103K500NT` (LCSC [`C1846`](https://www.lcsc.com/product-detail/C1846.html)) | `maclock:C_Chip_or_Disc_P5mm_SMD` — SMD chip (0603–1206) **or** a through-hole disc | Audio low-pass with R3 |
| PiInput     | 1   | 1×8 **male** pin header, 2.54 mm, straight — LCSC [`C492407`](https://www.lcsc.com/product-detail/C492407.html) | through-hole, 1.0 mm holes         | Silkscreened "Pi GPIO". Pin order: Dial B, GND, Dial A, 5V, A+, SW2, SW1, MUTE. MUTE is optional (see below) |
| U1          | 1   | PAM8302A 2.5 W class-D mono amp — Diodes `PAM8302AASCR` (LCSC [`C113367`](https://www.lcsc.com/product-detail/C113367.html)) | MSOP-8 | The amplifier, bottom side. Same chip as the Adafruit module |
| C2, C3      | 2   | 220 nF X7R 0603 — `CL10B224KA8NNNC` (LCSC [`C21120`](https://www.lcsc.com/product-detail/C21120.html)) | 0603 | Amp input coupling caps (IN+ and IN−) |
| C4          | 1   | 1 µF X5R 0603 — `CL10A105KB8NNNC` (LCSC [`C15849`](https://www.lcsc.com/product-detail/C15849.html)) | 0603 | Amp supply decoupling |
| C5          | 1   | 10 µF X5R 0805 — `CL21A106KAYNNNE` (LCSC [`C15850`](https://www.lcsc.com/product-detail/C15850.html)) | 0805 | Amp bulk decoupling |
| R4, R5      | 2   | 47 kΩ ±1% 0402 — `0402WGF4702TCE` (LCSC [`C25792`](https://www.lcsc.com/product-detail/C25792.html)) | 0402 | Amp input resistors: set the gain to about 9 dB |
| R6          | 1   | 100 kΩ ±1% 0402 — `0402WGF1003TCE` (LCSC [`C25741`](https://www.lcsc.com/product-detail/C25741.html)) | 0402 | Pull-up on the amp's shutdown pin: amp is on unless MUTE is pulled low |
| J3          | 1   | JST ZH 1×2, 1.5 mm — `B2B-ZR` (LCSC [`C158011`](https://www.lcsc.com/product-detail/C158011.html)) | through-hole, vertical | **Speaker** connector, silkscreened `+` / `-` |
| ENC1        | 1   | Rotary encoder, **horizontal SMD mouse-wheel** — HOAUC `HYCW03-2.8D-5P-S` (LCSC [`C55218995`](https://www.lcsc.com/product-detail/C55218995.html)) | `maclock:RotaryEncoder_HYCW03-2.8D-5P-S_SMD` — 3 quadrature pads (2 mm pitch) + 2 solder tabs + two NPTH Ø0.7/Ø0.9 locating holes | The "Dial". Hex 1.78 mm bore, 3.2 mm mount height, 12 pulse / 12 detent. Drops onto the silkscreened "Dial" land; ENC_A / ENC_B / GND also break out on the Pi header. LCSC-stocked equivalent of the F-SWITCH `E8E8-3.2C60-9B34` (hex 1.74 mm, 9 P/18 D — not on LCSC; order from F-Switch/Dicomon and consign if you want the exact feel) |
| J1          | 1   | JST ZH 1×2, 1.5 mm — `B2B-ZR` (LCSC [`C158011`](https://www.lcsc.com/product-detail/C158011.html)) | through-hole, vertical | **Power switch** connector, inline in the 5V rail (5V_IN ↔ 5V). Wire an SPST switch here: closed = board on |
| J2          | 1   | JST ZH 1×4, 1.5 mm — `B4B-ZR` (LCSC [`C157997`](https://www.lcsc.com/product-detail/C157997.html)) | through-hole, vertical | **Power input** from USB-C or battery: pin 4 (silk `+`) = 5V (3.7 V on battery), pin 3 (silk `-`) = GND. Pins 1–2 unused (legacy Maclock, not needed). Pin 1 is the end nearest J1 |
| —           | 1   | Small speaker, 8 Ω, ~0.5 W                | —                                  | Plugs into J3. Whatever fits behind the original Maclock grille |

The dial (**ENC1**) mounts on the board's "Dial" land — the F-SWITCH `E8E8-3.2C60-9B34` horizontal SMD encoder, or any part matching that land. Its **ENC_A**, **ENC_B**, and **GND** lines also appear on the Pi GPIO header's **Dial A**, **Dial B**, and **GND** pins, so the encoder can be board-mounted here or wired from the header.

### C1 takes either a chip or a disc

C1's land is a hybrid: two SMD pads overlapping the original through-holes. The default is a chip capacitor across the 0.8 mm gap — 0603 through 1206 land correctly (an 0402 only overlaps each pad by 0.1 mm) — and the footprint is typed SMD, so it exports as SMT in the position and BOM files. The holes are still there if you would rather fit a through-hole disc; populate one or the other, never both.

### Optional (only if not reusing the Maclock's original parts)

| Ref         | Qty | Part                                      | Footprint           | Notes                                              |
| ----------- | --- | ----------------------------------------- | ------------------- | -------------------------------------------------- |
| SW1, SW2    | 2   | BZCN `TSB001A3518A` (LCSC [`C2888448`](https://www.lcsc.com/product-detail/C2888448.html)) — 7.7 × 3.55 mm side-press SMD tactile, 180 gf | `maclock:SW_TSB001_7.7x3.55_SideSMD` — side actuated + bracket, two Ø0.9 mm NPTH locators | The two front buttons. **LCSC-stocked.** Same land fits any TSB001 variant (120 / 180 / 260 gf, 3.2 / 3.5 / 3.8 mm heights). Skip if wiring the Maclock's existing buttons to the SW pads |

The SW1/SW2 land is the TSB001 pattern: four SMD pads (pad 1 = the signal contact, pads 2–4 to GND) plus two Ø0.9 mm NPTH locators. Earlier revisions used a Same Sky `TS32-7-35-BK-160-RA-SMT-TR` (160 gf) on a custom 6-pad land; the board now carries the LCSC-stocked TSB001.

## Sourcing for Chinese assembly

PCBWay assembles from LCSC stock, so the BOM leans on parts LCSC carries.

| Ref            | LCSC                                                        | Notes                                    |
| -------------- | ----------------------------------------------------------- | ---------------------------------------- |
| R1, R2, R3     | [`C11702`](https://www.lcsc.com/product-detail/C11702.html)  | UNI-ROYAL 0402WGF1001TCE, 1 kΩ ±1%       |
| C1             | [`C1846`](https://www.lcsc.com/product-detail/C1846.html)     | 1206B103K500NT, 10 nF X7R 1206 (Basic); the land also takes 0603–1206 or a through-hole disc |

The two parts that used to need hand-picking are now LCSC-stocked:

- **SW1, SW2.** BZCN `TSB001A3518A` (LCSC [`C2888448`](https://www.lcsc.com/product-detail/C2888448.html)) — a 180 gf, 7.7 × 3.55 mm side-press SMD tactile that matches the board's TSB001 land. Want the exact original feel? The Same Sky `TS32-7-35-BK-160-RA-SMT-TR` is 160 gf but isn't on LCSC — order it from DigiKey/Mouser and consign against a rebuilt TS32 land.
- **The dial (ENC1).** HOAUC `HYCW03-2.8D-5P-S` (LCSC [`C55218995`](https://www.lcsc.com/product-detail/C55218995.html)) sits on the Dial land. The original F-SWITCH `E8E8-3.2C60-9B34` (9 pulse / 18 detent, hex 1.74 mm) is China-domestic — consign it if you want that exact feel.

The Pi header and the three JST connectors stay through-hole, so the board needs a hand-soldering or selective-solder pass whichever way C1 goes.

### The on-board amp (rev 2)

The Adafruit PAM8302 module used to plug into a 5-pin socket. Rev 2 puts the same chip on the board:

- **Signal path.** Pi PWM audio → R3/C1 low-pass (16 kHz) → C2 (220 nF) → R4 (47 kΩ) → PAM8302A IN+. IN− is tied to ground through the matching R5/C3 pair. R4 adds to the chip's internal 10 kΩ input resistor, which brings the fixed 24 dB gain down to about 9 dB, roughly where the module's trim pot was set. Fine volume is a software setting.
- **Power.** VDD runs from the 5V rail with 1 µF + 10 µF decoupling, so it works down to the 3.7 V battery.
- **MUTE.** The chip's shutdown pin is pulled up to 5V through R6 (100 kΩ), so the amp is on by default and Pi pin 8 can stay unconnected. Wire it to a spare GPIO and drive it low to silence the amp when idle, which is the real fix for hiss.
- **Speaker.** J3 is a JST ZH 2-pin: pin 1 (`+`) and pin 2 (`-`). Speaker polarity does not matter for a single speaker.
- **Layout.** Everything sits on the bottom side where the socket was, so the top-side dial and buttons are unchanged.

### Worth adding to the next revision

**The dial lines need nothing.** `Dial A` and `Dial B` run from the Pi GPIO header to the encoder with no pull-up and no filtering, leaning on the Pi's internal ~50 kΩ. That sounds wrong — EC11-class encoders are usually specced for a 10–50 kΩ pull-up — but it measures fine. A healthy encoder on this board decodes ten flicks out of ten, and an idle dial logs zero interrupts. The fix that mattered was in software: sample the pins every 1 ms instead of reacting to every edge.

Adding pull-ups was tried and reverted, for two reasons worth recording:

- **A stronger pull-up makes a worn encoder worse, not better.** The low level is a divider against contact resistance. Against a contact gone to 10 kΩ, the internal 50 kΩ still gives 0.55 V and reads low; adding 10 kΩ in parallel gives 1.8 V, which reads high. The weak internal pull-up is the more forgiving choice as contacts age.
- **100 nF is about 100× too much capacitance.** Real transitions inside a flick arrive 19 µs to 680 µs apart, so a 1 ms time constant smears the signal, not just the bounce. If you ever do want a hardware glitch filter, size it around 10 kΩ and 1 nF — roughly 10 µs — and take the numbers from a fresh capture rather than from generic encoder advice.

**The schematic now matches the board.** [`maclock-breakout.kicad_sch`](./maclock-breakout.kicad_sch) was rebuilt from the PCB (the source of truth) — all 11 parts with correct footprints, LCSC numbers, and pin-for-pin nets, drawn in net-label style (connectivity by labels, not wires). ERC is clean and it passes board↔schematic parity apart from benign symbol-metadata differences. R1/R2/R3 are series resistors (button lines feed `SW1`/`SW2` → `BTN1`/`BTN2`; R3 filters `AUDIO` → `A+`), and U1 is the on-board PAM8302A amplifier.

## License

CC BY-NC-SA 4.0 — see [`LICENSE`](./LICENSE). Free for non-commercial use; derivatives must also be non-commercial.
