from datetime import timedelta
import numpy as np
import pandas as pd

__version__ = '1.1'

class Cashflow:
    def __init__(self,name):
        self.name = name
    
class IntervalCashflow(Cashflow):
    def __init__(self, name, start_date, interval_days, amount):
        super().__init__(name)
        self.start_date = start_date
        self.interval_days = interval_days
        self.amount = amount

    def flow(self,date):
        delta = date - self.start_date

        if delta.days >= 0 and (delta.days % self.interval_days ) == 0:
            return self.amount
        else:
            return 0

class Limited(Cashflow):
    
    def __init__(self, cashflow, startDate, maximum):
        self.flows = {}
        sum = 0
        d = startDate
        maximum = abs(maximum)
        done = False
        while not done:
            f = cashflow.flow(d)
            if abs(f) > 0.01:
                if abs(sum+f) < maximum:
                    self.flows[d] = f
                else:
                    self.flows[d] = np.sign(sum+f)*maximum - sum
                    done = True
                sum += f
            d = d + timedelta(days=1)

    def flow(self, date):
        if date in self.flows:
            return self.flows[date]
        else:
            return 0
    

class StartOn(Cashflow):
    def __init__(self, date, cashflow):
        self.start_date = date
        self.cashflow = cashflow
    
    def flow(self, date):
        if date >= self.start_date:
            return self.cashflow.flow(date)
        else:
            return 0

class EndOn(Cashflow):
    def __init__(self, date, cashflow):
        self.end_date = date
        self.cashflow = cashflow

    def flow(self, date):
        if date <= self.end_date:
            return self.cashflow.flow(date)
        else:
            return 0

class MonthlyCashflow(Cashflow):
    def __init__(self, name, day_of_month, amount, months=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]):
        super().__init__(name)
        self.day_of_month = day_of_month
        self.amount = amount
        self.months = months
    
    def flow(self,date):
        if (date.day == self.day_of_month) & (date.month in self.months):
            return self.amount
        else:
            return 0

class OneTimeCashflow(Cashflow):
    def __init__(self, name, date, amount):
        super().__init__(name)
        self.date = date
        self.amount = amount
        
    def flow(self, date):
        if self.date == date:
            return self.amount
        return 0

class CompositeCashflow(Cashflow):
    def __init__(self, name):
        super().__init__(name)
        self.cashflows = []
    
    def add(self, cashflow):
        self.cashflows.append( cashflow )
    
    def flow(self, date):
        sum = 0
        for cf in self.cashflows:
            sum = sum + cf.flow(date)
        
        return sum

def run_cashflows(cashflows, startDate, duration, stream):
    stream.write("Date")
    for c in cashflows:
        stream.write("," + c.name)
    stream.write("\n")

    date_list = [startDate + timedelta(days=x) for x in range(0, duration)]

    for d in date_list:
        stream.write( str(d ))
        for c in cashflows:
            stream.write(",")
            amount = c.flow( d );
            if amount != 0:
                stream.write( str(amount) )
        stream.write("\n")

def flow(cashflows, date):
    total = 0
    for c in cashflows:
        total += c.flow(date)
    return total

def sum_cashflows(cashflows, start_date, duration, starting_balance):
    df = pd.DataFrame(index=[t.to_pydatetime().date() for t in pd.date_range(start_date,periods=duration)])
    for c in cashflows:
        df[c.name] = [flow([c], i) for i in df.index]

    labels = []
    for index, row in df.iterrows():
        label = []
        for i, v in row.iteritems():
            if v != 0.0:
                label.append("{}: {}".format(i,v))
        if len(labels) == 0:
            labels.append("")
        else:
            labels.append(", ".join(label))

    df['labels'] = labels

    df['total'] = [ flow(cashflows, i) for i in df.index]
    df['balance'] = df['total'].cumsum().add(starting_balance)
    df['min_forward'] = [df['balance'][i:].min() for i in df.index]
    return df

# Demonstration code
if __name__ == "__main__":
    from datetime import date
    c = []
    c.append( IntervalCashflow( "Payday", date(2016,10,21), 14, 1000) )
    c.append( MonthlyCashflow("Rent", 1, -600) )
    
    with open("demo.csv", 'w') as f:
        runCashflows(c, date(2016,10,21),180, f)
