from datetime import timedelta, datetime as dt
import numpy as np
import pandas as pd
from json import loads, JSONEncoder

__version__ = '1.1'

def _to_date(date_string):
    return dt.strptime(date_string, "%Y-%m-%d").date()

def _to_string(date):
    return dt.strftime(date,"%Y-%m-%d")

def CashflowEncoder(JSONEncoder):

    def default(o):
        if is_instance(o, Cashflow):
            return o.to_dict()
        else:
            return super().default(o)

class Cashflow:
    def __init__(self,name):
        self.name = name
    
    def to_dict(self):
        return {"name": self.name}
    
    def from_json(desc):
        return Cashflow.from_dict(loads(desc))
        
    def from_dict(data):
        
        try:
            cf_type = data['details']['type']
        except KeyError:
            raise ValueError("Cashflow type must be specified.")
        
        if cf_type == "one-time":
            cf = OneTimeCashflow(data['name'],
                                 _to_date(data['details']['date']),
                                 data['details']['amount'])
        elif cf_type == "interval":
            cf = IntervalCashflow(data['name'],
                                  _to_date(data['details']['first_date']),
                                  data['details']['interval'],
                                  data['details']['amount'])
        elif cf_type == "monthly":
            try:
                months = data['details']['months']
            except KeyError:
                months = [1,2,3,4,5,6,7,8,9,10,11,12]
                
            cf = MonthlyCashflow(data['name'],
                                 data['details']['day'],
                                 data['details']['amount'],
                                 months)
        elif cf_type == "composite":
            cf = CompositeCashflow(data['name'])
            for flow in data['details']['cashflows']:
                cf.add( Cashflow.from_dict(flow) )
        else:
            raise ValueError(f"{data['details']['type']} is not a supported cashflow type")
        
        try:
            cf = Limited(_to_date(data['start']),
                         data['limit'],
                         cf)
        except KeyError:
            pass
        
        try:
            cf = StartOn(_to_date(data['start']),
                         cf)
        except KeyError:
            pass
        
        try:
            cf = EndOn(_to_date(data['end']),
                       cf)
        except KeyError:
            pass
            
        return cf
        
class IntervalCashflow(Cashflow):
    def __init__(self, name, start_date, interval_days, amount):
        super().__init__(name)
        self.start_date = start_date
        self.interval_days = interval_days
        self.amount = amount
    
    def to_dict(self, d = None):
        if d is None:
            d = super().to_dict()
        if 'details' not in d:
            d['details'] = {}
        d['details']['type'] = 'interval'
        d['details']['first_date'] = _to_string(self.start_date)
        d['details']['interval'] = self.interval_days
        d['details']['amount'] = self.amount
        
        return d
        
    def flow(self,date):
        delta = date - self.start_date

        if delta.days >= 0 and (delta.days % self.interval_days ) == 0:
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
                if abs(sum+f) < maximum:
                    self.flows[d] = f
                else:
                    self.flows[d] = np.sign(sum+f)*maximum - sum
                    done = True
                sum += f
            d = d + timedelta(days=1)
    
    def to_dict(self, d = None):
        if d is None:
            d = super().to_dict()    
        d['start'] = _to_string(self.startDate)
        d['limit'] = self.maximum
        
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

    def to_dict(self, d = None):
        if d is None:
            d = super().to_dict()    
        d['start'] = _to_string(self.start_date)
        
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
    
    def to_dict(self, d = None):
        if d is None:
            d = super().to_dict()    
        d['end'] = _to_string(self.end_date)
        
        return self.cashflow.to_dict(d)
    
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
    
    def to_dict(self, d = None):
        if d is None:
            d = super().to_dict()
        if 'details' not in d:
            d['details'] = {}
        d['details']['type'] = 'monthly'
        d['details']['day'] = self.day_of_month
        d['details']['amount'] = self.amount
        d['details']['months'] = self.months
        
        return d
    
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
    
    def to_dict(self, d = None):
        if d is None:
            d = super().to_dict()
        if 'details' not in d:
            d['details'] = {}
        
        d['details']['type'] = "one-time"
        d['details']['date'] = _to_string(self.date)
        d['details']['amount'] = self.amount
        
        return d
        
    def flow(self, date):
        if self.date == date:
            return self.amount
        return 0

class CompositeCashflow(Cashflow):
    def __init__(self, name):
        super().__init__(name)
        self.cashflows = []
    
    def to_dict(self, d = None):
        if d is None:
            d = super().to_dict()
        if 'details' not in d:
            d['details'] = {}
        
        d['details']['type'] = 'composite'
        d['details']['cashflows'] = [c.to_dict() for c in self.cashflows]
        
        return d
            
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
