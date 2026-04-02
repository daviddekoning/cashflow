from datetime import date
from json import dumps

import pytest
from cashflow import QCSalary, Cashflow, CashflowEncoder


def _make_salary(**overrides):
    """Helper to create a QCSalary with sensible defaults."""
    defaults = dict(
        name="Job",
        year=2025,
        starting_salary=3000.0,
        estimated_raise=0.03,
        raise_month=4,
        first_pay_day=date(2025, 1, 10),
        constant_deductions=200.0,
        ei_rate=0.0132,
        ei_cap=834.24,
        qpip_rate=0.00494,
        qpip_cap=464.36,
        qpp_rate=0.064,
        qpp_cap=4160.00,
    )
    defaults.update(overrides)
    return QCSalary(**defaults)


# --- Basic payday tests ---


def test_qc_salary_flow_on_first_payday():
    s = _make_salary()
    # First payday is Jan 10, 2025 (the anchor date itself)
    # gross = 3000 (before raise_month=4)
    # EI = 3000 * 0.0132 = 39.60
    # QPIP = 3000 * 0.00494 = 14.82
    # QPP = 3000 * 0.064 = 192.00
    # net = 3000 - 200 - 39.60 - 14.82 - 192.00 = 2553.58
    assert s.flow(date(2025, 1, 10)) == pytest.approx(2553.58)


def test_qc_salary_flow_off_day():
    s = _make_salary()
    assert s.flow(date(2025, 1, 11)) == 0.0


def test_qc_salary_flow_second_payday():
    s = _make_salary()
    # Second payday: Jan 24
    assert s.flow(date(2025, 1, 24)) == pytest.approx(2553.58)


# --- Year boundary tests ---


def test_qc_salary_returns_zero_before_year():
    s = _make_salary()
    assert s.flow(date(2024, 12, 31)) == 0.0


def test_qc_salary_returns_zero_after_year():
    s = _make_salary()
    assert s.flow(date(2026, 1, 9)) == 0.0


# --- Raise tests ---


def test_qc_salary_raise_applied_after_raise_month():
    s = _make_salary()
    # First payday in April: need to find it
    # Paydays: Jan 10, 24; Feb 7, 21; Mar 7, 21; Apr 4, 18, ...
    # Apr 4 is the first payday in raise_month=4
    # gross_raised = 3000 * 1.03 = 3090
    # deductions are percentage of raised gross
    apr4_flow = s.flow(date(2025, 4, 4))
    jan10_flow = s.flow(date(2025, 1, 10))
    assert apr4_flow > jan10_flow


# --- Deduction cap tests ---


def test_qc_salary_deduction_caps_increase_net():
    """Once deduction caps are hit, net pay should increase."""
    s = _make_salary(
        ei_cap=50.0,  # Very low cap, hit after ~2 paydays
        qpip_cap=50.0,
        qpp_cap=50.0,
    )
    first_pay = s.flow(date(2025, 1, 10))

    # Find a later payday where all caps should be hit
    # With caps of 50 each, after 2 paydays EI (39.6/pay) and QPIP (14.82/pay) nearly exhausted
    # By the 4th payday (Feb 21), all should be capped
    later_pay = s.flow(date(2025, 3, 7))
    assert later_pay > first_pay


def test_qc_salary_all_caps_hit_gives_max_net():
    """After all caps are hit, net = gross - constant_deductions."""
    s = _make_salary(
        ei_cap=0.0,
        qpip_cap=0.0,
        qpp_cap=0.0,
        estimated_raise=0.0,
        raise_month=13,  # No raise
    )
    # With zero caps, no variable deductions apply
    # net = 3000 - 200 = 2800
    assert s.flow(date(2025, 1, 10)) == pytest.approx(2800.0)


# --- Serialization tests ---


def test_qc_salary_to_dict_type():
    s = _make_salary()
    d = s.to_dict()
    assert d["details"]["type"] == "qc-salary"
    assert d["details"]["year"] == 2025
    assert d["details"]["starting_salary"] == 3000.0


def test_qc_salary_roundtrip_from_dict():
    s = _make_salary()
    d = s.to_dict()
    s2 = Cashflow.from_dict(d)
    assert isinstance(s2, QCSalary)
    assert s2.flow(date(2025, 1, 10)) == s.flow(date(2025, 1, 10))


def test_qc_salary_json_roundtrip():
    s = _make_salary()
    js = dumps(s, cls=CashflowEncoder)
    s2 = Cashflow.from_json(js)
    assert isinstance(s2, QCSalary)
    assert s2.name == "Job"
    assert s2.flow(date(2025, 1, 10)) == s.flow(date(2025, 1, 10))


# --- Edge case: anchor date before the year ---


def test_qc_salary_anchor_before_year():
    """Anchor date from a previous year still produces correct biweekly paydays."""
    s = _make_salary(first_pay_day=date(2024, 1, 3))
    # 2024-01-03 + 26*14 = 2024-01-03 + 364 = 2025-01-01
    assert s.flow(date(2025, 1, 1)) == pytest.approx(2553.58)


# --- No raise scenario ---


def test_qc_salary_no_raise():
    """When raise_month is 13 (beyond December), no raise is applied all year."""
    s = _make_salary(raise_month=13, estimated_raise=0.10)
    first = s.flow(date(2025, 1, 10))
    # All paydays should have the same gross (before caps start changing things)
    second = s.flow(date(2025, 1, 24))
    assert first == second
