import math
from sizer.queueing import erlang_c, wq_mean, cells_hand, cells_erlang, p_wait_exceeds


def test_erlang_c_textbook_value():
    # A = 2 Erlangs on 3 servers: P(wait) = 4/9 (standard table value)
    assert math.isclose(erlang_c(2.0, 1.0, 3), 4 / 9, rel_tol=1e-12)


def test_single_server_reduces_to_mm1():
    lam, mu = 3.0, 5.0
    assert math.isclose(erlang_c(lam, mu, 1), lam / mu)
    assert math.isclose(wq_mean(lam, mu, 1), lam / (mu * (mu - lam)))


def test_unstable_is_flagged():
    assert erlang_c(10, 1, 10) == 1.0 and p_wait_exceeds(10, 1, 9, 1) == 1.0


def test_hand_calc():
    # 12,000 parcels, 4 h, 500/h/cell, 2.5% exceptions: 11,700 / 2,000 = 5.85 -> 6
    assert cells_hand(12_000, 4.0, 500, 0.025) == 6
    assert cells_hand(10_000, 4.0, 500, 0.0) == 5  # exact division does not round up


def test_erlang_cells_monotone_in_load():
    assert cells_erlang(1000, 500, 0.5) <= cells_erlang(2000, 500, 0.5) <= cells_erlang(4000, 500, 0.5)
