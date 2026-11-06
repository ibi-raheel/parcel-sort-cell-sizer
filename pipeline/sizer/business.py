"""Manual vs robot labour comparison and simple payback."""
import math


def manual_heads(volume: float, window_h: float, rate_h: float) -> int:
    return math.ceil(volume / (window_h * rate_h))


def payback_months(capex_total: float, annual_saving: float) -> float:
    return math.inf if annual_saving <= 0 else 12 * capex_total / annual_saving


def annual_saving(manual_h: int, robot_staff: float, wage: float, shift_h: float, days: int, opex_total: float) -> float:
    return (manual_h - robot_staff) * wage * shift_h * days - opex_total


def labour_case(manual_heads: int, cells: int, ops_per_cell: float, exception_heads: int,
                wage: float, paid_h: float, days: int) -> dict:
    """Annual labour delta of a robot bank vs an all-manual sort, and break-even capex per cell.

    break-even capex per cell for an N-month payback = delta * N / 12 / cells.
    No vendor price is assumed; the output is the most a cell can cost to pay back.
    """
    robot_heads = ops_per_cell * cells + exception_heads
    delta = (manual_heads - robot_heads) * wage * paid_h * days
    return {"ops_per_cell": ops_per_cell, "manual_heads": manual_heads, "robot_side_heads": robot_heads,
            "annual_labour_delta_usd": delta,
            "breakeven_capex_per_cell_usd": {str(mo): delta * mo / 12 / cells for mo in (18, 24, 36)}}
