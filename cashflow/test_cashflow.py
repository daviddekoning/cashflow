
from . import Cashflow, IntervalCashflow, StartOn, EndOn, Limited, OneTimeCashflow, MonthlyCashflow
from json import dumps
from datetime import date, datetime
from pytest import approx

def defaultconverter(o):
  if isinstance(o, date):
      return datetime.strftime(o,"%Y-%m-%d")


def test_interval():
    input = '''{
    "name": "Arup Pay 2021",
    "start": "2021-01-01",
    "end": "2021-12-31",
    "details": {
        "type": "interval",
        "first_date": "2019-01-11",
        "interval": 14,
        "amount": 3301.28
    }
}
'''
    cf = Cashflow.from_json(input)
#    print(cf.__dict__)
    assert cf.name == "Arup Pay 2021"
    assert type(cf) == EndOn
    assert type(cf.cashflow) == StartOn
    assert type(cf.cashflow.cashflow) == IntervalCashflow
    assert cf.cashflow.cashflow.amount == approx(3301.28)
    assert cf.cashflow.cashflow.interval_days == 14
    assert cf.cashflow.cashflow.start_date == date(2019, 1, 11)
    
    print(dumps(cf.to_dict()))

def test_onetime():
    input = '''{
    "name": "Bonus",
    "details": {
        "type": "one-time",
        "date": "2023-03-04",
        "amount": 19650
    }
}
'''

def test_composite():
    input = '''{
    "name": "Pay",
    "start": "2022-01-01",
    "end": "2022-12-31",
    "details": {
        "type": "composite",
        "cashflows": [
            {        
                "name": "Bonus",
                "details": {
                    "type": "one-time",
                    "date": "2023-03-04",
                    "amount": 19650
                }
            },
            {
                "name": "Arup Pay 2022",
                "start": "2022-01-01",
                "end": "2022-12-31",
                "details": {
                    "type": "interval",
                    "first_date": "2019-01-11",
                    "interval": 14,
                    "amount": 3301.28
                }
            }
        ]
    }
}'''

    cf = Cashflow.from_json(input)
    assert cf.flow(date(2022,1,7)) == approx(3301.28)
    assert cf.flow(date(2023,3,4)) == approx(0)
    print(dumps(cf.to_dict(), indent = 4))
