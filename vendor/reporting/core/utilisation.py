"""The one utilisation rule for a whole report.

Every utilisation shown anywhere in a report — tables, cards, banners, calc
blocks — uses `util_label`. Every OK/FAIL from a utilisation comes from
`util_status` or `util_passed`. An overall pass is
`all(util_passed(u) for u in utils)`. Never use f"{u:.0%}", round() or a
hand-typed status: they round to the nearest value, so one check could read 76 %
in a summary card and 77 % in the check table, or a banner say 100 % while the
table says FAIL.

The rule — engineering-significant, each part tested:

- `util` is a utilisation RATIO (1.0 == 100 %). It must be a real number, not
  bool / numpy.bool_ / Decimal / str / None, and finite and >= 0. It is never
  clamped or abs()'d: a negative ratio raises, because it usually means a signed
  (uplift) demand was used without taking the governing direction.
- A Pint quantity is accepted if it is dimensionless, and converted with
  `m_as("dimensionless")`. Never pass `q.magnitude` yourself: the magnitude keeps
  the unit's scale (84 percent -> 84; kN·m / kN·mm -> 1/1000 of the true ratio).
- pct = round(util * 100, 6); the rounding absorbs float noise
  (0.84 * 100 == 84.00000000000001). passed = pct <= 100.
- Labels round UP: "percent" gives ceil(pct) % and "ratio" gives ceil(pct) / 100
  to two places. So a value shown above 100 % (or 1.00) is always FAIL and one
  shown at or below it is always OK: 1.004 -> "101%" / "1.01" FAIL;
  0.995 -> "100%" / "1.00" OK.
- beams' local `_ok(u)` uses a strict u <= 1.0. The two differ only for
  1.0 < util < about 1.000000005 (5 parts per billion): OK here, FAIL there.
"""

import math
import numbers


def _ratio(util, name: str = "") -> float:
    """Validate a utilisation ratio and return it as a float."""
    what = f"Utilisation {name!r}" if name else "Utilisation"
    if hasattr(util, "m_as") and hasattr(util, "dimensionality"):
        util = util.m_as("dimensionless")   # Pint: raises DimensionalityError (a TypeError) if not a ratio
    if isinstance(util, bool) or not isinstance(util, numbers.Real):
        raise TypeError(f"{what} must be a real number (a ratio, 1.0 == 100 %), got {type(util).__name__} {util!r}")
    value = float(util)
    if not math.isfinite(value):
        raise ValueError(f"{what} must be finite, got {value}")
    if value < 0:
        raise ValueError(
            f"{what} is negative ({value}). This usually means a signed (uplift) demand was used "
            "without taking the governing direction; fix the sign, do not abs() it."
        )
    return value


def util_pct(util) -> float:
    """The utilisation as a percentage, with float noise rounded away."""
    return round(_ratio(util) * 100, 6)


def util_passed(util) -> bool:
    """True when the utilisation is at most 100 %."""
    return util_pct(util) <= 100


def util_status(util) -> str:
    """"OK" or "FAIL"."""
    return "OK" if util_passed(util) else "FAIL"


def util_label(util, style: str = "percent") -> str:
    """The utilisation for display, rounded up: "77%" (percent) or "0.77" (ratio)."""
    shown = math.ceil(util_pct(util))
    if style == "percent":
        return f"{shown}%"
    if style == "ratio":
        return f"{shown / 100:.2f}"
    raise ValueError(f"util_label style must be 'percent' or 'ratio', got {style!r}")
