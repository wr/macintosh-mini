"""Write the print plate as STEP (to edit in any CAD tool) and STL (to slice),
and the key on its own as STL, to reprint the part most likely to get lost."""
import pathlib
import sys

from build123d import export_step, export_stl

import jig

HERE = pathlib.Path(__file__).resolve().parent
NAME = "maclock-usb-jig"


def main() -> int:
    plate = jig.plate()
    export_step(plate, str(HERE / f"{NAME}.step"))
    export_stl(plate, str(HERE / f"{NAME}.stl"), tolerance=0.001, angular_tolerance=0.1)
    parts = jig.plate_parts()
    export_stl(parts["key"], str(HERE / f"{NAME}-key.stl"), tolerance=0.001, angular_tolerance=0.1)
    for name, part in parts.items():
        bb = part.bounding_box()
        print(f"{name}: {bb.size.X:.3f} x {bb.size.Y:.3f} x {bb.size.Z:.3f} mm, {part.volume:.1f} mm3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
