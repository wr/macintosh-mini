"""The customizer's sliders, read from maclock-usb-jig.scad, and params.py with
some of them moved, so the tests can try the model at the ends of each."""
import ast
import contextlib
import pathlib
import re
import types

HERE = pathlib.Path(__file__).resolve().parent
SCAD = HERE / "maclock-usb-jig.scad"

NAMES = {
    "hole_width": "HOLE_W",
    "hole_height": "HOLE_H",
    "foot_diameter": "FOOT_D",
    "bit_diameter": "BIT_D",
    "press_fit": "PRESS_FIT",
}
"""Each slider's name in the .scad, and in params.py."""

SLIDER = re.compile(r"^(\w+) = ([\d.]+); // \[([\d.]+):([\d.]+):([\d.]+)\]$", re.M)


def sliders():
    """{name: (default, smallest, largest)} for each slider in the .scad."""
    return {m[1]: (float(m[2]), float(m[3]), float(m[5])) for m in SLIDER.finditer(SCAD.read_text())}


def settings():
    """Named sets of slider values to try, from the sliders' own ranges."""
    s = sliders()
    low = {name: lo for name, (_, lo, _) in s.items()}
    high = {name: hi for name, (_, _, hi) in s.items()}
    return {
        "defaults": {},
        # A wider bit makes a smaller jig, so it goes the other way.
        "smallest jig": dict(low, bit_diameter=high["bit_diameter"]),
        "biggest jig": dict(high, bit_diameter=low["bit_diameter"]),
        "in between": dict(hole_width=4.5, hole_height=9.5, foot_diameter=52.5,
                           bit_diameter=3.2, press_fit=0.12),
    }


def params_with(**changed):
    """params.py, run with the given sliders set before anything is worked out
    from them."""
    changed = {NAMES[name]: value for name, value in changed.items()}
    ns = {}
    for node in ast.parse((HERE / "params.py").read_text()).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) in changed:
            ns[node.targets[0].id] = changed[node.targets[0].id]
        else:
            exec(compile(ast.Module([node], type_ignores=[]), "params.py", "exec"), ns)
    return types.SimpleNamespace(**{k: v for k, v in ns.items() if not k.startswith("__")})


@contextlib.contextmanager
def moved(settings):
    """jig.py builds from params.py with these sliders moved, until the end of
    the with block. Yields those params."""
    import jig
    saved = jig.p
    jig.p = params_with(**settings)
    try:
        yield jig.p
    finally:
        jig.p = saved
