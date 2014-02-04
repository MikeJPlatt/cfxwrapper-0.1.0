
import logging
from os import environ
import os.path
import sys
#import pickle

import cclparser
import cfxunitsinfo

from openmdao.lib.components.api import ExternalCode
from openmdao.util.filewrap import FileParser

indent1 = '    '
indent2 = indent1 + indent1
indent3 = indent2 + indent1

class TestRunner:
    """Internal class to run CFX only to get error messages telling us the units of Monitor Points."""
    def __init__(self, deffile, workdir, base, ansyspath, logger = None):
        #import pdb; pdb.set_trace()
        self.deffile = deffile
        self.workdir = workdir
        self.base = base
        self.logger = logger
        cfxpath = os.path.join(ansyspath, 'CFX', 'bin')
        test_name = 'TEST_' + self.base
        self.cclfile = os.path.join(self.workdir, test_name + '.ccl')
        fullname = os.path.join(self.workdir, test_name)
        self.solvecmd = [os.path.join(cfxpath, 'cfx5solve.exe'),
           '-def', self.deffile,
           '-ccl', self.cclfile,
           '-fullname', fullname]
        self.outfile = os.path.join(self.workdir, test_name + '.out')
        self.units_translations = {
            #length
            'm' : 'm', 'cm': 'cm', 'mm': 'mm', 'in': 'inch', 'ft': 'ft',
            'yd': '(3.0 * ft)', 'mile': 'mi', 'dm': 'dm', 'micron': 'um',
            #mass
            'kg' : 'kg', 'g': 'g', 'lb': 'lb', 'slug': 'slug',
            'tonne': 'tn', 'oz': 'oz', 'stone': '(6.35029318 * kg)',
            #time
            's' : 's', 'min': 'min', 'hr': 'h', 'day': 'd', 'year': 'year',
            #current
            'amp': 'A',
            #temperature
            'K': 'degK', 'R': 'degR',
            #amount
            'mol': 'mol',
            #angle
            'rad': 'rad',
            #solid_angle
            'sr': 'sr'
            }
            
        self.base_units = ['m', 'kg', 's', 'amp', 'K', 'mol', 'rad', 'sr']
        self.unit_keys = {   'Angle Units': 'rad',
            'Length Units': 'm',
            'Mass Units': 'kg',
            'Solid Angle Units': 'sr',
            'Temperature Units': 'K',
            'Time Units': 's'}
        
    def do_logging(self, msg, both = False):
        if both or self.logger == None:
            print msg
        if self.logger <> None:
            self.logger.debug(msg)
            
    def set_flow_dict(self, fl):
        #import pdb; pdb.set_trace()
        self.flow_dict = {}
        fl_units = fl.units
        if len(fl_units):
            fl_unit = fl_units[0] # just use the first one
            for k, v in fl_unit.iteritems():
                if k in self.unit_keys:
                    base_unit = self.unit_keys[k]
                    self.flow_dict[base_unit] = v.replace('[','').replace(
                        ']','')
        #print str(self.flow_dict)
                

    def _expr_str(self, v):
        if int(v) == v:
            return '**' + str(int(v))
        else:
            return '**'+ str(v)
        
    def _exponents_to_string(self, d):
        dd = {}
        for k, v in d.iteritems():
            if v != 0:
                if k in self.flow_dict:
                    k = self.flow_dict[k]
                dd[k] = v
        #import pdb; pdb.set_trace()
        numterms = len(dd)
        if numterms == 0:
            s = '1'
        elif numterms == 1:
            k = dd.keys()[0]
            if k in self.units_translations:
                s = self.units_translations[k]
                exp = dd.values()[0]
                if exp != 1.0:
                    s = s + self._expr_str(exp)
            else:
                self.do_logging('ERROR: unknown unit ' + k, both = True)
                s = ''
        else:
            s = '('
            first = True
            for k, v in dd.iteritems():
                if k in self.units_translations:
                    if first:
                        first = False
                    else:
                        s = s + ' * ' 
                    s = s + self.units_translations[k]
                    if v != 1.0:
                        s = s + self._expr_str(v)
                else:
                    self.do_logging('ERROR: unknown unit ' + k, both = True)
                    s = ''
                    break
            s = s + ')'
        return s
            
    def translate(self, u):
        numerator = {}
        denominator = {}
        for b in self.base_units:
            numerator[b] = 0
            denominator[b] = 0
        #import pdb; pdb.set_trace()
        us = u.split()
        for s in us:
            if '^' in s:
                ss = s.split('^')
                unitstring = ss[0]
                exponentstring = ss[1]
                is_neg = False
                if exponentstring.startswith('-'):
                    is_neg = True
                    exponentstring = exponentstring[1:]
                exponent, isnum = cfxunitsinfo.get_number(exponentstring)
                if not isnum:
                    self.do_logging('ERROR: for unit expression ' + u +\
                          ' exponent ' + exponentstring + ' is not numeric.', both = True)
                    return ''
                if is_neg:
                    if unitstring in denominator:
                        denominator[unitstring] = \
                            denominator[unitstring] + exponent
                    else:
                        self.do_logging('ERROR: for unit expression ' + u +\
                          ' unknown unit ' + unitstring, both = True)
                        return ''
                else:
                    if unitstring in numerator:
                        numerator[unitstring] = \
                            numerator[unitstring] + exponent
                    else:
                        self.do_logging('ERROR: for unit expression ' + u +\
                          ' unknown unit ' + unitstring, both = True)
                        return ''
            else:
                if s in numerator:
                    numerator[s] = numerator[s] + 1
                else:
                    self.do_logging('ERROR: for unit expression ' + u +\
                      ' unknown unit ' + s, both = True)
                    return ''
        numstring = self._exponents_to_string(numerator)
        if numstring != '':
            denomstring = self._exponents_to_string(denominator)
            if denomstring == '':
                return ''
            elif denomstring == '1':
                return numstring
            else:
                return numstring + '/' + denomstring
        


class TestCFX(ExternalCode):
    """Run a test of CFX to get error messages related to monitor point units.
       This is very convoluted, but it seems to be the only way to get CFX to
       tell us what it knows about units."""
    def __init__(self, runner, flow, name, expr, logger = None):
        super(TestCFX, self).__init__()
        self.logger = logger
        self.runner = runner
        self.flow = flow
        self.name = name
        self.expr = expr
        self.units = ''
        
    def do_logging(self, msg, both = False):
        if both or self.logger == None:
            print msg
        if self.logger <> None:
            self.logger.debug(msg)

    def execute(self):
        f = open(self.runner.cclfile, 'w')
        f.write('FLOW: ' + self.flow.name + '\n')
        f.write('  SOLUTION UNITS:\n' +
            '    Angle Units = [rad]\n' +
            '    Length Units = [m]\n' +
            '    Mass Units = [kg]\n' +
            '    Solid Angle Units = [sr]\n' +
            '    Temperature Units = [K]\n' +
            '    Time Units = [s]\n' +
            '  END\n'
            )
        f.write('OUTPUT CONTROL:\n')
        f.write('MONITOR OBJECTS:\n')
        f.write('MONITOR POINT: TEST_' + self.name + '\n')
        f.write('Expression Value = (' + self.expr + ') + 1 + 1 [m]\n')
        f.write('Option = Expression\n')
        f.write('END\n')
        f.write('END\n')
        f.write('END\n')
        f.write('END\n')
        f.close()
        #Execute
        self.command = self.runner.solvecmd
        
        if os.path.exists(self.runner.outfile):
            os.remove(self.runner.outfile)
            
        try:
            #import pdb; pdb.set_trace()
            super(TestCFX, self).execute()
            pass
        except:
            pass #we expect an error, since we've inserted erroneous monitor points

        # parse the output file for errors about expressions
        #Inconsistent dimensions on each side of '+' operator at position 25.
        #Dimensions on left:  'lb s^-1'
        #Dimensions on right: '<dimensionless>'.
        #Error processing expression: Expression Value = (massFlow()@SEAL_inlet) + 1 + 1 [m]
        
        parser = FileParser()
        done = False
        try:
            parser.set_file(self.runner.outfile)
        except IOError:
            self.do_logging('ERROR: cannot open file ' + self.runner.outfile, both = True)
            self.dim = ''
            import pdb; pdb.set_trace()
        
        while not done:
            try:
                parser.mark_anchor(
                    'Inconsistent dimensions on each side of \'+\' operator')
                left = parser.transfer_line(1).replace(
                    'Dimensions on left:','').strip()
                right = parser.transfer_line(2).replace(
                    'Dimensions on right:','').strip()
                e = parser.transfer_line(3).replace(
                    'Error processing expression: Expression Value = (','').replace(
                    ') + 1 + 1 [m]','').strip()
                if e == self.expr:
                    self.dim = left.replace('\'', '')
                    if self.dim == '<dimensionless>':
                        self.dim = ''
                    else:
                        self.dim = self.runner.translate(self.dim)
                    self.do_logging('Units for ' + self.flow.name + ': ' + self.name + ': ' + self.dim)
                    break
                
                #MDPL finish - use the units
                #MDPL check if using ANSYS 14 elsewhere
                #MDPL The possibleinputs and possibleoutputs seems convoluted:
                #   can we simplify?
            
                parser.current_row = parser.current_row + 3
                
            except RuntimeError: # did not find key, so done
                done = True
                self.do_logging('Unknown units for ' + self.flow.name + ': ' + self.name, both = True)
                self.dim = ''

def _add_quotes(s):
    return '\'' + s + '\''

class GenerateCFXWrapper:
    """Generate the subclass of CFXWrapper specifically for the given CCL, .def, and .res files.
    
    To use:  Initialize, then call generate to create the wrapped CFX component.  
        Use that component as you would any other OpenMDAO component.
    
    *Parameters*

        origcclfile: string
            full path to .ccl file created from the ANSYS CFX Model.
            
        deffile: string
            full path to .def file created from the ANSYS CFX Model.
            
        workingdir: string
            full path to directory in which to work and store results.
            
        name: string
            unique identifying name for this wrapper.
            
        origresfile: string
            full path to .res file created from a run of the ANSYS CFX Model.
            
        cachefile: string (optional)
            if not None, full path to a previously created file that caches the results of runs of the generated wrapper. Default None.
            
        ansyspathstring: string (optional)
            key in environ to identify path to ANSYS installation.  Default 'AWP_ROOT145'
            
        logger: logging.Logger (optional)
            an existing Logger to use for output.  If None, output will go to stdout.  Default None.
            
        parser: cclparser.CCLParser (optional)
            an existing CCLParser for the origcclfile. Used only for testing. If None, parser is created. Default None.
    """
    def __init__(self, origcclfile, deffile, workingdir, name = '',
                 origresfile = '', cachefile = '', ansyspathstring = 'AWP_ROOT145', logger = None, parser = None):
        self.logger = logger
        self.cclfile = origcclfile
        self.deffile = deffile
        self.origresfile = origresfile
        self.name = name
        head, tail = os.path.split(self.cclfile)
        if len(workingdir) == 0:
            workingdir = head
        self.workdir = workingdir
        if name == '':
            self.base, ext  = os.path.splitext(tail)
        else:
            self.base = name
        self.cachefile = cachefile
        self.componentfile = os.path.join(self.workdir, self.base +'.py')
        self.inputs = [] #empty list
        self.outputs = [] #empty list

        if parser == None:
            self.parser = cclparser.CCLParser(self.cclfile)
            self.need_parse = True
        else:
            self.parser = parser
            self.need_parse = False
        self.ansyspath = environ[ansyspathstring].replace('\\', '/')
        self.do_logging('Generating ' + self.componentfile + ' from ' + self.cclfile, both = True)
        
    def do_logging(self, msg, both = False):
        if both or self.logger == None:
            print msg
        if self.logger <> None:
            self.logger.debug(msg)
  
    def set_inputvals_str(self):
        """ generate string that sets the super class inputvals"""
        s = 'self.inputvals = ['
        first = True
        for i in self.inputs:
            if first: first = False
            else: s = s + ', '
            s = s + 'self.' + i.varname
        s = s + ']\n' 
        return s

    def _getnumerics(self, d, currpath, use_simple_name = False):
        """Recursively get items in the dictionary that have numeric values.
           Items may optionally have a units designation.
           Returns a list of PossibleInput"""
        depth = len(currpath)
        for k, v in d.iteritems():
            if isinstance(v, dict):
                currpath[depth:] = []
                currpath.append(k)
                self._getnumerics(v, currpath[0:len(currpath)], use_simple_name)
            else:
                #see if v is numeric, possibly with [units] at the end
                words = v.split('[')
                num, isnum = cfxunitsinfo.get_number(words[0])
                if isnum:
                    units = ''
                    if len(words) > 1:
                        words2 = words[1].split(']')
                        units = words2[0]
                    if use_simple_name:
                        varname = k
                    else:
                        varname = ''
                    self.inputs.append(cfxunitsinfo.PossibleInput(currpath, k, num, units, varname = varname))
                
    def _get_inputs(self, flow):
        for d in flow.domains:
            currpath = ['FLOW: ' + flow.name, 'DOMAIN: ' + d.name]
            todo = [d.inlets, d.outlets, d.openings, d.interfaces, d.walls,
                    d.symmetries]
            for t in todo:
                for b in t:
                    currpath[2:] = []
                    currpath.append('BOUNDARY: ' + b.name)
                    self._getnumerics(b.attributes, currpath[0:len(currpath)])

    def _gen_init(self, f, classname, varnamestring):
        f.write('\n')
        f.write(indent1 + 'def __init__(self):\n')
        f.write(indent2 + varnamestring)
        f.write(indent2 + self.set_inputvals_str())
        f.write(indent2 + 'self.possibleins = []\n')
        for i in self.inputs:
            f.write(indent2 +
                'self.possibleins.append(cfxunitsinfo.PossibleInput(' +
                str(i.path) + ', ' +
                _add_quotes(i.name) + ','  +
                _add_quotes(str(i.value)) + ', ' +
                _add_quotes(i.units) + ', ' +
                _add_quotes(i.varname) + '))\n')
        f.write(indent2 + 'self.possibleouts = []\n')
        for i in self.outputs:
            f.write(indent2 +
                'self.possibleouts.append(cfxunitsinfo.MonitorPointOutput(' +
                _add_quotes(i.flowname) + ', ' +
                _add_quotes(i.name) + ', ' +
                _add_quotes(i.expression_value) + ', ' +
                _add_quotes(i.option) + ', ' +
                _add_quotes(i.units) + ', ' +
                _add_quotes(i.varname) + '))\n')
        f.write(indent2 + 'self.workdir = ' + _add_quotes(self.workdir) + '\n')
        f.write(indent2 + 'self.base = ' + _add_quotes(self.base) + '\n')
        f.write(indent2 + 'self.origresfile = ' +
            _add_quotes(self.origresfile) + '\n')
        f.write(indent2 + 'self.deffile = ' + _add_quotes(self.deffile) + '\n')
        f.write(indent2 + 'self.cachefile = ' + _add_quotes(self.cachefile) + '\n')
        f.write(indent2 + 'self.ansyspath  = ' + _add_quotes(self.ansyspath) + '\n')
        f.write(indent2 + 'super(' + classname + ',self).__init__()\n')
        
                
    def generate(self, dump = False):
        """Generate the wrapper."""
        triplequote = '"""'
        if self.need_parse:
            self.parser.parse()
        if dump: 
            self.do_logging(self.parser.output())
        self._getnumerics(self.parser.expressions, ['LIBRARY:', 'CEL:', 'EXPRESSIONS:'], use_simple_name = True)
        tr = TestRunner(self.deffile, self.workdir, self.base, self.ansyspath, logger = self.logger)
        for fl in self.parser.flows:
            self._get_inputs(fl)
            tr.set_flow_dict(fl)
            for k, v in fl.monitorpoints.iteritems():
                option = v['Option']
                if option == 'Expression':
                    expr = v['Expression Value']
                    tester = TestCFX(tr, fl, k, expr, logger = self.logger)
                    tester.execute()
                    self.outputs.append(cfxunitsinfo.MonitorPointOutput(
                        fl.name, k, expr, option, tester.dim))
        self.do_logging('INPUTS:')
        for i in self.inputs: 
            self.do_logging(i.output())
        self.do_logging('OUTPUTS:')
        for i in self.outputs: 
            self.do_logging(i.output())

        classname = self.base + 'Wrapper'

        f = open(self.componentfile, 'w')
        f.write('#OpenMDOA Wrapper for ANSYS CFX generated from ' +\
                self.cclfile +'\n\n')
        f.write('from openmdao.main.api import Component\n')
        f.write('from openmdao.lib.datatypes.api import Float\n')
        f.write('from openmdao.lib.components.api import ExternalCode\n')
        f.write('import sys\n')
        f.write('sys.path.insert(0, \'' + sys.path[0] + '\')\n')
        f.write('import cfxunitsinfo\n')
        f.write('from cfxwrapper.cfxwrapper import CFXWrapper\n\n')
        f.write('class ' + classname + '(CFXWrapper):\n')
        f.write(indent1 + triplequote + \
                'Generated OpenMDAO wrapper for the ANSYS CFX Component in\n' +\
                indent1 + self.cclfile + '.' + triplequote + '\n\n')

        #generate input and output variables from self.inputs, self.outputs
        varnamestring = 'self.varnames = [ '
        f.write(indent1 + '#input and output variables\n')
        for i in self.inputs:
            f.write(indent1 + i.varname + ' = Float(' + str(i.value) + 
                    ', iotype=\'in\',\n')
            u = i.units
            if len(u):
                try:
                    us = cfxunitsinfo.translate(u)
                    f.write(indent2 + 'units=\'' + us + '\',\n')
                except:
                    pass #ignore problems with units
            f.write(indent2 +  'desc=\'' + i.info(True) + '\')\n')
            varnamestring += '\'' + i.varname + '\', '
        for i in self.outputs:
            f.write(indent1 + i.varname + ' = Float(0.0, iotype=\'out\',\n')
            u = i.units
            if len(u):
                f.write(indent2 + 'units=\'' + u + '\',\n')
            f.write(indent2 +  'desc=\'' + i.info(True) + '\')\n')
            varnamestring += '\'' + i.varname + '\', '
        varnamestring += ']\n'
        # init
        self._gen_init(f, classname, varnamestring)
        # execute
        f.write('\n')
        f.write(indent1 + 'def execute(self):\n')
        f.write(indent2 + self.set_inputvals_str())
        f.write(indent2 + 'super(' + classname + ', self).execute()\n')
        f.write(indent2 + 'if self.return_code == 0:\n')
        if len(self.outputs) == 0:
            f.write(indent3 + 'pass\n')
        else:
            for i, o in enumerate(self.outputs):
                s1 = 'self.' + o.varname
                s2 = 'self.outputvals[' + str(i) + ']'
                f.write(indent3 + s1 + ' = ' + s2 + '\n')
                f.write(indent3 + 'print \'' + s1 + '\' + \' = \'  + str(' + s2 +
                    ')\n')
        f.close()
        return self.componentfile, classname

if __name__ == "__main__": # pragma: no cover
    import os
    import sys
    base = 'C:/Projects/MUTT/MUTT_PhaseII/MSI_FSI_Examples/MSI_Pump_Case/Case_5'
    outdir = os.path.join(base, 'Temp')
    modelsdir = os.path.join(base, 'CFX')
    nm = 'MSI_pumpLoop_Impeller'
    
    if True: #not os.path.exists(os.path.join(outdir, 'MSI_pumpLoop_Impeller.py')):
        gen = GenerateCFXWrapper(os.path.join(modelsdir, nm + '.ccl'),
                                 os.path.join(modelsdir, nm + '.def'),
                                 outdir, nm,
                                 os.path.join(modelsdir, nm + '.res'),
                                 os.path.join(outdir, nm + '.txt') )
        gen.generate(True)
    
    sys.path.append(outdir)
    from MSI_pumpLoop_Impeller import MSI_pumpLoop_ImpellerWrapper
    mpi = MSI_pumpLoop_ImpellerWrapper()
    mpi.ptin = 3.0
    mpi.execute()

