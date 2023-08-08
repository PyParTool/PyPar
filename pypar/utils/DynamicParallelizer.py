from trace import Trace
import sys
from time import monotonic as _time
import os
import linecache
import ast
import astunparse
import inspect
import linecache
import copy
import io

from pypar.basics.ReadWriteAnalyzer import ReadWriteAnalyzer
from pypar.basics.CompExtractor import CompExtractor
from pypar.basics.CostAnalyzer import CostAnalyzer
from pypar.basics.config import COST_THRESHOLD
from pypar.basics.SequenceExtractor import SequenceExtractor
from pypar.basics.SequenceParallelizer import SequenceParallelizer
from pypar.basics.DependenceAnalyzer import DependenceAnalyzer
from pypar.basics.LoopParallelizer import LoopParallelizer
from pypar.basics.ExprExtractor import ExprExtractor
from pypar.basics.CompParallelizer import CompParallelizer
from pypar.basics.ParentExtractor import ParentExtractor
from pypar.basics.utils import getstr

# dct: key -> (value, count)
# if key not in dct, create new item
# else add to original item
def addOrCreate(dct, key, value):
    if key not in dct:
        dct[key] = [value, 1]
    else:
        dct[key][0] += value
        dct[key][1] += 1

class TimeTracer(Trace):
    def __init__(self, interestingFilePrefixs = None, ignoreFilePrefixs = None):
        super().__init__(ignoredirs=(sys.prefix, sys.exec_prefix))
        
        self.interestingFilePrefixs = interestingFilePrefixs
        self.ignoreFilePrefixs = ignoreFilePrefixs

        self.funcTime = {}   # func -> (time, num)
        self.funcStack = []     # startTime
        
        self.lineTime = {}    # line -> (time, num)
        self.lineStack = []     # (line, startTime)

        self.funcLineno = {}    # func -> startlineno

        self.globaltrace = self._globaltrace
        self.localtrace = self._localtrace # self._localtrace_func
    
    def wantToTrace(self, file, module, func):
        # want to trace lines of this function ?
        return not file.startswith('/usr/lib/python3.8')
        #return func != 'deepcopy'
        #return func[0] != '<'

    def isInterestingFunc(self, file, module, func):
        # ignore useless functions such as builtins
        # assume interesting and ignore do not intersect

        if file[0] == '<' or module[0] == '<' or func[0] == '<':
            return False
        if self.interestingFilePrefixs:
            for prefix in self.interestingFilePrefixs:
                if file.startswith(prefix):
                    return True
            return False
        if self.ignoreFilePrefixs:
            for prefix in self.ignoreFilePrefixs:
                if file.startswith(prefix):
                    return False
        return True

    def isListCompFrame(self, file, module, func):
        # ignore listcomp frame for correct count
        return func == '<listcomp>'

    def _globaltrace(self, frame, why, arg):
        if why == 'call':
            # XXX Should do a better job of identifying methods
            this_func = (self.file_module_function_of(frame))
            if not self.wantToTrace(*this_func):
                return None
            parent_func = self.file_module_function_of(frame.f_back)
            
            self.funcLineno[this_func] = frame.f_lineno
            #print('call', this_func)
            #print('#' * 20)

            self.funcStack.append(_time())

            self.lineStack.append((None, None))

            # call relation
            #if (parent_func, this_func) not in self._callers:
            #    self._callers[(parent_func, this_func)] = 1
            #else:
            #    self._callers[(parent_func, this_func)] += 1
        
            return self.localtrace

    def _localtrace_func(self, frame, why, arg):
        # only trace function time
        if why == 'return':
            this_func = self.file_module_function_of(frame)
            
            # update funcTime
            beginTime = self.funcStack.pop(-1)
            endTime = _time()
            if self.isInterestingFunc(*this_func):
                addOrCreate(self.funcTime, this_func, endTime - beginTime)
        return self.localtrace

    def _localtrace(self, frame, why, arg):
        # trace function & line time
        if why == 'line':
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno
            bname = os.path.basename(filename)
            this_func = self.file_module_function_of(frame)

            this_line = (this_func, lineno, linecache.getline(filename, lineno))
            
            prev_line, beginTime = self.lineStack[-1]
            if prev_line and not self.isListCompFrame(*this_func):
                addOrCreate(self.lineTime, prev_line, _time() - beginTime)
            self.lineStack[-1] = (this_line, _time())

            return self.localtrace
        elif why == 'return':
            #print('return', self.isFirstLine)
            #print('-' * 20)
            #print(self.lineStack)
            this_func = self.file_module_function_of(frame)
            
            # update funcTime
            beginTime = self.funcStack.pop(-1)
            endTime = _time()
            if self.isInterestingFunc(*this_func):
                addOrCreate(self.funcTime, this_func, endTime - beginTime)

            prev_line, beginTime = self.lineStack[-1]
            if prev_line and not self.isListCompFrame(*this_func):
                addOrCreate(self.lineTime, prev_line, _time() - beginTime)
            self.lineStack.pop(-1)
    
    def drawCallerGraph(self, filename='a.png', expectedFiles=None):
        import pygraphviz
        G = pygraphviz.AGraph(directed=True)
        for u, v in self._callers.keys():
            if u[1]  == '<string>' or v[1] == '<string>':
                continue
            if expectedFiles and\
                (u[0] not in expectedFiles or v[0] not in expectedFiles):
                continue
            uText = u[1] + ':' + u[2]
            vText = v[1] + ':' + v[2]
            G.add_edge(uText, vText)
        G.draw(filename, prog='dot')

def getSourceCode(file, module, function, lineno):
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

class DynamicParallelizer:
    # extract the code that costs the most time ( >= COST_THRESHOLD % )
    # try parallelize the costly code

    def runAndTime(self, code, glbs, lcls, 
            interestingFilePrefixs = None,
            ignoreFilePrefixs = None):
        # run code and time each part
        # statistics saved in TimeTracer object

        self.tracer = TimeTracer(
            interestingFilePrefixs=interestingFilePrefixs, 
            ignoreFilePrefixs=ignoreFilePrefixs)
        if glbs == None or lcls == None:
            self.tracer.run(code)
        else:
            self.tracer.runctx(code, globals=glbs, locals=lcls)

    def getEssentialFuncs(self):
        # input: time result
        # output: essential functions = functions that cost most
        #         self.essentialFunctimes : func -> (t, n, lineno)
        #         self.normalizedFuncCost : funcName -> normalized_time
        sortedFuncTimes = sorted(self.tracer.funcTime.items(), key=lambda u: -u[1][0])
        self.totalTime = sortedFuncTimes[0][1][0]
        idx = 0
        for func, (t, n) in sortedFuncTimes:
            if t / self.totalTime < COST_THRESHOLD:
                break
            idx += 1
        self.essentialFuncTimes = sortedFuncTimes[:idx]
        self.essentialFuncs = {
            f: (t, n, self.tracer.funcLineno[f]) 
                for f, (t, n) in self.essentialFuncTimes
        }

        self.normalizedFuncCost = {
            f[2].split('.')[-1] : t / self.totalTime for f, (t, n) in sortedFuncTimes
        }  

    def getEssentialFuncLineTimes(self):
        # input: time result, essential functions
        # output: running time of each line of essential functions
        #         self.funcLineTimes : func -> lineno -> (t, n, code)
        self.funcLineTimes = {
            f: {} for f in self.essentialFuncs
        }
        for (f, lineno, content), (t, n) in self.tracer.lineTime.items():
            if f in self.essentialFuncs:
                self.funcLineTimes[f][lineno - self.essentialFuncs[f][2] + 1] = (t, n, content)
        self.funcLineTimes = {
            f: dict(sorted(dct.items(), key=lambda u: u[0])) 
                for f, dct in self.funcLineTimes.items()
        }

    def getASTTime(self):
        # input: func line time
        # output: 
        #   running time of each AST node
        #         self.astTimeMap: astNode -> (t, n)
        #         self.normalizedastCost: astNode -> normalized_time
        # code segment AST to try parallelize:
        #         self.essentialASTs: astNode -> (t, n, func)
        # not so important:
        #         self.loopNum: loopStmt -> numLoop
        #         self.funcASTs: funcName -> ASTNode

        self.astTimeMap = {}

        self.loopNum = {}
        self.essentialASTs = []
        self.funcASTs = {}

        for f, (t, n, lineno) in self.essentialFuncs.items():
            self.getTimedAST(f, lineno)

        self.normalizedastCost = {
            node : t / self.totalTime for node, (t, n) in self.astTimeMap.items()
        }

    def getTimedAST(self, func, lineno):
        # input:  func, startlineno of func
        # output: astTimeMap, essentialASTs

        # get AST of function
        src = getSourceCode(*func, lineno)
        try:
            root = ast.parse(src)
        except:
            return
        funcDef = root.body[0]
        if not isinstance(funcDef, ast.FunctionDef):
            print(func, lineno)
            print(ast.dump(root))
            print(src)
            return
        assert isinstance(funcDef, ast.FunctionDef)

        self.funcASTs[func] = funcDef
        self.astTimeMap[funcDef] = (self.essentialFuncs[func][0], self.essentialFuncs[func][1])
        
        stmtList = funcDef.body
        allStmts = [(stmt, self.astTimeMap[funcDef][1]) for stmt in stmtList]
        # (stmt, num of parent)
        for stmt, num_p in allStmts:
            self.astTimeMap[stmt] = [0, 0]
            for l in range(stmt.lineno, stmt.end_lineno + 1):
                if l in self.funcLineTimes[func]:
                    self.astTimeMap[stmt][0] += self.funcLineTimes[func][l][0]
            # take AST node that run long enough as essential
            if self.astTimeMap[stmt][0] / self.totalTime > COST_THRESHOLD:
                if stmt.lineno in self.funcLineTimes[func]:
                    self.astTimeMap[stmt][1] = self.funcLineTimes[func][stmt.lineno][1]
                else:
                    for i in range(1, 4):
                        if stmt.lineno + i in self.funcLineTimes[func]:
                            self.astTimeMap[stmt][1] = self.funcLineTimes[func][stmt.lineno + i][1]
                            break
                        elif i == 3:
                            self.astTimeMap[stmt][1] = -1

                if isinstance(stmt, ast.If):
                    for s in stmt.body + stmt.orelse:
                        allStmts.append((s, num_p))
                elif isinstance(stmt, ast.For) or isinstance(stmt, ast.While):
                    self.astTimeMap[stmt][1] = num_p
                    if stmt.lineno in self.funcLineTimes[func]:
                        loopNum = self.funcLineTimes[func][stmt.lineno][1] - num_p
                    else:
                        for i in range(1, 4):
                            if stmt.lineno + i in self.funcLineTimes[func]:
                                loopNum = self.funcLineTimes[func][stmt.lineno + i][1]
                                break
                            elif i == 3:
                                loopNum = -1
                    self.loopNum[stmt] = loopNum
                    for s in stmt.body:
                        allStmts.append((s, loopNum))
                elif isinstance(stmt, ast.Try):
                    for s in stmt.body + stmt.orelse + stmt.finalbody:
                        allStmts.append((s, num_p))
                self.essentialASTs.append([stmt] + self.astTimeMap[stmt] + [func])

        # extract essential statement Sequence, for Seq parallelization
        se = SequenceExtractor(root)
        seqs = se.sequences
        for seq in seqs:
            t, n = 0, 0
            overThresholdCnt = 0
            for stmt in seq:
                if stmt not in self.astTimeMap:
                    continue
                t += self.astTimeMap[stmt][0]
                n = self.astTimeMap[stmt][1]
                if self.astTimeMap[stmt][0] / self.totalTime > COST_THRESHOLD:
                    overThresholdCnt += 1
            if overThresholdCnt >= 2:
                self.essentialASTs.append([seq, t, n, func])
      
    def dumpEssential(self):
        # input: statistics
        # output: self.essentialDumpStr
        fio = io.StringIO()
       
        origStdout = sys.stdout
        sys.stdout = fio
        for (file, mod, f), (t, n, lineno) in self.essentialFuncs.items():
            print('-' * 100)
            print(file)
            print(f)
            print('lineno:', lineno)
            print('running time:', t)
            print('normalized time:', t/self.totalTime)
            print('n_calls:', n)
        
        print('\n\n\n')

        for root, t, n, (file, mod, f) in self.essentialASTs:
            print('-' * 100)
            print('file:', file)
            print('function:', f)
            print('running time:', t)
            print('normalized time:', t/self.totalTime)
            print('n_calls', n)
            print(getstr(root))

        #for u, v in self.tracer._callers.keys():
        #    print(u, ' --> ', v)
        sys.stdout = origStdout
        
        self.essentialDumpStr = fio.getvalue()

    def __init__(self, 
            code,
            glbs,   # globals()
            lcls,   # locals()
            interestingFilePrefixs = None,
            ignoreFilePrefixs = None):
            #, essentialCodeDumpFile = 'essentialCode.txt'):
        
        self.runAndTime(code, glbs, lcls, interestingFilePrefixs, ignoreFilePrefixs)
        
        self.getEssentialFuncs()

        self.getEssentialFuncLineTimes()

        self.getASTTime()
        
        self.dumpEssential()    
        # optional, dump essential code, for comprehensioning
        
        #print(self.essentialDumpStr)

        # fileImportLibs: all the modules imported
        self.fileImportLibs = {}
        
        # parallelizable Report
        # item: (reportStr, pickLst, func)
        self.parallelizables = []

        for root, t, n, func in self.essentialASTs:
            # collect modules imported
            file, _, _ = func
            if file not in self.fileImportLibs:
                src = getFileSource(file)
                rt = ast.parse(src)
                rwa = ReadWriteAnalyzer(rt)
                self.fileImportLibs[file] = rwa.Libs
            
            # try parallelize
            self.parallelAST(root, self.fileImportLibs[file], func)    
           
    def parallelAST(self, root, libs, func):
        ca = CostAnalyzer(
            root=root, 
            funcCost=self.normalizedFuncCost, 
            astCost=self.normalizedastCost)
        rwa = ReadWriteAnalyzer(root, Libs=libs)

        # save essential code, ... 
        pickleLst = None

        f = io.StringIO()
        if isinstance(root, list):
            da = DependenceAnalyzer(root, rwa.Readn, rwa.Writen, kind='sequential')
            sp = SequenceParallelizer(root, da.dependence, ca.cost)
            if len(sp.parallelizableSets):
                pickleLst = [
                    'Seq',
                    [
                        self.funcASTs[func],    # AST of all funcDef
                        root,                   # AST of parallelizable seq
                        sp,                     # parallelizer
                        rwa                     # ReadWrite Analyzer
                    ]
                ]
                origStdout = sys.stdout
                sys.stdout = f

                print('Seq')
                print("-" * 50)
                print('Code:')
                print(getstr(root))
                print("-" * 50)
                saved = 0
                for pset in sp.parallelizableSets:
                    tims = []
                    for stmt in pset:
                        if stmt in self.normalizedastCost:
                            tim = self.normalizedastCost[stmt]
                        else:
                            tim = ca.cost[stmt]
                        tims.append(tim)
                        print(getstr(stmt), tim)
                    print("-" * 50)
                    saved += sum(tims) - max(tims)
                print("expected parallel time: ", 1.0 - saved)

                sys.stdout = origStdout
        elif isinstance(root, ast.For):
            pe = ParentExtractor(root)
            nseq = []
            deps = set()
            for stmt in root.body:
                ee = ExprExtractor(stmt)
                deps |= ee.dependence
                nseq += ee.exprs
            nloop = ast.For(root.target, root.iter, nseq, root.orelse, root.type_comment)
            da = DependenceAnalyzer(nloop, rwa.Read, rwa.Write, kind='loop')
            da.dependence |= deps
            
            #print(getstr(root))
            #da.draw()
            
            lp = LoopParallelizer(nloop, da.dependence, ca.cost)

            if len(lp.parallelizable):
                N_loop = self.loopNum[root]

                pickleLst = [
                    'Loop',
                    [
                        self.funcASTs[func],    # AST of all funcDef
                        root,                   # AST of parallelizable seq
                        nseq,                   # seq
                        lp,                     # parallelizer
                        N_loop,                 # number of iterations, used to decide of whether block
                        rwa                     # ReadWrite Analyzer
                    ]
                ]

                if N_loop > 20:
                    N_loop = 10 # num_block
                #if N_loop <= 1:
                #    return

                #f = open(self.paraDumpFile, 'a')
                origStdout = sys.stdout
                sys.stdout = f
                print('Loop')
                print('-' * 50)
                print('Code:')
                print(getstr(root))
                print('-' * 50)
                total_Time = 0
                for stmt in lp.parallelizable:
                    if stmt in self.normalizedastCost:
                        total_Time += self.normalizedastCost[stmt]
                    else:
                        total_Time += ca.cost[stmt]
                    print(getstr(stmt))
                    print('-' * 50)
                
                saved = total_Time / N_loop * (N_loop - 1)
                print('N_loop: ', self.loopNum[root])
                print('parallel_degree: ', N_loop)
                print("expected parallel time: ", 1.0 - saved)

                #print('-' * 50)

                #lr = LoopRewriter(root, nseq, lp.sccStmtList, root, lp.parallelizable, rwa.Readn, rwa.Writen)
                #print(getstr(lr.resSeq))

                sys.stdout = origStdout
                #f.close()
        elif isinstance(root, ast.Assign) or isinstance(root, ast.Return) or isinstance(root, ast.Expr):
            ce = CompExtractor(root)
            if len(ce.comps) > 0:
                rwa = ReadWriteAnalyzer(root)
                #print(astunparse.unparse(root))

                cp = CompParallelizer(ce.comps, rwa.Read, rwa.Write, ca.cost)

                if len(cp.parallelizableComps) > 0:
                    pickleLst = [
                        'Comp',
                        [
                            self.funcASTs[func],    # AST of all funcDef
                            root,                   # AST of parallelizable seq
                            cp,                     # parallelizer
                            rwa                     # ReadWrite Analyzer
                        ]
                    ]
                    #f = open(self.paraDumpFile, 'a')
                    origStdout = sys.stdout
                    sys.stdout = f
                    for comp in cp.parallelizableComps:
                        print('Comp')
                        print(getstr(root))
                        print(getstr(comp))
                        if root in self.normalizedastCost:
                            print(self.normalizedastCost[root])
                    sys.stdout = origStdout
                    #f.close()

        parallelDumpString = f.getvalue()

        if len(parallelDumpString) > 0:
            self.parallelizables.append((parallelDumpString, pickleLst, func))
    
from pypar.utils.DepTracer import DepTracer, WriteObjAnalyzer
class DynamicParallelizerWithWriteObj:
    # extract the code that costs the most time ( >= COST_THRESHOLD % )
    # try parallelize the costly code

    def runAndTime(self, code, glbs, lcls, 
            interestingFilePrefixs = None,
            ignoreFilePrefixs = None):
        # run code and time each part
        # statistics saved in TimeTracer object

        self.tracer = TimeTracer(
            interestingFilePrefixs=interestingFilePrefixs, 
            ignoreFilePrefixs=ignoreFilePrefixs
        )
        if glbs == None or lcls == None:
            self.tracer.run(code)
        else:
            self.tracer.runctx(code, globals=glbs, locals=lcls)

    def getEssentialFuncs(self):
        # input: time result
        # output: essential functions = functions that cost most
        #         self.essentialFunctimes : func -> (t, n, lineno)
        #         self.normalizedFuncCost : funcName -> normalized_time
        sortedFuncTimes = sorted(self.tracer.funcTime.items(), key=lambda u: -u[1][0])
        self.totalTime = sortedFuncTimes[0][1][0]
        idx = 0
        for func, (t, n) in sortedFuncTimes:
            if t / self.totalTime < COST_THRESHOLD:
                break
            idx += 1
        self.essentialFuncTimes = sortedFuncTimes[:idx]
        self.essentialFuncs = {
            f: (t, n, self.tracer.funcLineno[f]) 
                for f, (t, n) in self.essentialFuncTimes
        }

        self.normalizedFuncCost = {
            f[2].split('.')[-1] : t / self.totalTime for f, (t, n) in sortedFuncTimes
        }  

    def getEssentialFuncLineTimes(self):
        # input: time result, essential functions
        # output: running time of each line of essential functions
        #         self.funcLineTimes : func -> lineno -> (t, n, code)
        self.funcLineTimes = {
            f: {} for f in self.essentialFuncs
        }
        for (f, lineno, content), (t, n) in self.tracer.lineTime.items():
            if f in self.essentialFuncs:
                self.funcLineTimes[f][lineno - self.essentialFuncs[f][2] + 1] = (t, n, content)
        self.funcLineTimes = {
            f: dict(sorted(dct.items(), key=lambda u: u[0])) 
                for f, dct in self.funcLineTimes.items()
        }

    def getASTTime(self):
        # input: func line time
        # output: 
        #   running time of each AST node
        #         self.astTimeMap: astNode -> (t, n)
        #         self.normalizedastCost: astNode -> normalized_time
        # code segment AST to try parallelize:
        #         self.essentialASTs: astNode -> (t, n, func)
        # not so important:
        #         self.loopNum: loopStmt -> numLoop
        #         self.funcASTs: funcName -> ASTNode

        self.astTimeMap = {}

        self.loopNum = {}
        self.essentialASTs = []
        self.funcASTs = {}

        for f, (t, n, lineno) in self.essentialFuncs.items():
            self.getTimedAST(f, lineno)

        self.normalizedastCost = {
            node : t / self.totalTime for node, (t, n) in self.astTimeMap.items()
        }

    def getTimedAST(self, func, lineno):
        # input:  func, startlineno of func
        # output: astTimeMap, essentialASTs

        # get AST of function
        src = getSourceCode(*func, lineno)
        try:
            root = ast.parse(src)
        except:
            return
        funcDef = root.body[0]
        if not isinstance(funcDef, ast.FunctionDef):
            print(func, lineno)
            print(ast.dump(root))
            print(src)
            return
        assert isinstance(funcDef, ast.FunctionDef)

        self.funcASTs[func] = funcDef
        self.astTimeMap[funcDef] = (self.essentialFuncs[func][0], self.essentialFuncs[func][1])
        
        stmtList = funcDef.body
        allStmts = [(stmt, self.astTimeMap[funcDef][1]) for stmt in stmtList]
        # (stmt, num of parent)
        for stmt, num_p in allStmts:
            self.astTimeMap[stmt] = [0, 0]
            for l in range(stmt.lineno, stmt.end_lineno + 1):
                if l in self.funcLineTimes[func]:
                    self.astTimeMap[stmt][0] += self.funcLineTimes[func][l][0]
            # take AST node that run long enough as essential
            if self.astTimeMap[stmt][0] / self.totalTime > COST_THRESHOLD:
                if stmt.lineno in self.funcLineTimes[func]:
                    self.astTimeMap[stmt][1] = self.funcLineTimes[func][stmt.lineno][1]
                else:
                    for i in range(1, 4):
                        if stmt.lineno + i in self.funcLineTimes[func]:
                            self.astTimeMap[stmt][1] = self.funcLineTimes[func][stmt.lineno + i][1]
                            break
                        elif i == 3:
                            self.astTimeMap[stmt][1] = -1

                if isinstance(stmt, ast.If):
                    for s in stmt.body + stmt.orelse:
                        allStmts.append((s, num_p))
                elif isinstance(stmt, ast.For) or isinstance(stmt, ast.While):
                    self.astTimeMap[stmt][1] = num_p
                    if stmt.lineno in self.funcLineTimes[func]:
                        loopNum = self.funcLineTimes[func][stmt.lineno][1] - num_p
                    else:
                        for i in range(1, 4):
                            if stmt.lineno + i in self.funcLineTimes[func]:
                                loopNum = self.funcLineTimes[func][stmt.lineno + i][1]
                                break
                            elif i == 3:
                                loopNum = -1
                    self.loopNum[stmt] = loopNum
                    for s in stmt.body:
                        allStmts.append((s, loopNum))
                elif isinstance(stmt, ast.Try):
                    for s in stmt.body + stmt.orelse + stmt.finalbody:
                        allStmts.append((s, num_p))
                self.essentialASTs.append([stmt] + self.astTimeMap[stmt] + [func])

        # extract essential statement Sequence, for Seq parallelization
        se = SequenceExtractor(root)
        seqs = se.sequences
        for seq in seqs:
            t, n = 0, 0
            overThresholdCnt = 0
            for stmt in seq:
                if stmt not in self.astTimeMap:
                    continue
                t += self.astTimeMap[stmt][0]
                n = self.astTimeMap[stmt][1]
                if self.astTimeMap[stmt][0] / self.totalTime > COST_THRESHOLD:
                    overThresholdCnt += 1
            if overThresholdCnt >= 2:
                self.essentialASTs.append([seq, t, n, func])
      
    def dumpEssential(self):
        # input: statistics
        # output: self.essentialDumpStr
        fio = io.StringIO()
       
        origStdout = sys.stdout
        sys.stdout = fio
        for (file, mod, f), (t, n, lineno) in self.essentialFuncs.items():
            print('-' * 100)
            print(file)
            print(f)
            print('lineno:', lineno)
            print('running time:', t)
            print('normalized time:', t/self.totalTime)
            print('n_calls:', n)
        
        print('\n\n\n')

        for root, t, n, (file, mod, f) in self.essentialASTs:
            print('-' * 100)
            print('file:', file)
            print('function:', f)
            print('running time:', t)
            print('normalized time:', t/self.totalTime)
            print('n_calls', n)
            print(getstr(root))

        #for u, v in self.tracer._callers.keys():
        #    print(u, ' --> ', v)
        sys.stdout = origStdout
        
        self.essentialDumpStr = fio.getvalue()

    def __init__(self, 
            code,
            glbs,   # globals()
            lcls,   # locals()
            interestingFilePrefixs = None,
            ignoreFilePrefixs = None):
            #, essentialCodeDumpFile = 'essentialCode.txt'):
        
        dpt = DepTracer()
        dpt.runctx(code, glbs, lcls)
        woa = WriteObjAnalyzer(dpt.NameMap)
        self.writeObj = woa.writeObj
        #print(self.writeObj)

        self.runAndTime(code, glbs, lcls, interestingFilePrefixs, ignoreFilePrefixs)
        
        self.getEssentialFuncs()

        self.getEssentialFuncLineTimes()

        self.getASTTime()
        
        self.dumpEssential()    
        # optional, dump essential code, for comprehensioning
        
        #print(self.essentialDumpStr)

        # fileImportLibs: all the modules imported
        self.fileImportLibs = {}
        
        # parallelizable Report
        # item: (reportStr, pickLst, func)
        self.parallelizables = []

        for root, t, n, func in self.essentialASTs:
            # collect modules imported
            file, _, _ = func
            if file not in self.fileImportLibs:
                src = getFileSource(file)
                rt = ast.parse(src)
                rwa = ReadWriteAnalyzer(rt)
                self.fileImportLibs[file] = rwa.Libs
            
            # try parallelize
            self.parallelAST(root, self.fileImportLibs[file], func)    
           
    def parallelAST(self, root, libs, func):
        ca = CostAnalyzer(
            root=root, 
            funcCost=self.normalizedFuncCost, 
            astCost=self.normalizedastCost)
        # writeObj
        rwa = ReadWriteAnalyzer(root, Libs=libs, writeObj=self.writeObj)

        # save essential code, ... 
        pickleLst = None

        f = io.StringIO()
        if isinstance(root, list):
            da = DependenceAnalyzer(root, rwa.Readn, rwa.Writen, kind='sequential')
            sp = SequenceParallelizer(root, da.dependence, ca.cost)
            if len(sp.parallelizableSets):
                pickleLst = [
                    'Seq',
                    [
                        self.funcASTs[func],    # AST of all funcDef
                        root,                   # AST of parallelizable seq
                        sp,                     # parallelizer
                        rwa                     # ReadWrite Analyzer
                    ]
                ]
                origStdout = sys.stdout
                sys.stdout = f

                print('Seq')
                print("-" * 50)
                print('Code:')
                print(getstr(root))
                print("-" * 50)
                saved = 0
                for pset in sp.parallelizableSets:
                    tims = []
                    for stmt in pset:
                        if stmt in self.normalizedastCost:
                            tim = self.normalizedastCost[stmt]
                        else:
                            tim = ca.cost[stmt]
                        tims.append(tim)
                        print(getstr(stmt), tim)
                    print("-" * 50)
                    saved += sum(tims) - max(tims)
                print("expected parallel time: ", 1.0 - saved)

                sys.stdout = origStdout
        elif isinstance(root, ast.For):
            #print(getstr(root))
            pe = ParentExtractor(root)
            nseq = []
            deps = set()
            for stmt in root.body:
                ee = ExprExtractor(stmt)
                deps |= ee.dependence
                nseq += ee.exprs
            '''for stmt in nseq:
                print('-' * 50)
                print(getstr(stmt))
                print(rwa.Write[stmt])
            '''
            nloop = ast.For(root.target, root.iter, nseq, root.orelse, root.type_comment)
            da = DependenceAnalyzer(nloop, rwa.Read, rwa.Write, kind='loop')
            da.dependence |= deps
            
            #print(getstr(root))
            #da.draw()
            
            lp = LoopParallelizer(nloop, da.dependence, ca.cost)

            if len(lp.parallelizable):
                N_loop = self.loopNum[root]

                pickleLst = [
                    'Loop',
                    [
                        self.funcASTs[func],    # AST of all funcDef
                        root,                   # AST of parallelizable seq
                        nseq,                   # seq
                        lp,                     # parallelizer
                        N_loop,                 # number of iterations, used to decide of whether block
                        rwa                     # ReadWrite Analyzer
                    ]
                ]

                if N_loop > 20:
                    N_loop = 10 # num_block
                #if N_loop <= 1:
                #    return

                #f = open(self.paraDumpFile, 'a')
                origStdout = sys.stdout
                sys.stdout = f
                print('Loop')
                print('-' * 50)
                print('Code:')
                print(getstr(root))
                print('-' * 50)
                total_Time = 0
                for stmt in lp.parallelizable:
                    if stmt in self.normalizedastCost:
                        total_Time += self.normalizedastCost[stmt]
                    else:
                        total_Time += ca.cost[stmt]
                    print(getstr(stmt))
                    print('-' * 50)
                
                saved = total_Time / N_loop * (N_loop - 1)
                print('N_loop: ', self.loopNum[root])
                print('parallel_degree: ', N_loop)
                print("expected parallel time: ", 1.0 - saved)

                #print('-' * 50)

                #lr = LoopRewriter(root, nseq, lp.sccStmtList, root, lp.parallelizable, rwa.Readn, rwa.Writen)
                #print(getstr(lr.resSeq))

                sys.stdout = origStdout
                #f.close()
        elif isinstance(root, ast.Assign) or isinstance(root, ast.Return) or isinstance(root, ast.Expr):
            ce = CompExtractor(root)
            if len(ce.comps) > 0:
                cp = CompParallelizer(ce.comps, rwa.Read, rwa.Write, ca.cost)

                if len(cp.parallelizableComps) > 0:
                    pickleLst = [
                        'Comp',
                        [
                            self.funcASTs[func],    # AST of all funcDef
                            root,                   # AST of parallelizable seq
                            cp,                     # parallelizer
                            rwa                     # ReadWrite Analyzer
                        ]
                    ]
                    #f = open(self.paraDumpFile, 'a')
                    origStdout = sys.stdout
                    sys.stdout = f
                    for comp in cp.parallelizableComps:
                        print('Comp')
                        print(getstr(root))
                        print(getstr(comp))
                        if root in self.normalizedastCost:
                            print(self.normalizedastCost[root])
                    sys.stdout = origStdout
                    #f.close()

        parallelDumpString = f.getvalue()

        if len(parallelDumpString) > 0:
            self.parallelizables.append((parallelDumpString, pickleLst, func))
    
           