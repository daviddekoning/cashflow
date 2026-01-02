from datetime import date, datetime
from json import dumps
import pytest
from cashflow import SalaryCashflow, Cashflow, CashflowEncoder


@pytest.mark.parametrize(
    "starting_date, gross_salary, test_date, expected_flow",
    [
        (date(2023, 1, 1), 1000, date(2023, 1, 1), 1000),  # Payday
        (date(2023, 1, 1), 1000, date(2023, 1, 14), 0),  # Off-day
        (date(2023, 1, 1), 1000, date(2023, 1, 15), 1000),  # Next payday
        (date(2023, 1, 1), 1000, date(2023, 1, 16), 0),  # Off-day
        (date(2023, 1, 1), 1000, date(2024, 1, 14), 1000),  # Subsequent year payday
    ],
)
def test_salary_flow_scenarios(starting_date, gross_salary, test_date, expected_flow):
    s = SalaryCashflow(
        name="Job",
        starting_date=starting_date,
        gross_salary=gross_salary,
        estimated_raise={"Month": 1, "raise": 0.0},
        constant_deductions=0,
        variable_deductions=[],
    )
    assert s.flow(test_date) == pytest.approx(expected_flow)


@pytest.mark.parametrize(
    "raise_month, raise_pct, test_date, expected_flow",
    [
        (7, 0.1, date(2023, 1, 1), 1000),
        (7, 0.1, date(2023, 1, 2), 0),
        (7, 0.1, date(2023, 7, 2), 1100),
        (7, 0.1, date(2024, 1, 14), 1100),
        (7, 0.1, date(2024, 7, 14), 1100 * 1.1),
    ],
)
def test_salary_raise_scenarios(raise_month, raise_pct, test_date, expected_flow):
    s = SalaryCashflow(
        name="Job",
        starting_date=date(2023, 1, 1),
        gross_salary=1000,
        estimated_raise={"Month": raise_month, "raise": raise_pct},
        constant_deductions=0,
        variable_deductions=[],
    )
    assert s.flow(test_date) == pytest.approx(expected_flow)


@pytest.mark.parametrize(
    "test_date, expected_flow",
    [
        (date(2024, 1, 1), 5683.95),  # Payday 1: 7500 - 1200 - 37.05 - 480 - 99
        (date(2024, 4, 8), 5959.31),
        (date(2024, 4, 22), 6222.39),  # Payday 9: EI and QPP hit caps
        (date(2024, 6, 17), 6587.65),  # Payday 13: QPIP hits cap
        (date(2024, 7, 1), 6600.00),  # Payday 14: All caps hit
        (date(2024, 7, 15), 6600.00),
        (date(2025, 1, 13), 5959.31),
    ],
)
def test_salary_deduction_scenarios(test_date, expected_flow):
    # Quebec 2024 Rates:
    # QPIP: 0.494%, cap 464.36
    # QPP: 6.40%, cap 4160.00 (simplified)
    # EI: 1.32%, cap 834.24
    v_deductions = [
        {"name": "QPIP", "amount": 0.00494, "cap": 464.36},
        {"name": "QPP", "amount": 0.064, "cap": 4160.00},
        {"name": "EI", "amount": 0.0132, "cap": 834.24},
    ]
    s = SalaryCashflow(
        name="Job",
        starting_date=date(2024, 1, 1),
        gross_salary=7500,
        estimated_raise={"Month": 4, "raise": 0.04},
        constant_deductions=1200,
        variable_deductions=v_deductions,
    )
    assert s.flow(test_date) == pytest.approx(expected_flow)


def test_salary_serialization():
    s = SalaryCashflow(
        name="Job",
        starting_date=date(2023, 1, 1),
        gross_salary=1000,
        estimated_raise={"Month": 7, "raise": 0.1},
        constant_deductions=100,
        variable_deductions=[{"name": "Tax", "amount": 0.05, "cap": 60}],
    )

    # To dict
    d = s.to_dict()
    assert d["details"]["type"] == "salary"
    assert d["details"]["gross_salary"] == 1000

    # From dict/json
    s2 = Cashflow.from_dict(d)
    assert isinstance(s2, SalaryCashflow)
    assert s2.name == "Job"
    assert s2.gross_salary == 1000
    assert s2.constant_deductions == 100

    # Json serialization
    js = dumps(s, cls=CashflowEncoder)
    s3 = Cashflow.from_json(js)
    assert s3.name == "Job"
    assert s3.flow(date(2023, 1, 1)) == s.flow(date(2023, 1, 1))


def test_salary_memoization():
    s = SalaryCashflow(
        name="Job",
        starting_date=date(2023, 1, 1),
        gross_salary=1000,
        estimated_raise={"Month": 1, "raise": 0.0},
        constant_deductions=0,
        variable_deductions=[],
    )
    # Check if _get_cashflows is actually memoized (indirectly by checking if it works)
    df1 = s._get_cashflows(2023)
    df2 = s._get_cashflows(2023)
    assert df1 is df2


def test_salary_flow_not_in_index():
    s = SalaryCashflow(
        name="Job",
        starting_date=date(2023, 1, 1),
        gross_salary=1000,
        estimated_raise={"Month": 1, "raise": 0.0},
        constant_deductions=0,
        variable_deductions=[],
    )
    # Passing a datetime with hours will not match the daily index
    assert s.flow(datetime(2023, 1, 1, 12, 0)) == 0.0


def test_onetime_to_dict_direct():
    from cashflow import OneTimeCashflow

    cf = OneTimeCashflow(name="O", date=date(2023, 1, 1), amount=10)
    d = cf.to_dict()
    assert d["details"]["type"] == "one-time"


def test_limited_flow_gap():
    from cashflow import IntervalCashflow, Limited

    icf = IntervalCashflow(
        name="I", start_date=date(2023, 1, 1), interval_days=2, amount=10
    )
    lcf = Limited(startDate=date(2023, 1, 1), maximum=100, cashflow=icf)
    # Jan 1 has 10. Jan 2 has 0.
    # This should hit the 'else' branch in Limited.flow
    assert lcf.flow(date(2023, 1, 2)) == 0
