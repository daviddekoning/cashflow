from datetime import date
from json import dumps

import pytest
from cashflow import QCMultiYearSalary, QCSalary, Cashflow, CashflowEncoder


def _make_multi(**overrides):
    """Helper to create a QCMultiYearSalary with sensible defaults."""
    defaults = dict(
        name="Job",
        year=2025,
        ending_year=2027,
        starting_salary=3000.0,
        annual_raise=0.03,
        raise_month=4,
        first_pay_day=date(2025, 1, 10),
        constant_deductions=200.0,
        ei_rate=0.0132,
        ei_cap=834.24,
        qpip_rate=0.00494,
        qpip_cap=464.36,
        qpp_rate=0.064,
        qpp_cap=4160.00,
        annual_ei_cap_increase=0.02,
        annual_qpip_cap_increase=0.02,
        annual_qpp_cap_increase=0.02,
        annual_constant_deductions_increase=0.02,
    )
    defaults.update(overrides)
    return QCMultiYearSalary(**defaults)


# --- Basic delegation tests ---


def test_multi_year_delegates_to_first_year():
    m = _make_multi()
    s = QCSalary(
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
    assert m.flow(date(2025, 1, 10)) == s.flow(date(2025, 1, 10))


def test_multi_year_second_year_has_increased_salary():
    m = _make_multi()
    # Year 2 salary = 3000 * 1.03 = 3090 (annual_raise=0.03)
    s2 = QCSalary(
        name="Job",
        year=2026,
        starting_salary=3000.0 * 1.03,
        estimated_raise=0.03,
        raise_month=4,
        first_pay_day=date(2025, 1, 10),
        constant_deductions=200.0 * 1.02,
        ei_rate=0.0132,
        ei_cap=834.24 * 1.02,
        qpip_rate=0.00494,
        qpip_cap=464.36 * 1.02,
        qpp_rate=0.064,
        qpp_cap=4160.00 * 1.02,
    )
    # Find a payday in 2026 — the biweekly cycle from 2025-01-10
    # continues into 2026
    for d in s2._flows:
        assert m.flow(d) == pytest.approx(s2.flow(d))
        break  # Just check the first payday


def test_multi_year_third_year_compounds():
    m = _make_multi()
    # Year 3 salary = 3000 * 1.03^2
    s3 = QCSalary(
        name="Job",
        year=2027,
        starting_salary=3000.0 * 1.03**2,
        estimated_raise=0.03,
        raise_month=4,
        first_pay_day=date(2025, 1, 10),
        constant_deductions=200.0 * 1.02**2,
        ei_rate=0.0132,
        ei_cap=834.24 * 1.02**2,
        qpip_rate=0.00494,
        qpip_cap=464.36 * 1.02**2,
        qpp_rate=0.064,
        qpp_cap=4160.00 * 1.02**2,
    )
    for d in s3._flows:
        assert m.flow(d) == pytest.approx(s3.flow(d))
        break


# --- Year boundary tests ---


def test_multi_year_zero_before_range():
    m = _make_multi()
    assert m.flow(date(2024, 6, 15)) == 0.0


def test_multi_year_zero_after_range():
    m = _make_multi()
    assert m.flow(date(2028, 6, 15)) == 0.0


def test_multi_year_off_day_zero():
    m = _make_multi()
    assert m.flow(date(2025, 1, 11)) == 0.0


# --- Single year span ---


def test_multi_year_single_year():
    m = _make_multi(ending_year=2025)
    assert m.flow(date(2025, 1, 10)) != 0.0
    assert m.flow(date(2026, 1, 10)) == 0.0


# --- Serialization ---


def test_multi_year_to_dict_type():
    m = _make_multi()
    d = m.to_dict()
    assert d["details"]["type"] == "qc-multi-year-salary"
    assert d["details"]["ending_year"] == 2027
    assert d["details"]["annual_raise"] == 0.03


def test_multi_year_roundtrip_from_dict():
    m = _make_multi()
    d = m.to_dict()
    m2 = Cashflow.from_dict(d)
    assert isinstance(m2, QCMultiYearSalary)
    assert m2.flow(date(2025, 1, 10)) == m.flow(date(2025, 1, 10))
    # Also check a later year
    for d_date in m._salaries[2027]._flows:
        assert m2.flow(d_date) == pytest.approx(m.flow(d_date))
        break


def test_multi_year_json_roundtrip():
    m = _make_multi()
    js = dumps(m, cls=CashflowEncoder)
    m2 = Cashflow.from_json(js)
    assert isinstance(m2, QCMultiYearSalary)
    assert m2.flow(date(2025, 1, 10)) == m.flow(date(2025, 1, 10))


# --- Zero increases ---


def test_multi_year_zero_increases_same_each_year():
    m = _make_multi(
        annual_raise=0.0,
        annual_ei_cap_increase=0.0,
        annual_qpip_cap_increase=0.0,
        annual_qpp_cap_increase=0.0,
        annual_constant_deductions_increase=0.0,
        raise_month=13,
    )
    # First paydays in 2025 and 2026 should have the same net
    first_2025 = m.flow(date(2025, 1, 10))
    # Find first payday in 2026
    for d in m._salaries[2026]._flows:
        first_2026 = m.flow(d)
        break
    assert first_2025 == pytest.approx(first_2026)
