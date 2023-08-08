import inspect
import linecache
import ast
import sys
import io
from pypar.basics.FunctionCostAnalyzer import FunctionCostAnalyzer
from pypar.basics.CostAnalyzer import CostAnalyzer
from pypar.basics.ReadWriteAnalyzer import ReadWriteAnalyzer
from pypar.basics.SequenceExtractor import SequenceExtractor
from pypar.basics.DependenceAnalyzer import DependenceAnalyzer
from pypar.basics.SequenceParallelizer import SequenceParallelizer
from pypar.basics.LoopExtractor import LoopExtractor
from pypar.basics.LoopParallelizer import LoopParallelizer
from pypar.basics.CompExtractor import CompExtractor
from pypar.basics.CompParallelizer import CompParallelizer
from pypar.basics.ExprExtractor import ExprExtractor


from pypar.basics.utils import getstr

def getSourceCode(funcobj):
    file = funcobj.__code__.co_filename
    lineno = funcobj.__code__.co_firstlineno
    lines = linecache.getlines(file)
    nlines = inspect.getblock(lines[(lineno - 1):])
    # remove redundant \t
    def removeTab(line):
        if line[:4] == '    ':
            return line[4:]
        else:
            return line
    while nlines[0][:4] == '    ':
        nlines = [removeTab(line) for line in nlines]
    return ''.join(nlines)

def getFileSource(file):
    lines = linecache.getlines(file)
    return ''.join(lines)

def staticParallelize(funcobj):
    code = getSourceCode(funcobj)
    root = ast.parse(code)

    fca = FunctionCostAnalyzer([root])
    ca = CostAnalyzer(root, fca.cost)
    for k in ca.cost:
        ca.cost[k] = 1

    rwa = ReadWriteAnalyzer(root)
    se = SequenceExtractor(root)

    seqParallelizables = []
    loopParallelizables = []
    #compParallelizables = []

    for i, seq in enumerate(se.sequences):
        da = DependenceAnalyzer(seq, rwa.Read, rwa.Write, kind='sequential')
        
        #da.draw('graphs/test.seq.' + str(i) + '.dg.png')

        sp = SequenceParallelizer(seq, da.dependence, ca.cost)

        if len(sp.parallelizableSets) > 0:
            seqParallelizables += sp.parallelizableSets
    
    le = LoopExtractor(root)
    for i, loop in enumerate(le.loops):
        nseq = []
        deps = set()
        for stmt in loop.body:
            ee = ExprExtractor(stmt)
            deps |= ee.dependence
            nseq += ee.exprs

        if isinstance(loop, ast.While):
            nloop = ast.While(loop.test, nseq, loop.orelse)
        elif isinstance(loop, ast.For):
            nloop = ast.For(loop.target, loop.iter, nseq, loop.orelse, loop.type_comment)
        else:
            raise
        
        da = DependenceAnalyzer(nloop, rwa.Read, rwa.Write, kind='loop')
        da.dependence |= deps
        
        lp = LoopParallelizer(nloop, da.dependence, ca.cost)

        if len(lp.parallelizable) > 0:
            loopParallelizables += lp.parallelizable
    
    return seqParallelizables, loopParallelizables

class StaticParallelizer:
    def __init__(self, funcobj):
        # parse AST
        code = getSourceCode(funcobj)
        root = ast.parse(code).body[0]

        libs = self.parse_libs(funcobj)
        
        self.parallelizables = []
        self.parallelize(root, libs)



    def parse_libs(self, funcobj):
        file = funcobj.__code__.co_filename
        module = funcobj.__code__.co_filename.split('.')[-2]
        name = funcobj.__code__.co_name
        self.func = (file, module, name)

        src = getFileSource(file)
        rt = ast.parse(src)
        rwa = ReadWriteAnalyzer(rt)
        return rwa.Libs

    def parallelize(self, root, libs):
        fca = FunctionCostAnalyzer([root])
        ca = CostAnalyzer(root, fca.cost)
        for k in ca.cost:
            ca.cost[k] = 1

        rwa = ReadWriteAnalyzer(root, Libs=libs)

        pickleLst = None

        se = SequenceExtractor(root)
        for i, seq in enumerate(se.sequences):
            da = DependenceAnalyzer(seq, rwa.Read, rwa.Write, kind='sequential')
            sp = SequenceParallelizer(seq, da.dependence, ca.cost)

            if len(sp.parallelizableSets) > 0:
                #seqParallelizables += sp.parallelizableSets
                fio = io.StringIO()
                pickleLst = [
                    'Seq',
                    [
                        root,                   # AST of all funcDef
                        seq,                    # AST of parallelizable seq
                        sp,                     # parallelizer
                        rwa                     # ReadWrite Analyzer
                    ]
                ]
                origStdout = sys.stdout
                sys.stdout = fio

                print('Seq')
                print("-" * 50)
                print('Code:')
                print(getstr(seq))
                print("-" * 50)
                for pset in sp.parallelizableSets:
                    for stmt in pset:
                        print(getstr(stmt))
                    print("-" * 50)

                sys.stdout = origStdout

                self.parallelizables.append((fio.getvalue(), pickleLst, self.func))

        le = LoopExtractor(root)
        for i, loop in enumerate(le.loops):
            nseq = []
            deps = set()
            for stmt in loop.body:
                ee = ExprExtractor(stmt)
                deps |= ee.dependence
                nseq += ee.exprs

            nloop = ast.For(loop.target, loop.iter, nseq, loop.orelse, loop.type_comment)    
            da = DependenceAnalyzer(nloop, rwa.Read, rwa.Write, kind='loop')
            da.dependence |= deps
            
            lp = LoopParallelizer(nloop, da.dependence, ca.cost)

            if len(lp.parallelizable) > 0:
                fio = io.StringIO()
                pickleLst = [
                    'Loop',
                    [
                        root,                   # AST of all funcDef
                        loop,                   # AST of parallelizable seq
                        nseq,                   # seq
                        lp,                     # parallelizer
                        10,                     # number of iterations, used to decide of whether block
                        rwa                     # ReadWrite Analyzer
                    ]
                ]

                origStdout = sys.stdout
                sys.stdout = fio
                print('Loop')
                print('-' * 50)
                print('Code:')
                print(getstr(loop))
                print('-' * 50)
                for stmt in lp.parallelizable:
                    print(getstr(stmt))
                    print('-' * 50)

                sys.stdout = origStdout  

                self.parallelizables.append((fio.getvalue(), pickleLst, self.func))

        ce = CompExtractor(root)
        cp = CompParallelizer(ce.comps, rwa.Read, rwa.Write, ca.cost)

        for comp in cp.parallelizableComps:
            fio = io.StringIO()
            pickleLst = [
                'Comp',
                [
                    root,                   # AST of all funcDef
                    comp,                   # AST of parallelizable seq
                    cp,                     # parallelizer
                    rwa                     # ReadWrite Analyzer
                ]
            ]
            #f = open(self.paraDumpFile, 'a')
            origStdout = sys.stdout
            sys.stdout = fio
            
            print('Comp')
            print('-' * 50)
            print(getstr(comp))
            print('-' * 50)
            sys.stdout = origStdout

            self.parallelizables.append((fio.getvalue(), pickleLst, self.func))
