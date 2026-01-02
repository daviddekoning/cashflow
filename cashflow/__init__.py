from datetime import timedelta, datetime as dt
import numpy as np
import pandas as pd
from sqlite3 import Connection, OperationalError
from json import loads, JSONEncoder
from datetime import datetime, date
import os
from functools import lru_cache

__version__ = "1.2"


def _to_date(date_string):
    return dt.strptime(date_string, "%Y-%m-%d").date()


def _to_string(date):
    return dt.strftime(date, "%Y-%m-%d")


class CashflowEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Cashflow):
            return o.to_dict()
        else:
            return super().default(o)


class Cashflow:
    def __init__(self, name):
        self.name = name

    def to_dict(self):
        return {"name": self.name}

    def from_json(desc):
        return Cashflow.from_dict(loads(desc))

    def from_dict(data):
        try:
            cf_type = data["details"]["type"]
        except KeyError:
            raise ValueError("Cashflow type must be specified.")

        if cf_type == "one-time":
            cf = OneTimeCashflow(
                data["name"],
                _to_date(data["details"]["date"]),
                data["details"]["amount"],
            )
        elif cf_type == "interval":
            cf = IntervalCashflow(
                data["name"],
                _to_date(data["details"]["first_date"]),
                data["details"]["interval"],
                data["details"]["amount"],
            )
        elif cf_type == "monthly":
            try:
                months = data["details"]["months"]
            except KeyError:
                months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

            cf = MonthlyCashflow(
                data["name"], data["details"]["day"], data["details"]["amount"], months
            )
        elif cf_type == "composite":
            cf = CompositeCashflow(data["name"])
            for flow in data["details"]["cashflows"]:
                cf.add(Cashflow.from_dict(flow))
        elif cf_type == "salary":
            cf = SalaryCashflow(
                data["name"],
                _to_date(data["details"]["starting_date"]),
                data["details"]["gross_salary"],
                data["details"]["estimated_raise"],
                data["details"]["constant_deductions"],
                data["details"]["variable_deductions"],
            )
        else:
            raise ValueError(
                f"{data['details']['type']} is not a supported cashflow type"
            )

        try:
            cf = Limited(_to_date(data["start"]), data["limit"], cf)
        except KeyError:
            pass

        try:
            cf = StartOn(_to_date(data["start"]), cf)
        except KeyError:
            pass

        try:
            cf = EndOn(_to_date(data["end"]), cf)
        except KeyError:
            pass

        return cf


class IntervalCashflow(Cashflow):
    def __init__(self, name, start_date, interval_days, amount):
        super().__init__(name)
        self.start_date = start_date
        self.interval_days = interval_days
        self.amount = amount

    def to_dict(self, d=None):
        if d is None:
            d = super().to_dict()
        if "details" not in d:
            d["details"] = {}
        d["details"]["type"] = "interval"
        d["details"]["first_date"] = _to_string(self.start_date)
        d["details"]["interval"] = self.interval_days
        d["details"]["amount"] = self.amount

        return d

    def flow(self, date):
        delta = date - self.start_date

        if delta.days >= 0 and (delta.days % self.interval_days) == 0:
            return self.amount
        else:
            return 0


class Limited(Cashflow):
    def __init__(self, startDate, maximum, cashflow):
        super().__init__(cashflow.name)
        self.startDate = startDate
        self.maximum = maximum
        self.cashflow = cashflow

        self.flows = {}
        sum = 0
        d = startDate
        maximum = abs(maximum)
        done = False
        while not done:
            f = cashflow.flow(d)
            if abs(f) > 0.01:
                if abs(sum + f) < maximum:
                    self.flows[d] = f
                else:
                    self.flows[d] = np.sign(sum + f) * maximum - sum
                    done = True
                sum += f
            d = d + timedelta(days=1)

    def to_dict(self, d=None):
        if d is None:
            d = super().to_dict()
        d["start"] = _to_string(self.startDate)
        d["limit"] = self.maximum

        return self.cashflow.to_dict(d)

    def flow(self, date):
        if date in self.flows:
            return self.flows[date]
        else:
            return 0


class StartOn(Cashflow):
    def __init__(self, date, cashflow):
        super().__init__(cashflow.name)
        self.start_date = date
        self.cashflow = cashflow

    def to_dict(self, d=None):
        if d is None:
            d = super().to_dict()
        d["start"] = _to_string(self.start_date)

        return self.cashflow.to_dict(d)

    def flow(self, date):
        if date >= self.start_date:
            return self.cashflow.flow(date)
        else:
            return 0


class EndOn(Cashflow):
    def __init__(self, date, cashflow):
        super().__init__(cashflow.name)
        self.end_date = date
        self.cashflow = cashflow

    def to_dict(self, d=None):
        if d is None:
            d = super().to_dict()
        d["end"] = _to_string(self.end_date)

        return self.cashflow.to_dict(d)

    def flow(self, date):
        if date <= self.end_date:
            return self.cashflow.flow(date)
        else:
            return 0


class MonthlyCashflow(Cashflow):
    def __init__(
        self, name, day_of_month, amount, months=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    ):
        super().__init__(name)
        self.day_of_month = day_of_month
        self.amount = amount
        self.months = months

    def to_dict(self, d=None):
        if d is None:
            d = super().to_dict()
        if "details" not in d:
            d["details"] = {}
        d["details"]["type"] = "monthly"
        d["details"]["day"] = self.day_of_month
        d["details"]["amount"] = self.amount
        d["details"]["months"] = self.months

        return d

    def flow(self, date):
        if (date.day == self.day_of_month) & (date.month in self.months):
            return self.amount
        else:
            return 0


class OneTimeCashflow(Cashflow):
    def __init__(self, name, date, amount):
        super().__init__(name)
        self.date = date
        self.amount = amount

    def to_dict(self, d=None):
        if d is None:
            d = super().to_dict()
        if "details" not in d:
            d["details"] = {}

        d["details"]["type"] = "one-time"
        d["details"]["date"] = _to_string(self.date)
        d["details"]["amount"] = self.amount

        return d

    def flow(self, date):
        if self.date == date:
            return self.amount
        return 0


class CompositeCashflow(Cashflow):
    def __init__(self, name):
        super().__init__(name)
        self.cashflows = []

    def to_dict(self, d=None):
        if d is None:
            d = super().to_dict()
        if "details" not in d:
            d["details"] = {}

        d["details"]["type"] = "composite"
        d["details"]["cashflows"] = [c.to_dict() for c in self.cashflows]

        return d

    def add(self, cashflow):
        self.cashflows.append(cashflow)

    def flow(self, date):
        sum = 0
        for cf in self.cashflows:
            sum = sum + cf.flow(date)

        return sum


class SalaryCashflow(Cashflow):
    def __init__(
        self,
        name,
        starting_date,
        gross_salary,
        estimated_raise,
        constant_deductions,
        variable_deductions,
    ):
        super().__init__(name)
        self.starting_date = starting_date
        self.gross_salary = gross_salary
        self.estimated_raise = estimated_raise
        self.constant_deductions = constant_deductions
        self.variable_deductions = variable_deductions

    def _num_raises(self, d):
        rm = self.estimated_raise["Month"]
        # First raise occurs in RM of starting_date's year if starting_date.month < RM
        # otherwise in RM of (starting_date's year + 1).
        first_raise_year = self.starting_date.year + (
            0 if self.starting_date.month < rm else 1
        )
        first_raise_date = date(first_raise_year, rm, 1)

        if d < first_raise_date:
            return 0

        # Total full years since the first raise date plus current year raise if applicable
        years_passed = d.year - first_raise_year
        return years_passed + (1 if d.month >= rm else 0)

    @lru_cache(maxsize=12)
    def _get_cashflows(self, year):
        start_of_year = date(year, 1, 1)
        end_of_year = date(year, 12, 31)

        # 1. Establish paydays for the year
        paydays = []
        days_diff = (start_of_year - self.starting_date).days
        if days_diff <= 0:
            current_payday = self.starting_date
        else:
            num_intervals = (days_diff + 13) // 14
            current_payday = self.starting_date + timedelta(days=num_intervals * 14)

        while current_payday <= end_of_year:
            if current_payday >= self.starting_date:
                paydays.append(current_payday)
            current_payday += timedelta(days=14)

        # 2. Build the result dataframe
        df = pd.DataFrame(
            index=pd.date_range(start_of_year, end_of_year), columns=["total"]
        )
        df["total"] = 0.0

        # Track annual caps for variable deductions
        cap_remaining = {v["name"]: v["cap"] for v in self.variable_deductions}

        for p in paydays:
            num_raises = self._num_raises(p)
            gross = self.gross_salary * (
                (1 + self.estimated_raise["raise"]) ** num_raises
            )

            payday_net = gross - self.constant_deductions
            for v in self.variable_deductions:
                raw_deduction = gross * v["amount"]
                actual_deduction = min(raw_deduction, cap_remaining[v["name"]])
                payday_net -= actual_deduction
                cap_remaining[v["name"]] -= actual_deduction

            df.at[pd.Timestamp(p), "total"] = payday_net

        return df

    def flow(self, date):
        df = self._get_cashflows(date.year)
        # pandas index uses Timestamp
        ts = pd.Timestamp(date)
        if ts in df.index:
            return df.at[ts, "total"]
        return 0.0

    def to_dict(self, d=None):
        if d is None:
            d = super().to_dict()
        if "details" not in d:
            d["details"] = {}
        d["details"]["type"] = "salary"
        d["details"]["starting_date"] = _to_string(self.starting_date)
        d["details"]["gross_salary"] = self.gross_salary
        d["details"]["estimated_raise"] = self.estimated_raise
        d["details"]["constant_deductions"] = self.constant_deductions
        d["details"]["variable_deductions"] = self.variable_deductions
        return d


def run_cashflows(cashflows, startDate, duration, stream):
    stream.write("Date")
    for c in cashflows:
        stream.write("," + c.name)
    stream.write("\n")

    date_list = [startDate + timedelta(days=x) for x in range(0, duration)]

    for d in date_list:
        stream.write(str(d))
        for c in cashflows:
            stream.write(",")
            amount = c.flow(d)
            if amount != 0:
                stream.write(str(amount))
        stream.write("\n")


def flow(cashflows, date):
    total = 0
    for c in cashflows:
        total += c.flow(date)
    return total


def sum_cashflows(cashflows, start_date, duration, starting_balance):
    df = pd.DataFrame(
        index=[
            t.to_pydatetime().date()
            for t in pd.date_range(start_date, periods=duration)
        ]
    )
    for c in cashflows:
        df[c.name] = [flow([c], i) for i in df.index]

    labels = []
    for index, row in df.iterrows():
        label = []
        for i, v in row.items():
            if v != 0.0:
                label.append("{}: {}".format(i, v))
        if len(label) == 0:
            labels.append("")
        else:
            labels.append(", ".join(label))

    df["labels"] = labels

    df["total"] = [flow(cashflows, i) for i in df.index]
    df["balance"] = df["total"].cumsum().add(starting_balance)
    df["min_forward"] = [df["balance"][i:].min() for i in df.index]
    return df


def store_projection(
    projection: pd.DataFrame, conn: Connection, projection_name: str = "working"
):
    curr = conn.cursor()
    curr.execute(
        "CREATE TABLE IF NOT EXISTS projections (timestamp TEXT, name TEXT PRIMARY KEY)"
    )
    if projection_name != "working":
        # check if the projection already exists.
        try:
            existing_name = curr.execute(
                "SELECT name FROM projections WHERE name = ? LIMIT 1",
                (projection_name,),
            ).fetchone()
        except OperationalError:
            raise
        if existing_name is not None:
            raise ValueError(
                f"The project {projection_name} already exists. Please choose a different name."
            )
    else:
        # if we are working with teh
        curr.execute('''DELETE FROM projections WHERE name = "working"''')
    # add projection info to the tables
    curr.execute(
        "INSERT INTO projections VALUES (?,?)",
        (datetime.now().isoformat(), projection_name),
    )
    conn.commit()

    projection["name"] = projection_name
    projection[["name", "total", "balance", "min_forward", "labels"]].to_sql(
        "projection_data", conn, if_exists="append", index=True, index_label="Date"
    )

    conn.commit()
    conn.close()


def get_projection(conn: Connection, projection_name: str = "working"):
    return pd.read_sql(
        "SELECT * from projection_data where name = ?",
        con=conn,
        index_col="Date",
        params=[projection_name],
    )


def main():
    c = []
    c.append(IntervalCashflow("Payday", date(2016, 10, 21), 14, 1000))
    c.append(MonthlyCashflow("Rent", 1, -600))

    with open("demo.csv", "w") as f:
        run_cashflows(c, date(2016, 10, 21), 180, f)
    if os.path.exists("demo.csv"):
        os.remove("demo.csv")


# Demonstration code
if __name__ == "__main__":
    main()
