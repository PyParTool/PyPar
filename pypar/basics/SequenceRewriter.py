import ast
from pypar.basics.utils import getstr
from pypar.basics.config import PUTSIZE, MAX_TASK_NUM

class RaySequenceRewriter:
    # assume all parallelizables are stmts, no sub exprs
    def __init__(self, 
            funcDef,    # the funcDef to be rewrite
            seq,        # target sequence for parallelization
            stDepthSet, endDepth,   # a stmt/expr start at which depth & end at which depth
            parallelizable,     # parallelizable stmt/expr
            Read, Write):
        assert isinstance(funcDef, ast.FunctionDef)
        self.funcDef = funcDef

        self.parallelizable = parallelizable
        self.nodes = endDepth.keys()
        self.nodeSet = set(self.nodes)

        self.funcCnt = 0    # counter for generating names of tmpFunc & tmpVar
        self.remoteCnt = 0    #

        self.rewrite(seq, stDepthSet, endDepth, Read, Write)

    def rewrite(self, seq, stDepthSet, endDepth, Read, Write):
        self.parallelFuncDefs = []
        stmtSeq = []

        maxDepth = max(stDepthSet.keys())
        getStmts = {i: set() for i in range(maxDepth + 1)}

        for level in range(1, maxDepth + 1):
            for getStmt in getStmts[level]:
                stmtSeq.append(getStmt)
            
            nodeSet = stDepthSet[level]
            nodeSet = list(nodeSet)
            nodeSet.sort(key=lambda x: getstr(x))

            for node in nodeSet:
                if node in self.parallelizable:
                    readVars = Read[node] - set({'stdin', 'stdout'})
                    writeVars = Write[node] - set({'stdin', 'stdout'})
                    funcDef = self.getFuncDef(node, readVars, writeVars)
                    remoteTmp, callStmt = self.getCallStmt(funcDef.name, readVars)
                    getStmt = self.getGetStmt(remoteTmp, writeVars)
                    
                    self.parallelFuncDefs.append(funcDef)
                    stmtSeq.append(callStmt)
                    getStmts[endDepth[node]].add(getStmt)
                else:
                    stmtSeq.append(node)

        p, br = seq[0].p, seq[0].br
        stmtList = getattr(p, br)
        idxBegin, idxEnd = stmtList.index(seq[0]), stmtList.index(seq[-1])

        newStmtList = stmtList[:idxBegin] + stmtSeq + stmtList[idxEnd+1:]
        setattr(p, br, newStmtList)

        self.funcDef.name = self.funcDef.name + '_ray'

    def getFuncDef(self, node, readVars, writeVars):
        funcName = self.funcDef.name + '_parallel_func_' + str(self.funcCnt)
        self.funcCnt += 1

        bdStmt = node
        rtStmt = ast.Return(
                    ast.Tuple([ast.Name(wt) for wt in writeVars]))                
        body = [bdStmt, rtStmt]

        args = ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(
                                rd,
                                annotation = None,
                                type_comment = None) 
                            for rd in readVars], 
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults = [])
        
        funcDef = ast.FunctionDef(funcName, args, body, [])
        
        return funcDef
    
    def getCallStmt(self, funcName, readVars):
        remoteTmp = 'remote_tmp_' + str(self.remoteCnt)
        self.remoteCnt += 1

        ## ray.remote(f).remote(reads)
        callExpr = ast.Call(
                            ast.Attribute(
                                ast.Call(
                                    ast.Attribute(
                                        ast.Name('ray'), 
                                        'remote'),
                                    [ast.Name(funcName)],
                                    []),
                                'remote'), 
                            [ast.Name(rd) for rd in readVars],
                            [])
        assignStmt = ast.Assign(
                            [ast.Name(remoteTmp)],
                            callExpr)
        
        return remoteTmp, assignStmt
    
    def getGetStmt(self, remoteTmp, writeVars):
        if len(writeVars) == 0:
            target = ast.Name('_')
        else:
            target = ast.Tuple([ast.Name(wt) for wt in writeVars])
        
        callExpr = ast.Call(ast.Attribute(ast.Name('ray'), 
                                            'get'), 
                            [ast.Name(remoteTmp)],
                            [])

        assignStmt = ast.Assign([target], callExpr)

        return assignStmt

class ConcurrentSequenceRewriter:
    # assume all parallelizables are stmts, no sub exprs
    def __init__(self, 
            funcDef,    # the funcDef to be rewrite
            seq,        # target sequence for parallelization
            stDepthSet, endDepth,   # a stmt/expr start at which depth & end at which depth
            parallelizable,     # parallelizable stmt/expr
            Read, Write, 
            executorCls = 'thread'):
        assert isinstance(funcDef, ast.FunctionDef)
        self.funcDef = funcDef

        self.parallelizable = parallelizable
        self.nodes = endDepth.keys()
        self.nodeSet = set(self.nodes)

        # counter for generating names of tmpFunc & tmpVar
        self.funcCnt = 0    
        self.remoteCnt = 0

        assert(executorCls == 'thread' or executorCls == 'process')
        self.executorCls = executorCls

        self.rewrite(seq, stDepthSet, endDepth, Read, Write)

    def rewrite(self, seq, stDepthSet, endDepth, Read, Write):
        self.parallelFuncDefs = []
        stmtSeq = []

        maxDepth = max(stDepthSet.keys())
        getStmts = {i: set() for i in range(maxDepth + 1)}

        parallel_executor = 'parallel_executor'

        max_workers = 0

        for level in range(1, maxDepth + 1):
            for getStmt in getStmts[level]:
                stmtSeq.append(getStmt)
            
            nodeSet = stDepthSet[level]

            nodeSet = list(nodeSet)
            nodeSet.sort(key=lambda x: getstr(x))
            for node in nodeSet:
                if node in self.parallelizable:
                    readVars = Read[node] - set({'stdin', 'stdout'})
                    writeVars = Write[node] - set({'stdin', 'stdout'})
                    funcDef = self.getFuncDef(node, readVars, writeVars)
                    remoteTmp, callStmt = self.getCallStmt(parallel_executor, funcDef.name, readVars)
                    getStmt = self.getGetStmt(remoteTmp, writeVars)
                    
                    self.parallelFuncDefs.append(funcDef)
                    stmtSeq.append(callStmt)
                    getStmts[endDepth[node]].add(getStmt)
                    max_workers += 1
                else:
                    stmtSeq.append(node)
        
        initStmt = self.getInitStmt(parallel_executor, max_workers)
        stmtSeq = [initStmt] + stmtSeq

        p, br = seq[0].p, seq[0].br
        stmtList = getattr(p, br)
        idxBegin, idxEnd = stmtList.index(seq[0]), stmtList.index(seq[-1])

        newStmtList = stmtList[:idxBegin] + stmtSeq + stmtList[idxEnd+1:]
        setattr(p, br, newStmtList)

        self.funcDef.name = self.funcDef.name + '_' + self.executorCls

    def getFuncDef(self, node, readVars, writeVars):
        funcName = self.funcDef.name + '_parallel_func_' + str(self.funcCnt)
        self.funcCnt += 1

        bdStmt = node
        rtStmt = ast.Return(
                    ast.Tuple([ast.Name(wt) for wt in writeVars]))                
        body = [bdStmt, rtStmt]

        args = ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(
                                rd,
                                annotation = None,
                                type_comment = None) 
                            for rd in readVars], 
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults = [])
        
        funcDef = ast.FunctionDef(funcName, args, body, [])
        
        return funcDef
    
    def getCallStmt(self, executor, funcName, readVars):
        remoteTmp = 'remote_tmp_' + str(self.remoteCnt)
        self.remoteCnt += 1

        ## ray.remote(f).remote(reads)
        callExpr = ast.Call(
                            ast.Attribute(
                                ast.Name(executor),
                                'submit'), 
                            [ast.Name(funcName)] + [ast.Name(rd) for rd in readVars],
                            [])
        assignStmt = ast.Assign(
                            [ast.Name(remoteTmp)],
                            callExpr)
        
        return remoteTmp, assignStmt
    
    def getGetStmt(self, remoteTmp, writeVars):
        if len(writeVars) == 0:
            target = ast.Name('_')
        else:
            target = ast.Tuple([ast.Name(wt) for wt in writeVars])
        
        callExpr = ast.Call(ast.Attribute(ast.Name(remoteTmp), 
                                            'result'), 
                            [],
                            [])

        assignStmt = ast.Assign([target], callExpr)

        return assignStmt

    def getInitStmt(self, executor, max_workers):
        poolExecutor = 'ThreadPoolExecutor' if self.executorCls == 'thread' else 'ProcessPoolExecutor'
        assignStmt = ast.Assign(
                        [ast.Name(executor)], 
                        ast.Call(
                            ast.Name(poolExecutor), 
                            [], 
                            [ast.keyword(
                                'max_workers', 
                                ast.Constant(max_workers, kind=None))]))
        return assignStmt

class ThreadSequenceRewriter(ConcurrentSequenceRewriter):
    def __init__(self, funcDef, seq, stDepthSet, endDepth, parallelizable, Read, Write):
        super().__init__(funcDef, seq, stDepthSet, endDepth, parallelizable, Read, Write, 'thread')

class ProcessSequenceRewriter(ConcurrentSequenceRewriter):
    def __init__(self, funcDef, seq, stDepthSet, endDepth, parallelizable, Read, Write):
        super().__init__(funcDef, seq, stDepthSet, endDepth, parallelizable, Read, Write, 'process')

if __name__ == '__main__':
    import argparse
    from pypar.basics.utils import slurp, getstr
    from pypar.basics.ReadWriteAnalyzer import ReadWriteAnalyzer
    from pypar.basics.SequenceExtractor import SequenceExtractor
    from pypar.basics.SequenceParallelizer import SequenceParallelizer
    from pypar.basics.DependenceAnalyzer import DependenceAnalyzer
    from pypar.basics.ExprExtractor import ExprExtractor
    from pypar.basics.ParentExtractor import ParentExtractor

    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))

    filename = args.pythonfile.split('/')[-1]

    pe = ParentExtractor(root)
    rwa = ReadWriteAnalyzer(root)
    se = SequenceExtractor(root)
    for i, seq in enumerate(se.sequences):
        nseq = []
        deps = set()
        for stmt in seq:
            #print('-'*50)
            ee = ExprExtractor(stmt)
            deps |= ee.dependence
            nseq += ee.exprs
        
        '''for u in nseq:
            print('-'*50)
            print(getstr(u))
            print(rwa.Readn[u])
            print(rwa.Writen[u])
        print('='*50 + '\n\n')'''

        da = DependenceAnalyzer(nseq, rwa.Read, rwa.Write, kind='sequential')
        da.dependence |= deps
        da.draw('graphs/' + filename + '.seq.' + str(i) + '.dg.png')

        sp = SequenceParallelizer(nseq, da.dependence)
        sr = RaySequenceRewriter(root, seq, sp.stDepthSet, sp.endDepth, sp.parallelizable, rwa.Readn, rwa.Writen)
    
    print(getstr(root))