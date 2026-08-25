<img height="120" alt="Macintosh Mini PCB" src="https://github.com/user-attachments/assets/03bcea85-d32f-4c79-91d4-0dbffdf8b3bf" />

# Macintosh Mini breakout PCB

KiCad 10 project for the breakout that connects the Mac-shaped clock's front-panel parts (rotary encoder, two pushbuttons, PAM8302 audio amp, speaker) to the Pi Zero 2 W's GPIO header.

Build guide with pin assignments lives in the [maclock guide](../maclock-build/README.md#1-wiring). For the case-side parts you'll print, see the [3D-printed screen bezel](../maclock-screen-bezel/).

<a href="https://www.buymeacoffee.com/wellsworkshop"><img src="https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=%E2%98%95&slug=wellsworkshop&button_colour=FFDD00&font_colour=000000&font_family=Arial&outline_colour=000000&coffee_colour=ffffff" /></a>

## Bill of materials

To populate one board:

| Ref         | Qty | Part                                      | Footprint                          | Notes                                                |
| ----------- | --- | ----------------------------------------- | ---------------------------------- | ---------------------------------------------------- |
| R1, R2, R3  | 3   | 1 kΩ ±1% — UNI-ROYAL `0402WGF1001TCE` (LCSC [`C11702`](https://www.lcsc.com/product-detail/C11702.html)) | 0402 (1005 metric) SMD | Pull-ups for the two buttons + the rotary encoder    |
| C1          | 1   | 100 nF ceramic capacitor                  | Through-hole disc, 5 mm pitch       | Audio decoupling. The only through-hole passive — see sourcing notes |
| —           | 1   | **PAM8302 audio amplifier breakout**      | external module                    | Wire `A+` to Pi GPIO 19 (header pin 35); output to speaker |
| —           | 1   | Small speaker, 8 Ω, ~0.5 W                | —                                  | Whatever fits behind the original Maclock grille     |
| PiInput     | 1   | 1×7 pin header, 2.54 mm pitch, vertical   | through-hole                        | Plugs into Pi GPIO pins 35–47                        |

### Optional (only if not reusing the Maclock's original parts)

| Ref         | Qty | Part                                      | Footprint           | Notes                                              |
| ----------- | --- | ----------------------------------------- | ------------------- | -------------------------------------------------- |
| SW1, SW2    | 2   | [Same Sky `TS32-7-35-BK-160-RA-SMT-TR`](https://www.digikey.com/en/products/detail/same-sky-formerly-cui-devices/TS32-7-35-BK-160-RA-SMT-TR/26253029) | 7.0 × 3.5 mm SMT, side actuated | 160 gf, 0.25 mm travel, 2.5 mm body depth, 1.1 mm plunger. Skip if you're wiring the Maclock's existing buttons to the SW1/SW2 pads |
| JP1         | 1   | F-SWITCH `E8E8-3.2C60-9B34` rotary encoder | 1×5 through-hole, 2.54 mm pitch | EC11-class quadrature encoder with push-switch. Skip if you're wiring the Maclock's existing dial |

The switches are the "no boss" variant: flat underside, no locating pins. A "with boss" switch has two Ø0.8 mm locating pins and will not sit down on these pads.

JP1 is a plain 1×5 row of 2.54 mm holes, not an encoder's own footprint — a bare EC11's pins are staggered and will not drop in. Use flying leads, or an encoder module that breaks out to 0.1 in pins.

## Sourcing for Chinese assembly

PCBWay assembles from LCSC stock, so the BOM leans on parts LCSC carries. Verified LCSC equivalents:

| Ref        | LCSC                                                             | Notes                                    |
| ---------- | ---------------------------------------------------------------- | ---------------------------------------- |
| R1, R2, R3 | [`C11702`](https://www.lcsc.com/product-detail/C11702.html)       | UNI-ROYAL 0402WGF1001TCE, 1 kΩ ±1%       |
| C1         | [`C1525`](https://jlcpcb.com/partdetail/C1525)                    | Samsung CL05B104KO5NNNC, 100 nF X7R — **0402, not the through-hole disc this board has** |

Two parts still need picking by hand:

- **SW1, SW2.** The Same Sky part above is the Western reference; LCSC stocks the same 7.0 × 3.5 × 2.5 mm side-press body from domestic brands far cheaper. Filter LCSC's tactile switches for side-press SMD, 7 × 3.5 mm, 160 gf, 4 terminals, and check the drawing shows no boss. Order a sample before committing — this body size comes in several incompatible pad layouts.
- **JP1.** F-SWITCH is China-domestic and not on LCSC. ALPS EC11 parts are stocked, for example [`C202365`](https://www.lcsc.com/product-detail/C202365.html), but they cost more than a dollar each and their pins are staggered, so they need the flying-lead treatment above.

### Worth changing for Chinese assembly

C1 is the only through-hole passive, and a single THT part pulls the whole board into a hand-soldering step. Moving it to an 0402 or 0603 pad pair (`C1525` above) would make the board fully SMD apart from the Pi header, which has to stay through-hole.

### Worth adding to the next revision

`ENC_A` and `ENC_B` run straight from JP1 to the Pi header with no pull-up and no filtering, while the buttons and the encoder's push-switch each get a 1 kΩ pull-up (R1, R2, R3). EC11-class encoders have open-collector outputs and want a 10–50 kΩ pull-up, so today those two lines lean on the Pi's weak internal pull-ups and the edges come out ragged. **10 kΩ to 3V3 and 100 nF to ground on each channel** would fix that. Details and the captured waveforms are in the [maclock guide](../maclock-build/README.md#known-issues).

## License

CC BY-NC-SA 4.0 — see [`LICENSE`](./LICENSE). Free for non-commercial use; derivatives must also be non-commercial.
