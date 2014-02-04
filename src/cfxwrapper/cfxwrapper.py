

from openmdao.main.api import Component
from openmdao.lib.datatypes.api import Float, Str
from openmdao.lib.components.api import ExternalCode

from os import environ
import os.path
import sys

import pickle
import cclparser
import cfxunitsinfo

class CFXWrapper(ExternalCode):
    """Base class for wrappers for ANSYS CFX.  Is only used by a generated CFX Wrapper.  See cfxwrappergenerator.GenerateCFXWrapper."""
    newdeffile = Str('', desc='a new CFX .def file to use instead of the original, can be used to apply deflections to all nodes', 
                     iotype='in')

    def __init__(self):
        super(CFXWrapper, self).__init__()
        self.inputvals = [] #empty list of floats, set in subclass execute
        self.outputvals = [] #empty list - set in execute, used in subclass execute
        self.cache = {} #empty dictionary to cache calculations        
        self.cfxpath = os.path.join(self.ansyspath, 'CFX', 'bin')
        self.cclfile = os.path.join(self.workdir, self.base + '.ccl')
        self.fullname = os.path.join(self.workdir, self.base)
        self.monfile = os.path.join(self.workdir, self.base + 'mon.txt')
        self.solvecmd = [os.path.join(self.cfxpath, 'cfx5solve.exe'),
                       '-def', self.deffile,
                       '-ccl', self.cclfile,
                       '-fullname', self.fullname]
        self.readmoncmd = [os.path.join(self.cfxpath, 'cfx5mondata.exe'),
                  '-res', self.fullname + '.res',
                  '-lastvaluesonly',
                  '-varrule', 'CATEGORY = USER POINT',
                  '-out', self.monfile]
        if self.cachefile != '':
            #import pdb; pdb.set_trace()
            if os.path.exists(self.cachefile):
                cachepickle = open(self.cachefile, 'r')
                self.cache = pickle.load(cachepickle)
                cachepickle.close()
                print 'Loaded cache ' + self.cachefile + '\n' + str(self.cache)
        else:
            self.cachefile = os.path.join(self.workdir, self.base + 'Cache.txt')
        if self.origresfile != '':
            #get the original values
            cmd = [os.path.join(self.cfxpath, 'cfx5mondata.exe'),
                  '-res', self.origresfile,
                  '-lastvaluesonly',
                   '-varrule', 'CATEGORY = USER POINT',
                  '-out', self.monfile]
            self.readmon(cmd)
            #import pdb; pdb.set_trace()
            self.cache[tuple(self.inputvals)] = tuple(self.outputvals)
            print 'Updated cache from origresfile' + self.origresfile + '\n' + str(self.cache)

            
        #Info output
        print 'Working Dir ' + self.workdir
        print 'Base File Name ' + self.base
        print 'CFX Path ' + self.cfxpath
        print 'CFX Input File ' + self.deffile
        print 'Generated CCL File ' + self.cclfile
        print 'Base for CFX Output ' + self.fullname
        print 'Solve Command ' + str(self.solvecmd)
        print 'Read Monitor Command ' + str(self.readmoncmd)
        print 'Possible Variables:'
        for i in self.possibleins:
            i.output()
        for i in self.possibleouts:
            i.output()
        print 'Cache file ' + self.cachefile

    def picklecache(self):
        picklefile = open(self.cachefile, 'w')
        pickle.dump(self.cache, picklefile)
        picklefile.close()

    def readmon(self, cmd):
        self.command = cmd
        try:
            #import pdb; pdb.set_trace()
            super(CFXWrapper, self).execute()
        except:
            print "Error in " + str(self.readmoncmd)
            print sys.exc_info()[0]
        else:
            if self.return_code == 0:
                # parse the self.monfile
                try:
                    f = open(self.monfile, 'r')
                except IOError:
                    print 'Problem opening monitor file ' + self.monfile
                    print sys.exc_info()[0]
                    self.return_code = -1
                else:
                    lines = f.readlines()
                    n = len(lines)
                    #import pdb; pdb.set_trace()
                    nameline = lines[0].replace('USER POINT,', '')
                    nameline = nameline.replace('"', '')
                    nameline = nameline.strip()
                    names = nameline.split(',')
                    valline = lines[n-1].strip()
                    vals = valline.split(',')
                    numvals = len(vals)
                    numnames = len(names)
                    print str(numnames) + ' names; ' + str(numvals) + ' vals'
                    dict = {} #empty dictionary
                    for i, l in enumerate(names):
                        if i < numvals:
                            dict[l] = vals[i]
        
                    f.close()

                    # set outputvals
                    self.outputvals = []
                    for o in self.possibleouts:
                        key = o.name
                        try:
                            valstr = dict[key]
                        except KeyError:
                            #import pdb; pdb.set_trace()
                            print 'Could not find monitor point ' + o.name + \
                                  ' in ' + self.monfile
                            print sys.exc_info()[0]
                            val = Float('nan')
                        else:
                            val, isnum = cfxunitsinfo.get_number(valstr)
                            if not isnum:
                                #import pdb; pdb.set_trace()
                                print 'Value for monitor point ' + o.name + \
                                  ' in ' + self.monfile + ' is not a number'
                                val = Float('nan')
                        self.outputvals.append(val)
                        print o.name + ' = ' + str(val)

    def execute(self):
        use_old_df = False
        if len(self.newdeffile) == 0 or self.deffile == self.newdeffile:
            use_old_df = True
            intuple = tuple(self.inputvals)
            #see if in cache
            if intuple in self.cache:
                outtuple = self.cache[intuple]
                self.outputvals = list(outtuple)
                print 'Found in cache: ' + str(intuple) + ': ' + str(outtuple)
                return
    
        #Write the ccl file
        cf = open(self.cclfile, 'w')
        for counter, i in enumerate(self.possibleins):
            if self.inputvals[counter] != i.value:
                i.cclout(cf, self.inputvals[counter])
            print i.varname + ' = ' + str(self.inputvals[counter])
        cf.close()
    
            #Execute
        if use_old_df:
            self.command = self.solvecmd
        else: #MDPL - NOT WORKING
            self.command = [os.path.join(self.cfxpath, 'cfx5solve.exe'),
                '-def', self.newdeffile,
                '-ccl', self.cclfile,
                '-initial-file', self.origresfile,
                '-fullname', self.fullname]
        
        try:
            super(CFXWrapper, self).execute()
        except:
            print "Error in " + str(self.solvecmd)
            print sys.exc_info()[0]
            self.return_code = -1
        else:
            #Get the results
            if self.return_code == 0:
                #import pdb; pdb.set_trace()
                self.readmon(self.readmoncmd)
                self.cache[tuple(self.inputvals)] = tuple(self.outputvals)
                self.picklecache()
