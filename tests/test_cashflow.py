import io
import os
import sqlite3
from datetime import date
from json import dumps, loads

import pytest
from pytest import approx, raises

from cashflow import (
    Cashflow,
    CashflowEncoder,
    CompositeCashflow,
    EndOn,
    IntervalCashflow,
    Limited,
    MonthlyCashflow,
    OneTimeCashflow,
    StartOn,
    flow,
    get_projection,
    main,
    run_cashflows,
    sum_cashflows,
    store_projection,
)


@pytest.fixture
def interval_json():
    return '{"name": "I", "details": {"type": "interval", "first_date": "2023-01-01", "interval": 14, "amount": 100}}'


@pytest.fixture
def interval_cf(interval_json):
    return Cashflow.from_json(interval_json)


@pytest.fixture
def monthly_json():
    return '{"name": "M", "details": {"type": "monthly", "day": 1, "amount": 10}}'


@pytest.fixture
def monthly_cf(monthly_json):
    return Cashflow.from_json(monthly_json)


@pytest.fixture
def onetime_json():
    return '{"name": "O", "details": {"type": "one-time", "date": "2023-01-01", "amount": 5}}'


@pytest.fixture
def onetime_cf(onetime_json):
    return Cashflow.from_json(onetime_json)


@pytest.fixture
def composite_json():
    return '{"name": "C", "details": {"type": "composite", "cashflows": [{"name": "S", "details": {"type": "one-time", "date": "2023-01-01", "amount": 1}}]}}'


@pytest.fixture
def composite_cf(composite_json):
    return Cashflow.from_json(composite_json)


@pytest.fixture
def limited_json():
    return """{
        "name": "L", "start": "2023-01-01", "end": "2023-01-02", "limit": 15,
        "details": {"type": "interval", "first_date": "2023-01-01", "interval": 1, "amount": 10}
    }"""


@pytest.fixture
def complex_cf(limited_json):
    return Cashflow.from_json(limited_json)


# --- IntervalCashflow Tests ---


def test_interval_from_json_is_instance(interval_cf):
    assert isinstance(interval_cf, IntervalCashflow)


def test_interval_flow_on_date(interval_cf):
    assert interval_cf.flow(date(2023, 1, 1)) == 100


def test_interval_flow_off_date(interval_cf):
    assert interval_cf.flow(date(2023, 1, 2)) == 0


def test_interval_to_dict_type(interval_cf):
    assert interval_cf.to_dict()["details"]["type"] == "interval"


# --- MonthlyCashflow Tests ---


def test_monthly_from_json_is_instance(monthly_cf):
    assert isinstance(monthly_cf, MonthlyCashflow)


def test_monthly_flow_on_date(monthly_cf):
    assert monthly_cf.flow(date(2023, 1, 1)) == 10


def test_monthly_flow_off_date(monthly_cf):
    assert monthly_cf.flow(date(2023, 1, 2)) == 0


def test_monthly_custom_months_flow():
    m = MonthlyCashflow("Q", 1, 10, [1, 4])
    assert m.flow(date(2023, 2, 1)) == 0


# --- OneTimeCashflow Tests ---


def test_onetime_from_json_is_instance(onetime_cf):
    assert isinstance(onetime_cf, OneTimeCashflow)


def test_onetime_flow_on_date(onetime_cf):
    assert onetime_cf.flow(date(2023, 1, 1)) == 5


def test_onetime_flow_off_date(onetime_cf):
    assert onetime_cf.flow(date(2023, 1, 2)) == 0


# --- CompositeCashflow Tests ---


def test_composite_from_json_is_instance(composite_cf):
    assert isinstance(composite_cf, CompositeCashflow)


def test_composite_flow_on_date(composite_cf):
    assert composite_cf.flow(date(2023, 1, 1)) == 1


def test_composite_manual_add():
    comp = CompositeCashflow("M")
    comp.add(Cashflow("B"))
    assert comp.to_dict()["details"]["cashflows"][0]["name"] == "B"


# --- Limited, StartOn, EndOn Tests ---


def test_complex_from_json_is_instance(complex_cf):
    assert isinstance(complex_cf, EndOn)


def test_complex_is_start_on(complex_cf):
    assert isinstance(complex_cf.cashflow, StartOn)


def test_complex_is_limited(complex_cf):
    assert isinstance(complex_cf.cashflow.cashflow, Limited)


def test_complex_flow_before_start(complex_cf):
    assert complex_cf.flow(date(2022, 12, 31)) == 0


def test_complex_flow_at_start(complex_cf):
    assert complex_cf.flow(date(2023, 1, 1)) == 10


def test_complex_flow_capped(complex_cf):
    assert complex_cf.flow(date(2023, 1, 2)) == 5


def test_complex_flow_after_end(complex_cf):
    assert complex_cf.flow(date(2023, 1, 3)) == 0


# --- Error Handling Tests ---


def test_from_dict_missing_type():
    with raises(ValueError, match="type must be specified"):
        Cashflow.from_dict({"name": "N", "details": {}})


def test_from_dict_unknown_type():
    with raises(ValueError, match="X is not a supported"):
        Cashflow.from_dict({"name": "B", "details": {"type": "X"}})


# --- Encoder Tests ---


def test_encoder_serializes_cashflow():
    cf = Cashflow("T")
    assert loads(dumps(cf, cls=CashflowEncoder))["name"] == "T"


def test_encoder_raises_type_error_on_unknown():
    class U:
        pass

    with raises(TypeError):
        dumps(U(), cls=CashflowEncoder)


# --- Global Utility Tests ---


def test_flow_total(onetime_cf):
    assert flow([onetime_cf], date(2023, 1, 1)) == 5  # 5 is the amount in onetime_json


def test_run_cashflows_writes_to_stream(onetime_cf):
    out = io.StringIO()
    run_cashflows([onetime_cf], date(2023, 1, 1), 1, out)
    assert "Date,O" in out.getvalue()  # O is the name in onetime_json


def test_sum_cashflows_labels(onetime_cf):
    df = sum_cashflows([onetime_cf], date(2023, 1, 1), 2, 0)
    assert "O: 5" in df.loc[date(2023, 1, 1), "labels"]


# --- Projection Tests ---


@pytest.fixture
def temp_db_path():
    path = "test_run.db"
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_store_and_get_projection(temp_db_path, onetime_cf):
    conn = sqlite3.connect(temp_db_path)
    df = sum_cashflows([onetime_cf], date(2023, 1, 1), 1, 0)
    store_projection(df, conn, "working")
    c2 = sqlite3.connect(temp_db_path)
    assert len(get_projection(c2, "working")) == 1


def test_store_projection_raises_on_duplicate(temp_db_path, onetime_cf):
    conn = sqlite3.connect(temp_db_path)
    df = sum_cashflows([onetime_cf], date(2023, 1, 1), 1, 0)
    store_projection(df, conn, "my_proj")
    c2 = sqlite3.connect(temp_db_path)
    with raises(ValueError, match="exists"):
        store_projection(df.copy(), c2, "my_proj")


def test_store_projection_raises_on_closed_conn(temp_db_path, onetime_cf):
    conn = sqlite3.connect(temp_db_path)
    conn.close()
    df = sum_cashflows([onetime_cf], date(2023, 1, 1), 1, 0)
    with raises(sqlite3.ProgrammingError):
        store_projection(df.copy(), conn, "err")


# --- Direct to_dict Tests ---


def test_interval_to_dict_direct():
    icf = IntervalCashflow("I", date(2023, 1, 1), 1, 1)
    assert icf.to_dict()["details"]["type"] == "interval"


def test_monthly_to_dict_direct():
    mcf = MonthlyCashflow("M", 1, 1)
    assert mcf.to_dict()["details"]["type"] == "monthly"


def test_starton_to_dict_direct():
    icf = IntervalCashflow("I", date(2023, 1, 1), 1, 1)
    scf = StartOn(date(2023, 1, 1), icf)
    assert scf.to_dict()["start"] == "2023-01-01"


def test_endon_to_dict_direct():
    icf = IntervalCashflow("I", date(2023, 1, 1), 1, 1)
    ecf = EndOn(date(2023, 1, 1), icf)
    assert ecf.to_dict()["end"] == "2023-01-01"


def test_limited_to_dict_direct():
    icf = IntervalCashflow("I", date(2023, 1, 1), 1, 1)
    lcf = Limited(date(2023, 1, 1), 10, icf)
    assert lcf.to_dict()["limit"] == 10


def test_composite_to_dict_direct():
    ccf = CompositeCashflow("C")
    assert ccf.to_dict()["details"]["type"] == "composite"


# --- Miscellaneous Tests ---


def test_cashflow_base_to_dict():
    assert Cashflow("G").to_dict() == {"name": "G"}


def test_main_execution():
    main()
