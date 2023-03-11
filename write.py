import json

def get_modifiers(data):
    start = data.get('start',None)
    end = data.get('end',None)
    limit = data.get('limit', None)
    
    modifiers = []

    if start is not None:
        modifiers.append(f"starting on {start}")
    
    if end is not None:
        modifiers.append(f"ending on {end}")
    
    if limit is not None:
        modifiers.append(f"maximum {limit}")
    
    return modifiers

def write_one_time(data, indent=""):
    
    tokens = []
    
    name = data.get('name', None)
    
    if name is not None:
        tokens.append(f"{name}:")
    
    tokens.append(data['details']['amount'])
    tokens.append("on")
    tokens.append(data['details']['date'])
    
    return indent + " ".join([str(t) for t in tokens])

def write_interval(data, indent=""):    
    tokens = []
    
    name = data.get('name', None)
    
    if name is not None:
        tokens.append(f"{name}:")
    
    tokens.append(data['details']['amount'])
    tokens.append("every")
    tokens.append(data['details']['interval'])
    tokens.append("days")
    tokens.append("counting from")
    tokens.append(data['details']['first_date'])
    tokens.extend(get_modifiers(data))

    return indent + " ".join([str(t) for t in tokens])
    
def write_monthly(data, indent=""):
    tokens = []
    months = ["Jan", "Feb", "Mar", "Apr", "May", "June", "July", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    name = data.get('name', None)
    
    if name is not None:
        tokens.append(f"{name}:")
    
    tokens.append( data['details'].get("amount", 0))
    tokens.append( "on day")
    tokens.append( data['details'].get("day", 1))
    if 'months' in data['details'].keys():
        tokens.append("in")
        tokens.append(", ".join([months[i-1] for i in data['details']['months']]))
    tokens.extend(get_modifiers(data))

    return indent + " ".join([str(t) for t in tokens])

def write_composite(data, indent=""):
    lines = []
    lines.append(f"{indent}{data['name']} (")
    lines.extend(serializers[c['details']['type']](c, indent + "    ") for c in data['details']['cashflows'])
    lines.append(f"{indent})")

    return "\n".join(lines)

serializers = {
    'composite': write_composite,
    'interval': write_interval,
    'monthly': write_monthly,
    'one-time': write_one_time
}

if __name__ == "__main__":
    file = r"cashflows.json"
    
    with open(file) as f:
        cashflows = json.load(f)
    
    if type(cashflows) is not list:
        print("Input json file must be a list at the top level")
        exit(1)
    
    for c in cashflows:
        try:
            flowtype = c['details'].get('type', "no type specified")
            print(serializers[flowtype](c))
        except KeyError as ke:
            print(f"Unknown type: '{flowtype}'")