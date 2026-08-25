<img height="120" alt="Macintosh Mini PCB" src="https://github.com/user-attachments/assets/03bcea85-d32f-4c79-91d4-0dbffdf8b3bf" />

# Macintosh Mini breakout PCB

KiCad 10 project for the breakout that connects the Mac-shaped clock's front-panel parts (rotary encoder, two pushbuttons, PAM8302 audio amp, speaker) to the Pi Zero 2 W's GPIO header.

Build guide with pin assignments lives in the [maclock guide](../maclock-build/README.md#1-wiring). For the case-side parts you'll print, see the [3D-printed screen bezel](../maclock-screen-bezel/).

<a href="https://www.buymeacoffee.com/wellsworkshop"><img src="https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=%E2%98%95&slug=wellsworkshop&button_colour=FFDD00&font_colour=000000&font_family=Arial&outline_colour=000000&coffee_colour=ffffff" /></a>

## Bill of materials

To populate one board:

| Ref         | Qty | Part                                      | Footprint                          | Notes                                                |
| ----------- | --- | ----------------------------------------- | ---------------------------------- | ---------------------------------------------------- |
| R1, R2      | 2   | 1 kΩ ±1% — UNI-ROYAL `0402WGF1001TCE` (LCSC [`C11702`](https://www.lcsc.com/product-detail/C11702.html)) | 0402 (1005 metric) SMD | In series with the SW1 and SW2 button lines          |
| R3          | 1   | 1 kΩ ±1% — same as above                  | 0402 (1005 metric) SMD             | With C1, the low-pass that smooths the Pi's PWM audio — about 1.6 kHz |
| C1          | 1   | 100 nF X7R — Samsung `CL05B104KO5NNNC` (LCSC [`C1525`](https://jlcpcb.com/partdetail/C1525)) | 0402 SMD (land also takes 0603 / 0805 / 1206, or a through-hole disc) | Audio low-pass with R3 |
| PiInput     | 1   | 1×7 **male** pin header, 2.54 mm, straight | through-hole, 1.0 mm holes         | Silkscreened "Pi GPIO". Pin order: Dial B, GND, Dial A, 5V, A+, SW2, SW1 |
| JP1         | 1   | 1×5 **female** socket, 2.54 mm, straight  | through-hole, 1.0 mm holes          | Silkscreened "Adafruit PAM8302" — the amp's own male pins plug in here |
| BAT+, BAT−  | 2   | **male** pins, 2.54 mm                    | through-hole, 1.0 mm holes          | Silkscreened "Input": 5V and GND. Two single pins, 3 mm apart |
| —           | 1   | **PAM8302 audio amplifier breakout**      | external module                    | Plugs into JP1; output to speaker                    |
| —           | 1   | Small speaker, 8 Ω, ~0.5 W                | —                                  | Whatever fits behind the original Maclock grille     |

The dial is not a board-mounted part. The [F-SWITCH `E8E8-3.2C60-9B34`](#) encoder — or any EC11-class encoder — wires to the **Dial A**, **Dial B**, and **GND** pins of the Pi GPIO header.

### C1 takes either a chip or a disc

C1's land is a hybrid: two SMD pads overlapping the original through-holes. The default is a chip capacitor across the 0.8 mm gap — 0402 through 1206 all land correctly — and the footprint is typed SMD, so it exports as SMT in the position and BOM files. The holes are still there if you would rather fit a through-hole disc; populate one or the other, never both.

### Optional (only if not reusing the Maclock's original parts)

| Ref         | Qty | Part                                      | Footprint           | Notes                                              |
| ----------- | --- | ----------------------------------------- | ------------------- | -------------------------------------------------- |
| SW1, SW2    | 2   | [Same Sky `TS32-7-35-BK-160-RA-SMT-TR`](https://www.digikey.com/en/products/detail/same-sky-formerly-cui-devices/TS32-7-35-BK-160-RA-SMT-TR/26253029) | 7.0 × 3.5 mm SMT, side actuated | 160 gf, 0.25 mm travel, 2.5 mm body, 1.1 mm plunger. Skip if you're wiring the Maclock's existing buttons to the SW1/SW2 pads |

The board carries the **no-boss** land pattern: six SMD pads and no drilled holes under the switch. Order the plain part, not the `B` (boss) variant — a boss switch has two Ø0.8 mm locating pins with nothing to sit in, so it will not seat.

## Sourcing for Chinese assembly

PCBWay assembles from LCSC stock, so the BOM leans on parts LCSC carries.

| Ref            | LCSC                                                        | Notes                                    |
| -------------- | ----------------------------------------------------------- | ---------------------------------------- |
| R1, R2, R3     | [`C11702`](https://www.lcsc.com/product-detail/C11702.html)  | UNI-ROYAL 0402WGF1001TCE, 1 kΩ ±1%       |
| C1             | [`C1525`](https://jlcpcb.com/partdetail/C1525)               | Samsung CL05B104KO5NNNC, 100 nF X7R 0402 — for an 0603 land use the 0603 equivalent |

Two parts still need picking by hand:

- **SW1, SW2.** The Same Sky part above is the Western reference; LCSC stocks the same 7.0 × 3.5 × 2.5 mm side-press body from domestic brands far cheaper. Filter for side-press SMD, 7 × 3.5 mm, 160 gf, 4 terminals, no boss. Order a sample first — this body size comes in several incompatible pad layouts.
- **The dial.** F-SWITCH is China-domestic and not on LCSC. ALPS EC11 parts are stocked, for example [`C202365`](https://www.lcsc.com/product-detail/C202365.html), but cost more than a dollar each. Since the dial wires to the header rather than mounting to the board, any EC11-class encoder works.

The three headers stay through-hole, so the board needs a hand-soldering or selective-solder pass whichever way C1 goes.

### Worth adding to the next revision

**Pull-ups and filtering on the dial lines.** `Dial A` and `Dial B` run straight from the Pi GPIO header to the encoder with nothing on them — R1, R2, and R3 are series resistors and none of them touch the dial. EC11-class encoders have open-collector outputs and want a 10–50 kΩ pull-up, so today those lines lean on the Pi's weak internal pull-ups and the edges come out ragged. Captured waveforms are in the [maclock guide](../maclock-build/README.md#known-issues).

Four parts fix it, one pair per channel:

| Ref      | Qty | Part                                      | Footprint | Connects                    |
| -------- | --- | ----------------------------------------- | --------- | --------------------------- |
| R4, R5   | 2   | 10 kΩ ±1% — UNI-ROYAL `0402WGF1002TCE` (LCSC [`C25744`](https://lcsc.com/product-detail/Chip-Resistor-Surface-Mount_Uniroyal-Elec-0402WGF1002TCE_C25744.html)) | 0402 SMD | Dial A → 3V3, Dial B → 3V3 |
| C2, C3   | 2   | 100 nF X7R — same part as C1 (LCSC [`C1525`](https://jlcpcb.com/partdetail/C1525)) | 0402 SMD | Dial A → GND, Dial B → GND |

10 kΩ with 100 nF gives a 1 ms time constant, which swallows the sub-millisecond contact chatter while leaving a flick — 60 to 300 ms of real movement — untouched.

**This needs a 3V3 pin the board does not have.** Every supply on the board is 5V, and a 5V pull-up would sit above the 3.3 V maximum on a Pi GPIO and damage it. So the next revision has to bring 3V3 in: the tidiest way is an eighth pin on the Pi GPIO header, wired to Pi header pin 1 or 17. Do not be tempted to pull these lines to the 5V that is already there.

**The schematic does not match the board.** [`maclock-breakout.kicad_sch`](./maclock-breakout.kicad_sch) is a reconstruction, and it says so. It draws R1, R2, and R3 as pull-ups to 5V and calls JP1 a rotary encoder. The board wires all three as series resistors and JP1 as the PAM8302 header. Trust the PCB; the schematic needs redrawing before anyone edits from it.

## License

CC BY-NC-SA 4.0 — see [`LICENSE`](./LICENSE). Free for non-commercial use; derivatives must also be non-commercial.
