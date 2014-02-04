from openmdao.util.filewrap import FileParser

import pprint

pp = pprint.PrettyPrinter(indent=4)

class StringArrayParser(FileParser):
    """Like FileParser for an array of data strings.
    Has methods for finding the *end_string* that matches an anchor."""
    end_string = 'END'
    start_string = ':'
    exclude_string = '=' # when matching start and end,
                         # ignore lines containing exclude_string
    def __init__(self, data_array, filename=''):
        super(StringArrayParser, self).__init__()
        #import pdb; pdb.set_trace()
        if filename == '':
            self.data = data_array
        else:
            self.set_file(filename)
            self.preprocess()
        self.set_delimiters('= \t') #so we can split the key, value pairs

    def strip_comments(self, line, start=0):
        """Strip CCL comments (starting with #) from a line."""
        index = line.find('#', start)
        if index < 0: #no comment
            return line
        elif index == 0: #whole line is a comment
            return ''
        else:
            if line[index-1] != '\\': # the # is not escaped
                return line[:index]
            else:
                return strip_comments(line, index + 1)

    def preprocess(self):
        """Handles continuation lines ending with \
           and comments starting with non-escaped #.
           Removes blank lines and trailing white space.
        """
        n = len(self.data) - 1
        i = n
        while i >= 0:
            line = self.data[i].rstrip()
            line = self.strip_comments(line)
            if len(line.strip()) == 0:
                del self.data[i]
            else:
                if i < n and line[len(line)-1] == '\\':
                    #don't process a continuation on the last line
                    #import pdb; pdb.set_trace()
                    line = line[:-1] + self.data[i + 1].lstrip()
                    del self.data[i + 1]
                self.data[i] = line.rstrip()
            i -= 1
        #import pdb; pdb.set_trace()

            
    def set_end_string(e):
        """Sets the end string to use for matching."""
        self.end_string = e

    def set_start_string(e):
        """Sets the start string to use for matching."""
        self.start_string = e
    def set_exclude_string(e):
        """Sets the exclude string to use for matching."""
        self.exclude_string = e
   
    def find_end(self):
        """Finds end row in data that matches *current_row*.
        
        Does not change the anchor.
        
        Returns -1 if not found."""
        
        endrow = -1
        depth = 1
        i = self.current_row + 1
        #import pdb; pdb.set_trace()
        while i < len(self.data):
            line = self.data[i]
            if line.find(self.exclude_string) == -1: # don't ignore line    
                if line.find(self.start_string) >= 0:
                    depth += 1
                    #print str(depth) + '[' + line + ']'
                elif line.find(self.end_string) >= 0:
                    depth -= 1
                    #print str(depth) + '[' + line + ']'
                if depth == 0:
                    endrow = i
                    break
            i += 1
        #import pdb; pdb.set_trace()
        return endrow

    def mark_anchor_withs(self, anchor, sr = 0):
        if sr == 0:
            self.mark_anchor(anchor)
        else:
            done = False
            #import pdb; pdb.set_trace()
            while not done:
                self.mark_anchor(anchor)
                if self.current_row >= sr:
                    done = True
            
    def find_range(self, anchor, sr = 0):
        """Finds the start and end rows in data for the entity that starts with *anchor*.
        
        Leaves the anchor set at the line that contains ``anchor``.
        
        Returns startrow and endrow. Returns -1 for both if anchor is not found."""
        startrow = -1
        endrow = -1
        try:
            self.mark_anchor_withs(anchor, sr)
        except RuntimeError: #anchor not found
            pass
        else:
            startrow = self.current_row
            endrow = self.find_end()
        finally:
            return startrow, endrow
        
def do_logging(logger, msg, both = False):
    if both or logger == None:
        print msg
    if logger <> None:
        logger.debug(msg)

class CCLEntityParser(StringArrayParser):
    """Puts ANSYS CFX CCL information into a dictionary structure.

        Lines containing ''='' will be put into the top-level dictionary.
        
        Lines containing '':'' signify the start of a sub-dictionary."""
    dictionary = {} #empty dictionary
    def __init__(self, data_array, logger = None):
        super(CCLEntityParser, self).__init__(data_array, '')
        self.dictionary = {} #empty dictionary
        self.logger = logger

    def parse(self, depth = 0):
        "Fill the dictionary."
        #print 'Parse depth ' + str(depth) + ' data: '
        #for s in self.data: print s
        #import pdb; pdb.set_trace()
        n = len(self.data)
        i = 1
        while i < n:
            self.current_row = i
            line = self.data[i]
            words = line.split('=')
            if len(words) > 1: #put into dictionary
                key = words[0].strip()
                value = words[1].strip()
                self.dictionary[key] = value
                #print 'Parse depth ' + str(depth) + ' key ' + key + ' value ' + value
                i = i + 1
            else:
                index = line.find(':')
                if index > 0:
                    anchor = line.strip()
                    #import pdb; pdb.set_trace()
                    endrow = self.find_end()
                    if endrow == -1:
                        do_logging(self.logger, 'Could not find end matching ' + anchor, both = True)
                        break
                    #print 'Parse depth ' +str(depth) + ' anchor ' + anchor
                    #import pdb; pdb.set_trace()
                    subparser = CCLEntityParser(self.data[i:endrow])
                    subparser.parse(depth+1)
                    
                    self.dictionary[anchor] = subparser.dictionary
                    i = endrow + 1
                else:
                    do_logging(self.logger, 'Unexpected line ' + line + ' depth ' + depth, both = True)
                    import pdb; pdb.set_trace()
                    i = i + 1

class Boundary: 
    """Holds info about a CFX Boundary."""
    attributes = {} # empty dictionary
    name = ''
    type = ''
    def __init__(self, n, d):
        #import pdb; pdb.set_trace()
        self.name = n
        self.attributes = d
        if 'Boundary Type' in d:
            self.type = d['Boundary Type']
    def output(self):
        s = 'Boundary: ' + self.type + ': ' + self.name + ' attributes: '
        s += pp.pformat(self.attributes)
        return s
        
    def get_location_names(self, loc_dict):
        if 'Location' in self.attributes:
            loc_dict[self.name] = self.attributes['Location']
        else:
            loc_dict[self.name] = ''
        

class Domain:
    """Holds info about a CFX Domain."""
    name = ''
    domaintype = ''
    location = ''
    inlets = [] #empty list
    outlets = [] #empty list
    openings = [] #empty list
    interfaces = [] #empty list
    walls = [] #empty list
    symmetries = [] #empty list
    def __init__(self, n):
        self.name = n
        self.inlets = [] #empty list
        self.outlets = [] #empty list
        self.openings = [] #empty list
        self.interfaces = [] #empty list
        self.walls = [] #empty list
        self.symmetries = [] #empty list
    def output(self):
        s =  'Domain: ' + self.name + " type: " + self.domaintype + ' location: ' + self.location
        s += '\nInlets:'
        for x in self.inlets: s += x.output()
        s += '\nOutlets:'
        for x in self.outlets: s += x.output()
        s += '\nOpenings:'
        for x in self.openings: s += x.output()
        s += '\nInterfaces:'
        for x in self.interfaces: s += x.output()
        s += '\nWalls:'
        for x in self.walls: s += x.output()
        s += '\nSymmetries:'
        for x in self.symmetries: s += x.output()
        s += '\nEnd of Domain ' + self.name + '\n'
        return s
        
    def get_location_names(self, d_loc_dict, b_loc_dict):
        d_loc_dict[self.name] = self.location
        for x in self.inlets:
            isinstance(x, Boundary)
            x.get_location_names(b_loc_dict)   
        for x in self.outlets:
            isinstance(x, Boundary)
            x.get_location_names(b_loc_dict)   
        for x in self.openings:
            isinstance(x, Boundary)
            x.get_location_names(b_loc_dict)   
        for x in self.interfaces:
            isinstance(x, Boundary)
            x.get_location_names(b_loc_dict)   
        for x in self.walls:
            isinstance(x, Boundary)
            x.get_location_names(b_loc_dict)   
        for x in self.symmetries:
            isinstance(x, Boundary)
            x.get_location_names(b_loc_dict)   
class Flow:
    """Holds info about a CFX Flow entity."""
    name = ''
    units = [] #empty list
    domains = [] #empty list
    monitorpoints = {} #empty dictionary
    def __init__(self, n):
        self.name = n
        self.units = []
        self.domains = []
        self.monitorpoints = {} #empty dictionary
    def output(self):
        s = 'Flow: ' + self.name
        s += '\nUnits:'
        s += pp.pformat(self.units)
        s += '\nDomains:'
        for d in self.domains:
            s += d.output()
            s += '\n'
        s += 'Monitor Points:'
        s += pp.pformat(self.monitorpoints)
        s += 'End of Flow ' + self.name
        return s
        
    def get_location_names(self, d_loc_dict, b_loc_dict):
        for d in self.domains:
            isinstance(d, Domain)
            d.get_location_names(d_loc_dict, b_loc_dict)
            
    def get_length_units(self, units):
        for u in self.units:
            if 'Length Units' in u:
                s = u['Length Units']
                units.add(s.lstrip('[').rstrip(']'))

class CCLParser():
    """A Parser for an ANSYS CFX CCL file.
       
        The CCL file is generated by ANSYS CFX-Pre: File->Export->CCL.
          
        CCLParser looks for definitions of ANSYS CFX entities to expose
        to the wrapper.

        See CFX Reference Guide Section 12.1 for CCL syntax
    """
    expressions = {} # empty dictionary
    flows = [] #empty list
    location_dictionary = {} #empty dictionary
    units = set() #empty set
    
    def __init__(self, filename, logger = None):
        self.parser = StringArrayParser([], filename)
        self.flows = [] #empty list
        self.expressions = {} # empty dictionary
        self.domain_location_dictionary = {} #empty dictionary
        self.boundary_location_dictionary = {} #empty dictionary
        self.units = set() #empty set
        self.logger = logger
        
    def getlibrary_parser(self):
        """Get a parser for just the LIBRARY section of the CCL file."""
        self.parser.reset_anchor()
        anchor = 'LIBRARY:'
        startrow, endrow = self.parser.find_range(anchor)
        if startrow == -1 or endrow == -1:
            return False
        else:
            self.library_parser = StringArrayParser(self.parser.data[startrow:endrow])
            return True

    def getexpressions(self):
        """Get expressions defined in LIBRARY:CEL:EXPRESSIONS:"""
        self.library_parser.reset_anchor()
        try:
            startrow, endrow = self.library_parser.find_range('CEL:')
            if startrow == -1 or endrow == -1: 
                return False
            cel_parser = StringArrayParser(
                self.library_parser.data[startrow:endrow])
            try:
                startrow, endrow = cel_parser.find_range('EXPRESSIONS:')
                if startrow == -1 or endrow == -1:
                    return False
                expr_parser = CCLEntityParser(cel_parser.data[startrow:endrow])
                expr_parser.parse()
                self.expressions = expr_parser.dictionary.copy()
                return True
            except RuntimeError: #anchor not found
                return False
        except RuntimeError: #anchor not found
            return False

    def getflow_parser(self, sr):
        """Get a parser for just the FLOW section of the CCL file."""
        anchor = 'FLOW:'
        startrow, endrow = self.parser.find_range(anchor, sr)
        if startrow == -1 or endrow == -1:
            return '', -1
        else:
            self.flow_parser = StringArrayParser(self.parser.data[startrow:endrow])
            name = self.getname('FLOW:', self.flow_parser.data[0])
            return name, endrow
       
    def getunits(self, flow):
        """Get SOLUTION UNITS defined in the flow."""
        try:
            self.flow_parser.reset_anchor()
            startrow, endrow = self.flow_parser.find_range(
                'SOLUTION UNITS:')
            if startrow == -1 or endrow == -1: 
                return
            #import pdb; pdb.set_trace()
            units_parser = CCLEntityParser(
                self.flow_parser.data[startrow:endrow])
            units_parser.parse()
            flow.units.append(units_parser.dictionary)
        except RuntimeError: #anchor not found
            return
        #end of getunits

    def getname(self, anchor, line):
        """Get the name defined on the line after *anchor*."""
        index = line.find(anchor)
        if (index >= 0):
            n = len(anchor) + index
            name = line[n:].strip()
        else:
            name = line.strip()
        return name

    def getdomains(self, flow):
        """Get information about the Domains defined in the flow.
           In particular, get Boundary and Monitor Point information.
        """
        i = 1
        sr = 0
        while True:
            try:
                self.flow_parser.reset_anchor()
                startrow, endrow = self.flow_parser.find_range('DOMAIN:', sr)
                if startrow == -1 or endrow == -1: 
                    break
                #import pdb; pdb.set_trace()
                sr = endrow
                domain_parser = StringArrayParser(self.flow_parser.data[startrow:endrow])
                
                #get the domain name from the first line
                name = self.getname('DOMAIN:', domain_parser.data[0])
                dmn = Domain(name)
                
                #get the Domain Type
                #import pdb; pdb.set_trace()
                dmn.domaintype = domain_parser.transfer_keyvar('Domain Type', 1)
                dmn.location = domain_parser.transfer_keyvar('Location', 1)
            
                #print 'Domain ' + dmn.name + ' ' + dmn.domaintype + ' startrow ' + str(domain_startrow) + \
                    #' endrow ' + str(domain_endrow)
                
                # look for boundaries
                anchor = "BOUNDARY:"
                #n = len(anchor)
                while True:
                    #import pdb; pdb.set_trace()
                    startrow, endrow = domain_parser.find_range(anchor)
                    if startrow == -1 or endrow == -1: 
                        break
                    boundary_parser = CCLEntityParser(domain_parser.data[startrow:endrow])
                    #get the boundary name from the first line
                    #import pdb; pdb.set_trace()
                    #line = boundary_parser.data[boundary_parser.current_row].strip()
                    name = self.getname(anchor, boundary_parser.data[0])
                    boundary_parser.parse()
                    #import pdb; pdb.set_trace()
                    b = Boundary(name, boundary_parser.dictionary)
                    btype = b.type
                    #print 'Boundary ' + name + ' ' + btype + ' startrow ' + str(boundary_startrow) + \
                        #' endrow ' + str(boundary_endrow)
                    if btype == 'INLET':
                        dmn.inlets.append(b)
                    elif btype == 'OUTLET':
                        dmn.outlets.append(b)
                    elif btype == 'OPENING':
                        dmn.openings.append(b)
                    elif btype == 'WALL':
                        dmn.walls.append(b)
                    elif btype == 'INTERFACE':
                        dmn.interfaces.append(b)
                    elif btype == 'SYMMETRY':
                        dmn.symmetries.append(b)
                    else:
                        do_logging(self.logger, 'Domain ' + dmn.name + ': Boundary ' + name + ': unknown type ' + btype, both = True)
                
                flow.domains.append(dmn)
                i = i + 1
            except RuntimeError: #anchor not found
                break
               
    def getmonitorpoints(self, flow):
        """Get monitor points defined in FLOW: OUTPUT CONTROL: MONITOR OBJECTS:"""
        self.flow_parser.reset_anchor()
        startrow, endrow = self.flow_parser.find_range('OUTPUT CONTROL:')
        if startrow == -1 or endrow == -1:
            return
        oc_parser = StringArrayParser(self.flow_parser.data[startrow:endrow])
        startrow, endrow = oc_parser.find_range('MONITOR OBJECTS:')
        if startrow == -1 or endrow == -1:
            return
        mo_parser = StringArrayParser(oc_parser.data[startrow:endrow])
        for i, l in enumerate(mo_parser.data):
            do_logging(self.logger, str(i) + ', ' + l)

        anchor = "MONITOR POINT:"
        n = len(anchor)
        sr = 0
        while True:
            try:
                mo_parser.reset_anchor()
                startrow, endrow = mo_parser.find_range(anchor, sr)
                if startrow == -1 or endrow == -1: 
                    break
                sr = endrow
                monitorpoints_parser = StringArrayParser(mo_parser.data[startrow:endrow])
                #import pdb; pdb.set_trace()
                #get the monitor name from the marked line
                line = monitorpoints_parser.data[0].strip()
                name = line[n:].strip()
                #if name == 'MonAmpere': import pdb; pdb.set_trace()
                d = {} #empty dictionary
                keys = ('Expression Value', 'Option')
                for line in monitorpoints_parser.data[1:]:  # look at the remaining lines for keys
                    for k in keys:
                        if k in line:
                            s = line.replace(k, '')
                            s = s.replace('=', '')
                            d[k] = s.strip()                        
                #for i, k in enumerate(keys, 1):
                    #monitorpoints_parser.reset_anchor()
                    #line = monitorpoints_parser.transfer_line(i)
                    #if k in line:
                        #s = line.replace(k, '')
                        #s = s.replace('=', '')
                        #d[k] = s.strip()
                flow.monitorpoints[name] = d
            except RuntimeError: #anchor not found
                break
       #end of getmonitorpoints
            
    def output(self):
        s = 'EXPRESSIONS:\n'
        for k, v in self.expressions.iteritems():
            s += k + ': ' + v + '\n'
        
        for f in self.flows:
            s += f.output()
        return s
            
    def parse(self, do_location_dictionary = False, do_length_units = False, debug = False):
        ''"Parse the CCL File."""
        #Parse LIBRARY: section (just expressions for now)
        if self.getlibrary_parser():
            self.getexpressions()
        
        #Parse FLOW: sections
        self.parser.reset_anchor()
        sr = 0
        self.flows = [] #emptylist
        while True:
            #import pdb; pdb.set_trace()
            flowname, endrow = self.getflow_parser(sr)
            if flowname == '':
                break
            flow = Flow(flowname)
            self.getunits(flow)
            self.getdomains(flow)
            self.getmonitorpoints(flow)
            self.flows.append(flow)
            sr = endrow
        if do_location_dictionary:
            self.get_location_dictionary(debug)
        if do_length_units:
            self.get_length_units(debug)
            
    def get_location_dictionary(self, debug = False):
        for f in self.flows:
            isinstance(f, Flow)
            f.get_location_names(self.domain_location_dictionary, self.boundary_location_dictionary)
        if debug: 
            do_logging(self.logger, 'Domain Location Dictionary:')
            do_logging(self.logger, pp.pformat(self.domain_location_dictionary))
            do_logging(self.logger, 'Boundary Location Dictionary:')
            do_logging(self.logger, pp.pformat(self.boundary_location_dictionary)  )          
    
    def get_length_units(self, debug = False):
        for f in self.flows:
            f.get_length_units(self.units)
        if debug:
            do_logging(self.logger, 'Units:' )
            do_logging(self.logger, pp.pformat(self.units))
       
if __name__ == "__main__": # pragma: no cover
    
    import os

    base = 'C:/Projects/MUTT/MUTT_PhaseII/'
    filename = 'MSI_FSI_Examples/MSI_Pump_Case/Case_5/CFX/MSI_pumpLoop_Impeller.ccl'
    cclp1 = CCLParser(os.path.join(base, filename))
    cclp1.parse()
    print cclp1.output()
    print 'End of parse2'
