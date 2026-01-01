from cashflow import (
    Cashflow,
    IntervalCashflow,
    StartOn,
    EndOn,
    Limited,
    OneTimeCashflow,
    MonthlyCashflow,
    CompositeCashflow,
    CashflowEncoder,
    run_cashflows,
    flow,
    sum_cashflows,
    store_projection,
    get_projection,
    main,
)
from json import dumps, loads
from datetime import date
from pytest import approx, raises
import sqlite3
import io
import os


def test_interval_full():
    input_str = '{"name": "I", "details": {"type": "interval", "first_date": "2023-01-01", "interval": 14, "amount": 100}}'
    cf = Cashflow.from_json(input_str)
    assert isinstance(cf, IntervalCashflow)
    assert cf.flow(date(2023, 1, 1)) == 100
    assert cf.flow(date(2023, 1, 2)) == 0  # Hits else in flow
    assert cf.to_dict()["details"]["type"] == "interval"


def test_monthly_full():
    input_str = '{"name": "M", "details": {"type": "monthly", "day": 1, "amount": 10}}'
    cf = Cashflow.from_json(input_str)
    assert isinstance(cf, MonthlyCashflow)
    assert cf.flow(date(2023, 1, 1)) == 10
    assert cf.flow(date(2023, 1, 2)) == 0
    m = MonthlyCashflow("Q", 1, 10, [1, 4])
    assert m.flow(date(2023, 2, 1)) == 0


def test_onetime_full():
    input_str = '{"name": "O", "details": {"type": "one-time", "date": "2023-01-01", "amount": 5}}'
    cf = Cashflow.from_json(input_str)
    assert isinstance(cf, OneTimeCashflow)
    assert cf.flow(date(2023, 1, 1)) == 5
    assert cf.flow(date(2023, 1, 2)) == 0


def test_composite_full():
    input_str = '{"name": "C", "details": {"type": "composite", "cashflows": [{"name": "S", "details": {"type": "one-time", "date": "2023-01-01", "amount": 1}}]}}'
    cf = Cashflow.from_json(input_str)
    assert isinstance(cf, CompositeCashflow)
    assert cf.flow(date(2023, 1, 1)) == 1
    comp = CompositeCashflow("M")
    comp.add(Cashflow("B"))
    assert comp.to_dict()["details"]["cashflows"][0]["name"] == "B"


def test_limited_start_end_full():
    input_str = """{
        "name": "L", "start": "2023-01-01", "end": "2023-01-02", "limit": 15,
        "details": {"type": "interval", "first_date": "2023-01-01", "interval": 1, "amount": 10}
    }"""
    # Result should be EndOn(StartOn(Limited(Interval)))
    cf = Cashflow.from_json(input_str)
    assert isinstance(cf, EndOn)
    assert isinstance(cf.cashflow, StartOn)
    assert isinstance(cf.cashflow.cashflow, Limited)

    # Test ranges to hit else branches in flow()
    assert cf.flow(date(2022, 12, 31)) == 0  # Hits EndOn -> StartOn (else)
    assert cf.flow(date(2023, 1, 1)) == 10  # Hits all
    assert cf.flow(date(2023, 1, 2)) == 5  # Hits all (Limited caps it)
    assert cf.flow(date(2023, 1, 3)) == 0  # Hits EndOn (else)


def test_from_dict_errors():
    with raises(ValueError, match="type must be specified"):
        Cashflow.from_dict({"name": "N", "details": {}})
    with raises(ValueError, match="X is not a supported"):
        Cashflow.from_dict({"name": "B", "details": {"type": "X"}})


def test_cashflow_encoder():
    cf = Cashflow("T")
    assert loads(dumps(cf, cls=CashflowEncoder))["name"] == "T"

    class U:
        pass

    with raises(TypeError):
        dumps(U(), cls=CashflowEncoder)


def test_global_utils():
    cfs = [OneTimeCashflow("A", date(2023, 1, 1), 10)]
    assert flow(cfs, date(2023, 1, 1)) == 10
    out = io.StringIO()
    run_cashflows(cfs, date(2023, 1, 1), 1, out)
    assert "Date,A" in out.getvalue()
    df = sum_cashflows(cfs, date(2023, 1, 1), 2, 0)
    assert "A: 10" in df.loc[date(2023, 1, 1), "labels"]


def test_projections():
    db = "test3.db"
    if os.path.exists(db):
        os.remove(db)
    conn = sqlite3.connect(db)
    df = sum_cashflows(
        [OneTimeCashflow("P", date(2023, 1, 1), 1)], date(2023, 1, 1), 1, 0
    )
    store_projection(df, conn, "working")
    c2 = sqlite3.connect(db)
    assert len(get_projection(c2, "working")) == 1
    c5 = sqlite3.connect(db)
    c5.close()
    with raises(Exception):  # sqlite3 raises varied errors on closed conn
        store_projection(df.copy(), c5, "err")
    if os.path.exists(db):
        os.remove(db)


def test_to_dict_direct():
    d = date(2023, 1, 1)
    icf = IntervalCashflow("I", d, 1, 1)
    assert icf.to_dict()["details"]["type"] == "interval"
    mcf = MonthlyCashflow("M", 1, 1)
    assert mcf.to_dict()["details"]["type"] == "monthly"
    scf = StartOn(d, icf)
    assert scf.to_dict()["start"] == "2023-01-01"
    ecf = EndOn(d, icf)
    assert ecf.to_dict()["end"] == "2023-01-01"
    lcf = Limited(d, 10, icf)
    assert lcf.to_dict()["limit"] == 10
    ccf = CompositeCashflow("C")
    assert ccf.to_dict()["details"]["type"] == "composite"


def test_main():
    main()
