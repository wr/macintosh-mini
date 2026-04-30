# Macintosh Mini breakout PCB

<img height="200" alt="Macintosh Mini PCB" src="https://github.com/user-attachments/assets/737a05eb-cc00-4b0e-b82b-f892061ca27d" />


KiCad 9 project for the breakout that connects the Mac-shaped clock's front-panel parts (rotary encoder, two pushbuttons, PAM8302 audio amp, speaker) to the Pi Zero 2 W's GPIO header.

Build guide with pin assignments lives in the [maclock guide](../maclock-build/README.md#1-wiring). For the case-side parts you'll print, see the [3D-printed screen bezel](../maclock-screen-bezel/).

## Bill of materials

To populate one board:

| Ref         | Qty | Part                                      | Footprint                          | Notes                                                |
| ----------- | --- | ----------------------------------------- | ---------------------------------- | ---------------------------------------------------- |
| R1, R2, R3  | 3   | 1 kΩ resistor                             | 0402 (1005 metric) SMD             | Pull-ups for the two buttons + the rotary encoder    |
| C1          | 1   | 100 nF ceramic capacitor                  | Through-hole disc, 5 mm pitch       | Audio decoupling                                     |
| —           | 1   | **PAM8302 audio amplifier breakout**      | external module                    | Wire `A+` to Pi GPIO 19 (header pin 35); output to speaker |
| —           | 1   | Small speaker, 8 Ω, ~0.5 W                | —                                  | Whatever fits behind the original Maclock grille     |
| PiInput     | 1   | 1×7 pin header, 2.54 mm pitch, vertical   | through-hole                        | Plugs into Pi GPIO pins 35–47                        |

### Optional (only if not reusing the Maclock's original parts)

| Ref         | Qty | Part                                      | Footprint           | Notes                                              |
| ----------- | --- | ----------------------------------------- | ------------------- | -------------------------------------------------- |
| SW1, SW2    | 2   | SMD tactile switch (e.g. Mountain TS32735) | 4.6 × 3.5 mm SMT    | Skip if you're wiring the Maclock's existing buttons to the SW1/SW2 pads |
| JP1         | 1   | 5-pin rotary encoder                      | 1×5 round, 2.54 mm   | Skip if you're wiring the Maclock's existing dial   |

## License

CC BY-NC-SA 4.0 — see [`LICENSE`](./LICENSE). Free for non-commercial use; derivatives must also be non-commercial.
