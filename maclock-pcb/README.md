<img height="120" alt="Macintosh Mini PCB" src="https://github.com/user-attachments/assets/03bcea85-d32f-4c79-91d4-0dbffdf8b3bf" />

# Macintosh Mini breakout PCB

KiCad 10 project for the breakout that connects the Mac-shaped clock's front-panel parts (rotary encoder, two pushbuttons, PAM8302 audio amp, speaker) to the Pi Zero 2 W's GPIO header.

Build guide with pin assignments lives in the [maclock guide](../maclock-build/README.md#1-wiring). For the case-side parts you'll print, see the [3D-printed screen bezel](../maclock-screen-bezel/).

Order from [PCBway](https://www.pcbway.com/project/shareproject/W654223ASS41_Untitled_kicad_pcb_95cca7e3.html). You can [use my referral code](https://pcbway.com/g/AsfKU9) to get $5 off your order, if you want.

## Bill of materials

To populate one board:

| Ref         | Qty | Part                                      | Footprint                          | Notes                                                |
| ----------- | --- | ----------------------------------------- | ---------------------------------- | ---------------------------------------------------- |
| R1, R2      | 2   | 1 kΩ ±1% — UNI-ROYAL `0402WGF1001TCE` (LCSC [`C11702`](https://www.lcsc.com/product-detail/C11702.html)) | 0402 (1005 metric) SMD | In series with the SW1 and SW2 button lines          |
| R3          | 1   | 1 kΩ ±1% — same as above                  | 0402 (1005 metric) SMD             | With C1, the low-pass that smooths the Pi's PWM audio — about 1.6 kHz |
| C1          | 1   | 100 nF X7R — 1206 chip ceramic (e.g. Samsung `CL31B104KBCNNNC`) | `maclock:C_Chip_or_Disc_P5mm_SMD` — SMD chip (0402–1206) **or** a through-hole disc | Audio low-pass with R3 |
| PiInput     | 1   | 1×7 **male** pin header, 2.54 mm, straight | through-hole, 1.0 mm holes         | Silkscreened "Pi GPIO". Pin order: Dial B, GND, Dial A, 5V, A+, SW2, SW1 |
| JP1         | 1   | 1×5 **female** socket, 2.54 mm, straight  | through-hole, 1.0 mm holes          | Silkscreened "Adafruit PAM8302" — the amp's own male pins plug in here |
| ENC1        | 1   | Rotary encoder, EC11-class **horizontal SMD** — F-SWITCH `E8E8-3.2C60-9B34` | `maclock:RotaryEncoder_E8E8-3.2C60-9B34_SMD` — 5 pads + two Ø1.5 mm posts | The "Dial". A real board footprint on the silkscreened "Dial" land; ENC_A / ENC_B / GND also break out on the Pi header |
| BAT+, BAT−  | 2   | **male** pins, 2.54 mm                    | through-hole, 1.0 mm holes          | Silkscreened "Input": 5V and GND. Two single pins, 3 mm apart |
| —           | 1   | **PAM8302 audio amplifier breakout**      | external module                    | Plugs into JP1; output to speaker                    |
| —           | 1   | Small speaker, 8 Ω, ~0.5 W                | —                                  | Whatever fits behind the original Maclock grille     |

The dial (**ENC1**) mounts on the board's "Dial" land — the F-SWITCH `E8E8-3.2C60-9B34` horizontal SMD encoder, or any part matching that land. Its **ENC_A**, **ENC_B**, and **GND** lines also appear on the Pi GPIO header's **Dial A**, **Dial B**, and **GND** pins, so the encoder can be board-mounted here or wired from the header.

### C1 takes either a chip or a disc

C1's land is a hybrid: two SMD pads overlapping the original through-holes. The default is a chip capacitor across the 0.8 mm gap — 0402 through 1206 all land correctly — and the footprint is typed SMD, so it exports as SMT in the position and BOM files. The holes are still there if you would rather fit a through-hole disc; populate one or the other, never both.

### Optional (only if not reusing the Maclock's original parts)

| Ref         | Qty | Part                                      | Footprint           | Notes                                              |
| ----------- | --- | ----------------------------------------- | ------------------- | -------------------------------------------------- |
| SW1, SW2    | 2   | [Same Sky `TS32-7-35-BK-160-RA-SMT-TR`](https://www.digikey.com/en/products/detail/same-sky-formerly-cui-devices/TS32-7-35-BK-160-RA-SMT-TR/26253029), or any 5 × 7.8 × 3.8 mm side-press SMD tactile that fits the land | `maclock:SW_Push_5x7.8x3.8mm_SMD` — side actuated, no-boss | 160 gf, side plunger. The land also fits generic 5 × 7.8 × 3.8 mm SMD samples. Skip if you're wiring the Maclock's existing buttons to the SW1/SW2 pads |

The board carries the **no-boss** land pattern: six SMD pads and no drilled holes under the switch. Order the plain part, not the `B` (boss) variant — a boss switch has two Ø0.8 mm locating pins with nothing to sit in, so it will not seat.

## Sourcing for Chinese assembly

PCBWay assembles from LCSC stock, so the BOM leans on parts LCSC carries.

| Ref            | LCSC                                                        | Notes                                    |
| -------------- | ----------------------------------------------------------- | ---------------------------------------- |
| R1, R2, R3     | [`C11702`](https://www.lcsc.com/product-detail/C11702.html)  | UNI-ROYAL 0402WGF1001TCE, 1 kΩ ±1%       |
| C1             | pick a 1206 100 nF X7R                                        | e.g. Samsung CL31B104KBCNNNC (1206) — confirm the LCSC part; the land also takes 0402–1206 or a through-hole disc |

Two parts still need picking by hand:

- **SW1, SW2.** The Same Sky `TS32-7-35-BK-160-RA-SMT-TR` is the reference and the only confirmed fit for the land, but LCSC/JLCPCB doesn't stock it. The nearest LCSC side-press part is XKB [`C609853`](https://www.lcsc.com/product-detail/C609853.html) (TS-1101S), but its body is 6 mm — about 1.8 mm shorter than this land — so it needs a shorter footprint before it seats. For a guaranteed fit, order the genuine TS32 from DigiKey/Mouser and consign it. Order a sample first — this body size comes in several incompatible pad layouts.
- **The dial (ENC1).** F-SWITCH `E8E8-3.2C60-9B34` is China-domestic and not on LCSC. Any encoder matching the horizontal-SMD land works; ALPS EC11 parts are stocked, for example [`C202365`](https://www.lcsc.com/product-detail/C202365.html), but cost more than a dollar each and use a different (vertical, through-hole) body.

The three headers stay through-hole, so the board needs a hand-soldering or selective-solder pass whichever way C1 goes.

### Worth adding to the next revision

**The dial lines need nothing.** `Dial A` and `Dial B` run from the Pi GPIO header to the encoder with no pull-up and no filtering, leaning on the Pi's internal ~50 kΩ. That sounds wrong — EC11-class encoders are usually specced for a 10–50 kΩ pull-up — but it measures fine. A healthy encoder on this board decodes ten flicks out of ten, and an idle dial logs zero interrupts. The fix that mattered was in software: sample the pins every 1 ms instead of reacting to every edge.

Adding pull-ups was tried and reverted, for two reasons worth recording:

- **A stronger pull-up makes a worn encoder worse, not better.** The low level is a divider against contact resistance. Against a contact gone to 10 kΩ, the internal 50 kΩ still gives 0.55 V and reads low; adding 10 kΩ in parallel gives 1.8 V, which reads high. The weak internal pull-up is the more forgiving choice as contacts age.
- **100 nF is about 100× too much capacitance.** Real transitions inside a flick arrive 19 µs to 680 µs apart, so a 1 ms time constant smears the signal, not just the bounce. If you ever do want a hardware glitch filter, size it around 10 kΩ and 1 nF — roughly 10 µs — and take the numbers from a fresh capture rather than from generic encoder advice.

**The schematic does not match the board.** [`maclock-breakout.kicad_sch`](./maclock-breakout.kicad_sch) is a reconstruction, and it says so. It draws R1, R2, and R3 as pull-ups to 5V and calls JP1 a rotary encoder. The board wires all three as series resistors and JP1 as the PAM8302 header. Trust the PCB; the schematic needs redrawing before anyone edits from it.

## License

CC BY-NC-SA 4.0 — see [`LICENSE`](./LICENSE). Free for non-commercial use; derivatives must also be non-commercial.
