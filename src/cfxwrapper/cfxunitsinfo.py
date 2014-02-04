import os

"""Translate a units string from CFX to OpenMDAO. Also info about CFX I/0."""


def get_number(s):
    try:
        answer = float(s)
        return answer, True
    except ValueError:
        return 0, False

def make_unique_name(currpath, n):
    s = ''
    for p in currpath:
        spl = p.split(':')
        if len(spl) > 1:
            s = s + spl[1].strip() + '_'
        else:
            s = s + spl[0].strip() + '_'
    s = s + n
    s = s.replace(' ', '_')
    return s

class PossibleInput:
    """Information about a possible input variable in the CFX Flow."""
    path = [] #empty list - will contain full path to the item
    name = ''
    value = 0
    units = ''
    varname = ''
    def __init__(self, p, n, v, u, varname = ''):
        self.path = p[0:len(p)]
        self.name = n
        self.value = v
        self.units = u
        if varname == '':
            self.varname = make_unique_name(self.path, self.name)
        else:
            self.varname = varname
    def info(self, stripquotes = False):
        s = str(self.path) + ': ' + self.name + ' = ' + str(self.value) + \
               ' [' + self.units + ']'
        if stripquotes:
            return s.replace('\'', '')
        return s
    def output(self):
        return self.varname + ' IS ' + self.info()
    def cclout(self, f, val):
        ends = ''
        for p in self.path:
            f.write(p + '\n')
            ends = ends + 'END\n'
        f.write(self.name + ' = ' + format(val, '.16g') + ' [' + \
                self.units + ']\n')
        f.write(ends)

class MonitorPointOutput:
    """Information about a monitor point used as an output variable."""
    def __init__(self, flowname, name, expr, option, units, varname = ''):
        self.flowname = flowname
        self.name = name
        self.expression_value = expr
        self.option = option
        self.units = units
        if varname == '':
            s = flowname + '__' + name
            self.varname =  s.replace(' ', '_')
        else:
            self.varname = varname
    def info(self, stripquotes = False): 
        s = self.flowname + ': ' + self.name + ' = ' \
               + str(self.expression_value) + ' ' + self.option
        if stripquotes:
            return s.replace('\'', '')
        return s
    def output(self):
        return self.varname + ' IS ' + self.info() + ' [' + self.units + ']'

#Basic translations - based on list in CFX documentation
# // CFX-Pre User's Guide // 19. Units and Dimensions // 19.2. Using Units in CFX-Pre // 19.2.1. Units Commonly Used in CFX
basics = {'mile': 'mi', 'foot': 'ft', #length
    'K': 'degK', 'C': 'degC', 'R': 'degR', 'F': 'degF', #temperature
    'litre': 'l', 'gallon': 'galUK', 'gallonUSliquid': 'galUS', #volume
    'tonne': 'tn', 'lb': 'lbm', #mass
    'dyne': 'dyn', #force
    'poise': 'g * cm**-1 / s', # dynamic viscosity
    'hour': 'h', 'hr': 'h', #time
    'BTU': 'Btu', #energy
    'radian': 'rad', 'degree': 'deg' #angle
    }
prefixes = {'nano': 'n', 'micro': 'u', 'centi': 'c', 'kilo': 'k',
    'milli': 'm', 'mega': 'M', 'giga': 'G'}

def translate(s):
    answer = ''
    parts = s.split()
    lastindex = len(parts) - 1
    #import pdb; pdb.set_trace()
    for i, p in enumerate(parts):
        newp = p
        #look for long-form prefix
        for prefix, val in prefixes.iteritems():
            if newp.startswith(prefix):
                newp = newp.replace(prefix, val, 1)
                break
        #look for basic translation:
        for k, v in basics.iteritems():
            newp = newp.replace(k, v)
        #replace ^ with **
        newp = newp.replace('^', '**')
        answer = answer +  newp
        if (i != lastindex):
            answer = answer + ' * '
    return answer


        

if __name__ == "__main__": # pragma: no cover

    import openmdao.units.units
    #import pdb; pdb.set_trace()

    
    for k, v in openmdao.units.units._unit_lib.unit_table.iteritems():
        f.write(k + ': ' + str(v) + '\n')
    f.close()
    s = 's^-1'
    t = translate(s)
    #import pdb; pdb.set_trace()
    u = openmdao.units.units._find_unit(t)
    print s + ' = ' + t + ': ' + repr(u)
    
    s = 'm^-1 s^-1'
    t = translate(s)
    import pdb; pdb.set_trace()
    u = openmdao.units.units._find_unit(t)
    print s + ' = ' + t + ': ' + repr(u)
    s = 'centipoise'
    t = translate(s)
    import pdb; pdb.set_trace()
    u = openmdao.units.units._find_unit(t)
    print s + ' = ' + t + ': ' + repr(u)

    for s in ['kg', 'mile hr^-1', 'litre s^-1', 'tonne s^-1', 'centipoise',
              'W m^-1 K^-1', 'gallonUSliquid', 'kilog', 'nanos']:
        t = translate(s)
        u = openmdao.units.units._find_unit(t)
        print s + ' = ' + t + ': ' + repr(u)
