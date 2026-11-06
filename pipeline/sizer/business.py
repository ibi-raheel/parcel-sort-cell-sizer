"""Manual vs robot labour comparison and simple payback."""
import math


def manual_heads(volume: float, window_h: float, rate_h: float) -> int:
    return math.ceil(volume / (window_h * rate_h))


def payback_months(capex_total: float, annual_saving: float) -> float:
    return math.inf if annual_saving <= 0 else 12 * capex_total / annual_saving


def annual_saving(manual_h: int, robot_staff: float, wage: float, shift_h: float, days: int, opex_total: float) -> float:
    return (manual_h - robot_staff) * wage * shift_h * days - opex_total
