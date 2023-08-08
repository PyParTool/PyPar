import ast
from pypar.basics.utils import getstr
from pypar.basics.config import NUM_BLOCK
import copy

class RayLoopRewriter:
    def __init__(self, funcDef, seq, sccStmtList, loop, parallelizable, Read, Write):
        assert(isinstance(funcDef, ast.FunctionDef))
        self.funcDef = funcDef

        self.nodes = seq
        self.nodeSet = set(seq)
        self.parallelizable = parallelizable
        
        # counters for generating names
        self.funcCnt = 0
        self.loopCnt = 0
        self.exprTmpCnt = 0

        self.Read = Read
        self.Write = Write

        assert(isinstance(loop, ast.For))

        self.getExtensiable()
        self.getParallelSeqs(sccStmtList)

        self.rewrite(loop)

    def rewrite(self, loop): 
        self.parallelFuncDefs = []
        takes = []
        resSeq = []
        
        # the write variable is useful only if it can be readed by following loops
        followingReads = self.getFollowingReads(self.parallelSeqs)
        for (seq, paraStartIdx), followRds in zip(self.parallelSeqs, followingReads):
            if paraStartIdx != None:
                readVars, writeVars = self.getReadWrite(seq)

                paraSeq = seq[paraStartIdx:]
                nonParaSeq = seq[:paraStartIdx]
                paraReads, paraWrites = self.getReadWrite(paraSeq)

                wtVars, funcDef = self.getFuncDef(paraSeq, paraReads, paraWrites & followRds)
    
                nonParaWrites = list((set(writeVars) - set(wtVars)) & followRds)

                rmt, stmts = self.getParaLoopStmt(loop, nonParaSeq, funcDef.name, nonParaWrites, paraReads, takes)

                self.parallelFuncDefs.append(funcDef)
                resSeq += stmts

                takes.append((rmt, nonParaWrites + wtVars))
            else:
                # non-parallel loop is always the last one
                loopStmt = self.getSeqLoopStmt(loop, seq, takes)
                resSeq.append(loopStmt)
        
        if hasattr(loop, 'p') and hasattr(loop, 'br'):
            p, br = loop.p, loop.br
            attr = getattr(p, br)

            assert (isinstance(attr, list))
            idx = attr.index(loop)
            setattr(p, br, attr[:idx] + resSeq + attr[idx+1:])

        self.funcDef.name = self.funcDef.name + '_ray'

    def getFollowingReads(self, parallelSeqs):
        followingReads = []
        curSeq = []
        for seq, paraStartIdx in reversed(parallelSeqs):
            rd, wt = self.getReadWrite(curSeq)
            followingReads.append(rd)
            curSeq += seq
        return list(reversed(followingReads))

    def getExtensiable(self):
        self.extensiable = set()
        for u in self.nodes:
            if (isinstance(u, ast.expr) 
                and u in self.parallelizable):
                pNode = u.p
                while pNode not in self.nodeSet:
                    pNode = pNode.p
                if pNode not in self.parallelizable:
                    self.extensiable.add(u)
    
    def getFuncDef(self, seq, readVars, writeVars):
        funcName = self.funcDef.name + '_parallel_func_' + str(self.funcCnt)
        self.funcCnt += 1

        tmpVarList = []
        body = []
        for node in seq:
            if isinstance(node, ast.expr):
                tmpVar = 'expr_tmp_' + str(self.exprTmpCnt)
                self.exprTmpCnt += 1
                tmpVarList.append(tmpVar)
                stmt = ast.Assign([ast.Name(tmpVar)], node, None)

                p, br = node.p, node.br
                attr = getattr(p, br)
                if isinstance(attr, list):
                    idx = attr.index(node)
                    attr[idx] = ast.Name(tmpVar)
                else:
                    setattr(p, br, ast.Name(tmpVar))

            else:
                stmt = node
            body.append(stmt)
        
        rtStmt = ast.Return(
                    ast.Tuple([ast.Name(wt) for wt in tmpVarList + list(writeVars)]))                
        body.append(rtStmt)

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
        
        return tmpVarList + list(writeVars), funcDef
    
    def getTakeStmt(self, remoteList, writeVars, loopIdx):
        # targets, ... = remoteList[loopIdx]
        target = ast.Tuple([ast.Name(wt) for wt in writeVars])
        if len(writeVars) == 0:
            target = ast.Name('_')
        value = ast.Subscript(ast.Name(remoteList), ast.Index(ast.Name(loopIdx)))
        takeStmt = ast.Assign([target], value)
        return takeStmt

    def getParaLoopStmt(self, loop, nonParaSeq, funcName, nonParaWrites, paraReads, takes):
        # remoteList = []
        # for loopIdx, ... in enumerate(iter):
        #     ... = remoteList_i[loopIdx]
        #     ...
        #     nonParaSeqs
        #     remoteList.append([nonParaWrites] + parallelFunc.remote(...))
        # remoteList = ray.get(remoteList)

        assert(isinstance(loop, ast.For))

        remoteList = 'remote_list_' + str(self.loopCnt)
        loopIdx = 'loop_idx_' + str(self.loopCnt)
        self.loopCnt += 1

        listInitStmt = ast.Assign([ast.Name(remoteList)], ast.List([]))
        
        # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
        target = ast.Tuple([ast.Name(loopIdx), loop.target])
        niter = ast.Call(ast.Name('enumerate'), [loop.iter], [])

        # remoteList.append([nonParaWrites] + parallelFunc.remote(...))
        callExpr = ast.Call(
                        ast.Attribute(
                                ast.Call(
                                    ast.Attribute(
                                        ast.Name('ray'),    
                                        'remote'),
                                    [ast.Name(funcName)],
                                    []),
                                'remote'), 
                            [ast.Name(rd) for rd in paraReads],
                            [])
        if len(nonParaWrites) > 0:
            wtVarsExpr = ast.BinOp(
                            left=ast.Tuple([ast.Name(wt) for wt in nonParaWrites]), 
                            op=ast.Add(), 
                            right=callExpr)
        else:
            wtVarsExpr = callExpr
        appendStmt = ast.Call(ast.Attribute(ast.Name(remoteList),
                                            'append'),
                            [wtVarsExpr],
                            [])
        appendStmt = ast.Expr(appendStmt)

        body = [self.getTakeStmt(rmt, wtv, loopIdx) for rmt, wtv in takes] + \
                [stmt for stmt in nonParaSeq] + \
                [appendStmt]

        orelse = loop.orelse
        type_comment = loop.type_comment

        loopStmt = ast.For(target, niter, body, orelse, type_comment)
    
        getExpr = ast.Call(ast.Attribute(ast.Name('ray'),
                                        'get'),
                            [ast.Name(remoteList)],
                            [])
        getStmt = ast.Assign([ast.Name(remoteList)], getExpr)

        return remoteList, [listInitStmt, loopStmt, getStmt]

    def getSeqLoopStmt(self, loop, seq, takes):
        # for loopIdx, ... in enumerate(iter):
        #     ... = remoteList_i[loopIdx]
        #     ...
        #     orignal seqs

        assert(isinstance(loop, ast.For))
        loopIdx = 'loop_idx_' + str(self.loopCnt)
        self.loopCnt += 1

        # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
        target = ast.Tuple([ast.Name(loopIdx), loop.target])
        niter = ast.Call(ast.Name('enumerate'), [loop.iter], [])
        
        body = [self.getTakeStmt(rmt, wtv, loopIdx) for rmt, wtv in takes] + \
                [node for node in seq if isinstance(node, ast.stmt)]

        orelse = loop.orelse
        type_comment = loop.type_comment

        loopStmt = ast.For(target, niter, body, orelse, type_comment)

        return loopStmt

    def getParallelSeqs(self, sccStmtList):
        self.parallelSeqs = []
        # List of (seq, paraStartIdx)

        curSeq = []
        paraStartIdx = None
        isPar = True
        for idx, scc in enumerate(sccStmtList):
            if scc[0] not in self.parallelizable:
                if isinstance(scc[0], ast.expr):
                    continue
                if not isPar:
                    curSeq += scc
                else:
                    if len(curSeq) >= 1:
                        self.parallelSeqs.append((curSeq, paraStartIdx))
                    curSeq = [u for u in scc]
                    paraStartIdx = None
                    isPar = False
            else:
                if (isinstance(scc[0], ast.expr)
                    and scc[0] not in self.extensiable):
                    continue
                if isPar and idx != 0:
                    curSeq += scc
                else:
                    paraStartIdx = len(curSeq)
                    curSeq += scc
                    isPar = True
        
        if len(curSeq) >= 1:
            self.parallelSeqs.append((curSeq, paraStartIdx))
        
    def getReadWrite(self, seq):
        Read = self.Read
        Write = self.Write
        readVars, writeVars = set(), set()
        for stmt in seq:
            for rd in Read[stmt]:
                if rd not in writeVars:
                    readVars.add(rd)
            writeVars |= Write[stmt]
        readVars -= set({'stdin', 'stdout'})
        writeVars -= set({'stdin', 'stdout'})
        return readVars, writeVars
    
class ConcurrentLoopRewriter:
    def __init__(self, funcDef, seq, sccStmtList, loop, parallelizable, Read, Write, executorCls='thread', max_workers = 10):
        assert(isinstance(funcDef, ast.FunctionDef))
        self.funcDef = funcDef

        self.nodes = seq
        self.nodeSet = set(seq)
        self.parallelizable = parallelizable
        
        # counters for generating names
        self.funcCnt = 0
        self.loopCnt = 0
        self.exprTmpCnt = 0

        assert(executorCls == 'thread' or executorCls == 'process')
        self.executorCls = executorCls
        self.max_workers = max_workers
        self.parallel_executor = 'parallel_executor'

        self.Read = Read
        self.Write = Write

        assert(isinstance(loop, ast.For))

        self.getExtensiable()
        self.getParallelSeqs(sccStmtList)

        self.rewrite(loop)

    def rewrite(self, loop): 
        self.parallelFuncDefs = []
        takes = []
        resSeq = []
        
        # the write variable is useful only if it can be readed by following loops
        followingReads = self.getFollowingReads(self.parallelSeqs)
        for (seq, paraStartIdx), followRds in zip(self.parallelSeqs, followingReads):
            if paraStartIdx != None:
                readVars, writeVars = self.getReadWrite(seq)

                paraSeq = seq[paraStartIdx:]
                nonParaSeq = seq[:paraStartIdx]
                paraReads, paraWrites = self.getReadWrite(paraSeq)

                wtVars, funcDef = self.getFuncDef(paraSeq, paraReads, paraWrites & followRds)
                
                nonParaWrites = list((set(writeVars) - set(wtVars)) & followRds)

                rmt, stmts = self.getParaLoopStmt(loop, nonParaSeq, funcDef.name, nonParaWrites, paraReads, takes)

                self.parallelFuncDefs.append(funcDef)
                resSeq += stmts

                takes.append((rmt, nonParaWrites + wtVars))
            else:
                # non-parallel loop is always the last one
                loopStmt = self.getSeqLoopStmt(loop, seq, takes)
                resSeq.append(loopStmt)
        
        initStmt = self.getInitStmt()
        resSeq = [initStmt] + resSeq

        if hasattr(loop, 'p') and hasattr(loop, 'br'):
            p, br = loop.p, loop.br
            attr = getattr(p, br)

            assert (isinstance(attr, list))
            idx = attr.index(loop)
            setattr(p, br, attr[:idx] + resSeq + attr[idx+1:])

        self.funcDef.name = self.funcDef.name + '_' + self.executorCls

    def getFollowingReads(self, parallelSeqs):
        followingReads = []
        curSeq = []
        for seq, paraStartIdx in reversed(parallelSeqs):
            rd, wt = self.getReadWrite(curSeq)
            followingReads.append(rd)
            curSeq += seq
        return list(reversed(followingReads))

    def getExtensiable(self):
        self.extensiable = set()
        for u in self.nodes:
            if (isinstance(u, ast.expr) 
                and u in self.parallelizable):
                pNode = u.p
                while pNode not in self.nodeSet:
                    pNode = pNode.p
                if pNode not in self.parallelizable:
                    self.extensiable.add(u)
    
    def getFuncDef(self, seq, readVars, writeVars):
        funcName = self.funcDef.name + '_parallel_func_' + str(self.funcCnt)
        self.funcCnt += 1

        tmpVarList = []
        body = []
        for node in seq:
            if isinstance(node, ast.expr):
                tmpVar = 'expr_tmp_' + str(self.exprTmpCnt)
                self.exprTmpCnt += 1
                tmpVarList.append(tmpVar)
                stmt = ast.Assign([ast.Name(tmpVar)], node, None)

                p, br = node.p, node.br
                attr = getattr(p, br)
                if isinstance(attr, list):
                    idx = attr.index(node)
                    attr[idx] = ast.Name(tmpVar)
                else:
                    setattr(p, br, ast.Name(tmpVar))

            else:
                stmt = node
            body.append(stmt)
        
        rtStmt = ast.Return(
                    ast.Tuple([ast.Name(wt) for wt in tmpVarList + list(writeVars)]))                
        body.append(rtStmt)

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
        
        return tmpVarList + list(writeVars), funcDef
    
    def getTakeStmt(self, remoteList, writeVars, loopIdx):
        # targets, ... = remoteList[loopIdx]
        target = ast.Tuple([ast.Name(wt) for wt in writeVars])
        if len(writeVars) == 0:
            target = ast.Name('_')
        value = ast.Subscript(ast.Name(remoteList), ast.Index(ast.Name(loopIdx)))
        takeStmt = ast.Assign([target], value)
        return takeStmt

    def getParaLoopStmt(self, loop, nonParaSeq, funcName, nonParaWrites, paraReads, takes):
        # remoteList = []
        # for loopIdx, ... in enumerate(iter):
        #     ... = remoteList_i[loopIdx]
        #     ...
        #     nonParaSeqs
        #     remoteList.append([nonParaWrites] + parallelFunc.remote(...))
        # remoteList = ray.get(remoteList)

        assert(isinstance(loop, ast.For))

        remoteList = 'remote_list_' + str(self.loopCnt)
        loopIdx = 'loop_idx_' + str(self.loopCnt)
        self.loopCnt += 1

        listInitStmt = ast.Assign([ast.Name(remoteList)], ast.List([]))
        
        # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
        target = ast.Tuple([ast.Name(loopIdx), loop.target])
        niter = ast.Call(ast.Name('enumerate'), [loop.iter], [])

        # remoteList.append([nonParaWrites] + parallelFunc.remote(...))
        callExpr = ast.Call(
                        ast.Attribute(
                                ast.Name(self.parallel_executor),
                                'submit'), 
                            [ast.Name(funcName)] + [ast.Name(rd) for rd in paraReads],
                            [])
        if len(nonParaWrites) > 0:
            wtVarsExpr = ast.BinOp(
                            left=ast.Tuple([ast.Name(wt) for wt in nonParaWrites]), 
                            op=ast.Add(), 
                            right=ast.Tuple(
                                [callExpr]))
        else:
            wtVarsExpr = ast.Tuple(
                            [callExpr])
        appendStmt = ast.Call(ast.Attribute(ast.Name(remoteList),
                                            'append'),
                            [wtVarsExpr],
                            [])
        appendStmt = ast.Expr(appendStmt)

        body = [self.getTakeStmt(rmt, wtv, loopIdx) for rmt, wtv in takes] + \
                [stmt for stmt in nonParaSeq] + \
                [appendStmt]

        orelse = loop.orelse
        type_comment = loop.type_comment

        loopStmt = ast.For(target, niter, body, orelse, type_comment)
        
        getExpr = ast.ListComp(
                    ast.BinOp(
                        left=ast.Subscript(
                            ast.Name('tmp'), 
                            ast.Slice(
                                None, 
                                ast.UnaryOp(
                                    ast.USub(), 
                                    ast.Constant(1, kind=None)), 
                                None)), 
                        op = ast.Add(), 
                        right=ast.Call(
                            ast.Attribute(
                                ast.Subscript(
                                    ast.Name(id='tmp'), 
                                    ast.Index(
                                        ast.UnaryOp(
                                            ast.USub(), 
                                            ast.Constant(1, kind=None)))), 
                                'result'),
                            [],
                            [])),
                    [ast.comprehension(
                        ast.Name('tmp'), 
                        ast.Name(remoteList),
                        [])])
        getStmt = ast.Assign([ast.Name(remoteList)], getExpr)

        return remoteList, [listInitStmt, loopStmt, getStmt]

    def getSeqLoopStmt(self, loop, seq, takes):
        # for loopIdx, ... in enumerate(iter):
        #     ... = remoteList_i[loopIdx]
        #     ...
        #     orignal seqs

        assert(isinstance(loop, ast.For))
        loopIdx = 'loop_idx_' + str(self.loopCnt)
        self.loopCnt += 1

        # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
        target = ast.Tuple([ast.Name(loopIdx), loop.target])
        niter = ast.Call(ast.Name('enumerate'), [loop.iter], [])
        
        body = [self.getTakeStmt(rmt, wtv, loopIdx) for rmt, wtv in takes] + \
                [node for node in seq if isinstance(node, ast.stmt)]

        orelse = loop.orelse
        type_comment = loop.type_comment

        loopStmt = ast.For(target, niter, body, orelse, type_comment)

        return loopStmt

    def getParallelSeqs(self, sccStmtList):
        self.parallelSeqs = []
        # List of (seq, paraStartIdx)

        curSeq = []
        paraStartIdx = None
        isPar = True
        for idx, scc in enumerate(sccStmtList):
            if scc[0] not in self.parallelizable:
                if isinstance(scc[0], ast.expr):
                    continue
                if not isPar:
                    curSeq += scc
                else:
                    if len(curSeq) >= 1:
                        self.parallelSeqs.append((curSeq, paraStartIdx))
                    curSeq = [u for u in scc]
                    paraStartIdx = None
                    isPar = False
            else:
                if (isinstance(scc[0], ast.expr)
                    and scc[0] not in self.extensiable):
                    continue
                if isPar and idx != 0:
                    curSeq += scc
                else:
                    paraStartIdx = len(curSeq)
                    curSeq += scc
                    isPar = True
        
        if len(curSeq) >= 1:
            self.parallelSeqs.append((curSeq, paraStartIdx))
        
    def getReadWrite(self, seq):
        Read = self.Read
        Write = self.Write
        readVars, writeVars = set(), set()
        for stmt in seq:
            for rd in Read[stmt]:
                if rd not in writeVars:
                    readVars.add(rd)
            writeVars |= Write[stmt]
        readVars -= set({'stdin', 'stdout'})
        writeVars -= set({'stdin', 'stdout'})
        return readVars, writeVars
    
    def getInitStmt(self):
        poolExecutor = 'ThreadPoolExecutor' if self.executorCls == 'thread' else 'ProcessPoolExecutor'
        assignStmt = ast.Assign(
                        [ast.Name(self.parallel_executor)], 
                        ast.Call(
                            ast.Name(poolExecutor), 
                            [], 
                            [ast.keyword(
                                'max_workers', 
                                ast.Constant(self.max_workers, kind=None))]))
        return assignStmt

class ThreadLoopRewriter(ConcurrentLoopRewriter):
    def __init__(self, funcDef, seq, sccStmtList, loop, parallelizable, Read, Write, max_workers=10):
        super().__init__(funcDef, seq, sccStmtList, loop, parallelizable, Read, Write, 'thread', max_workers)

class ProcessLoopRewriter(ConcurrentLoopRewriter):
    def __init__(self, funcDef, seq, sccStmtList, loop, parallelizable, Read, Write, max_workers=10):
        super().__init__(funcDef, seq, sccStmtList, loop, parallelizable, Read, Write, 'process', max_workers)

class RayBlockedLoopRewriter:
    def __init__(self, funcDef, seq, sccStmtList, loop, parallelizable, Read, Write):
        assert(isinstance(funcDef, ast.FunctionDef))
        self.funcDef = funcDef

        self.nodes = seq
        self.nodeSet = set(seq)
        self.parallelizable = parallelizable
        
        # counters for generating names
        self.funcCnt = 0
        self.loopCnt = 0
        self.exprTmpCnt = 0

        self.Read = Read
        self.Write = Write

        assert(isinstance(loop, ast.For))

        self.getExtensiable()
        self.getParallelSeqs(sccStmtList)

        self.rewrite(loop)

    def rewrite(self, loop): 
        self.parallelFuncDefs = []
        takes = []
        resSeq = []
        
        rmt, initStmts = self.getInitStmts(loop.iter)
        wtv = set(map(lambda x: x.strip(' '), getstr(loop.target).strip(' \n()').split(',')))

        takes.append((rmt, wtv))

        # the write variable is useful only if it can be readed by following loops
        followingReads = self.getFollowingReads(self.parallelSeqs)        
        len_parallelSeqs = len(self.parallelSeqs)
        for idx, ((seq, paraStartIdx), followRds) in enumerate(zip(self.parallelSeqs, followingReads)):
            readVars, writeVars = self.getReadWrite(seq)
            #print('-' * 50)
            #print(paraStartIdx)
            #for stmt in seq:
            #    print(getstr(stmt))
            if paraStartIdx != None:
                wtVars, funcDef = self.getFuncDef(seq, takes, writeVars & followRds)

                rmt, stmts = self.getParaLoopStmt(funcDef.name, takes)

                self.parallelFuncDefs.append(funcDef)
                resSeq += stmts

                takes.append((rmt, wtVars))
            else:
                if idx == len_parallelSeqs - 1:
                    loopStmt = self.getLastSeqLoopStmt(loop, seq, takes)
                    resSeq.append(loopStmt)
                else:
                    rmt, stmts = self.getSeqLoopStmt(loop, seq, takes, writeVars & followRds)
                    resSeq += stmts

                    takes.append((rmt, list(writeVars & followRds)))

        resSeq = initStmts + resSeq


        if hasattr(loop, 'p') and hasattr(loop, 'br'):
            p, br = loop.p, loop.br
            attr = getattr(p, br)

            assert (isinstance(attr, list))
            idx = attr.index(loop)
            setattr(p, br, attr[:idx] + resSeq + attr[idx+1:])

        self.funcDef.name = self.funcDef.name + '_ray'

    def getFollowingReads(self, parallelSeqs):
        followingReads = []
        curSeq = []
        for seq, paraStartIdx in reversed(parallelSeqs):
            rd, wt = self.getReadWrite(curSeq)
            followingReads.append(rd)
            curSeq += seq
        return list(reversed(followingReads))

    def getExtensiable(self):
        self.extensiable = set()
        for u in self.nodes:
            if (isinstance(u, ast.expr) 
                and u in self.parallelizable):
                pNode = u.p
                while pNode not in self.nodeSet:
                    pNode = pNode.p
                if pNode not in self.parallelizable:
                    self.extensiable.add(u)
    
    def getInitStmts(self, iter):
        # remoteLst0 = list(iter)
        # totalLength = len(remoteLst0)
        # BlockLength = totalLenght // NUM_BLOCK
        # while BlockLength * NUM_BLOCK < totalLength:
        #     BlockLength += 1

        self.BlockLength = 'BlockLength'

        remoteList = 'remote_list_' + str(self.loopCnt)
        self.loopCnt += 1
        
        rmtInitStmt = ast.Assign(
                        [ast.Name(remoteList)],
                        ast.Call(
                            ast.Name('list'),
                            [iter],
                            []))
        lengthStmt = ast.Assign(
                        [ast.Name('totalLength')],
                        ast.Call(
                            ast.Name('len'),
                            [ast.Name(remoteList)],
                            []))
                
        calcBlockLengthCode = '''BlockLength = totalLength // ''' + str(NUM_BLOCK) + '''
while BlockLength * ''' + str(NUM_BLOCK) + ''' < totalLength:
    BlockLength += 1'''

        initStmts = ast.parse(calcBlockLengthCode).body

        return remoteList, [rmtInitStmt, lengthStmt] + initStmts

    def getFuncDef(self, seq, takes, writeVars):
        # def parallel_func(remoteList_0 ...):
        #     rtLst = []
        #     for loopIdx in range(len(remoteList_0)):
        #         ... = remote_Lst_i[loopIdx]
        #         parallelStmts
        #         rtLst.append(wts)
        #     return rtLst

        funcName = self.funcDef.name + '_parallel_func_' + str(self.funcCnt)
        self.funcCnt += 1

        rtLst = 'rtLst'
        initStmt = ast.Assign(
                        [ast.Name(rtLst)],
                        ast.List([]))
        
        loopIdx = 'loopIdx'
        takeStmts = [self.getTakeStmt(rmt, wtv, loopIdx) for rmt, wtv in takes]
        
        tmpVarList = []
        bodyStmts = []
        for node in seq:
            if isinstance(node, ast.expr):
                tmpVar = 'expr_tmp_' + str(self.exprTmpCnt)
                self.exprTmpCnt += 1
                tmpVarList.append(tmpVar)
                stmt = ast.Assign([ast.Name(tmpVar)], node, None)

                p, br = node.p, node.br
                attr = getattr(p, br)
                if isinstance(attr, list):
                    idx = attr.index(node)
                    attr[idx] = ast.Name(tmpVar)
                else:
                    setattr(p, br, ast.Name(tmpVar))
            else:
                stmt = node
            bodyStmts.append(stmt)
        
        appendStmt = ast.Expr(
                        ast.Call(
                            ast.Attribute(
                                ast.Name(rtLst),
                                'append'),
                            [ast.Tuple(
                                [ast.Name(wt) for wt in tmpVarList + list(writeVars)])],
                            []))
        
        loopBody = takeStmts + bodyStmts + [appendStmt]

        rmt0 = takes[0][0]
        iterExpr = ast.Call(ast.Name('range'),
                            [ast.Call(
                                ast.Name('len'),
                                [ast.Name(rmt0)],
                                [])],
                            [])

        #For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
        forStmt = ast.For(
                    ast.Name(loopIdx),
                    iterExpr,
                    loopBody,
                    [],
                    None)

        rtStmt = ast.Return(
                    ast.Name(rtLst))               
        

        args = ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(
                                rmt,
                                annotation = None,
                                type_comment = None) 
                            for rmt, wtv in takes], 
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults = [])

        body = [initStmt, forStmt, rtStmt]

        funcDef = ast.FunctionDef(funcName, args, body, [])
        
        return tmpVarList + list(writeVars), funcDef
    
    def getTakeStmt(self, remoteList, writeVars, loopIdx):
        # targets, ... = remoteList[loopIdx]
        target = ast.Tuple([ast.Name(wt) for wt in writeVars])
        if len(writeVars) == 0:
            target = ast.Name('_')
        value = ast.Subscript(ast.Name(remoteList), ast.Index(ast.Name(loopIdx)))
        takeStmt = ast.Assign([target], value)
        return takeStmt

    def getParaLoopStmt(self, funcName, takes):
        # remoteLst = [
        #       parallel_func.remote(
        #           rmt_i[i * BlockLength: (i + 1) * BlockLength] ...) 
        #           for i in range(NUM_BLOCK)]
        #
        # rmtTmp = ray.get(remoteLst)
        # remoteLst = []
        # for tmp in rmtTmp:
        #     remoteLst += ray.get(tmp)

        remoteList = 'remote_list_' + str(self.loopCnt)
        self.loopCnt += 1


        args = [ast.parse(rmt + '[i * ' + self.BlockLength + ': (i + 1) * ' + self.BlockLength + ']').body[0].value
                    for rmt, wtv in takes]

        assignStmt = ast.Assign(
                        [ast.Name(remoteList)],
                        ast.ListComp(
                            ast.Call(
                                ast.Attribute(
                                    ast.Call(
                                        ast.Attribute(ast.Name(
                                            'ray'), 
                                            'remote'),
                                        [ast.Name(funcName)],
                                        []), 
                                    'remote'),
                                args,
                                []),
                            [ast.comprehension(
                                ast.Name('i'), 
                                ast.Call(
                                    ast.Name('range'),
                                    [ast.Name(str(NUM_BLOCK))],
                                    []),
                                [])]))
        
        getCode = '''rmtTmp = ray.get(''' + remoteList + ''')
''' + remoteList + ''' = []
for tmp in rmtTmp:
    ''' + remoteList + ''' += tmp'''
        getStmts = ast.parse(getCode).body

        return remoteList, [assignStmt] + getStmts

    def getLastSeqLoopStmt(self, loop, seq, takes):
        # last seq loop, don't need to prepare remoteList for subsequent
        # for loopIdx, ... in enumerate(iter):
        #     ... = remoteList_i[loopIdx]
        #     ...
        #     orignal seqs

        assert(isinstance(loop, ast.For))
        loopIdx = 'loop_idx_' + str(self.loopCnt)
        self.loopCnt += 1

        # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
        target = ast.Tuple([ast.Name(loopIdx), loop.target])
        niter = ast.Call(ast.Name('enumerate'), [loop.iter], [])
        
        body = [self.getTakeStmt(rmt, wtv, loopIdx) for rmt, wtv in takes] + \
                [node for node in seq if isinstance(node, ast.stmt)]

        orelse = loop.orelse
        type_comment = loop.type_comment

        loopStmt = ast.For(target, niter, body, orelse, type_comment)

        return loopStmt

    def getSeqLoopStmt(self, loop, seq, takes, writeVars):
        # prepare_seq_loop
        # remoteList = []
        # for loopIdx, ... in enumerate(iter):
        #     ... = remoteList_i[loopIdx]
        #     ...
        #     orignal seqs
        #     remoteList.append(...)

        assert(isinstance(loop, ast.For))

        remoteList = 'remote_list_' + str(self.loopCnt)
        loopIdx = 'loop_idx_' + str(self.loopCnt)
        self.loopCnt += 1

        listInitStmt = ast.Assign([ast.Name(remoteList)], ast.List([]))
        
        # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
        target = ast.Tuple([ast.Name(loopIdx), loop.target])
        niter = ast.Call(ast.Name('enumerate'), [loop.iter], [])
        
        appendStmt = ast.Call(ast.Attribute(ast.Name(remoteList),
                                            'append'),
                            [ast.Tuple([ast.Name(var) for var in writeVars])],
                            [])
        appendStmt = ast.Expr(appendStmt)

        body = [self.getTakeStmt(rmt, wtv, loopIdx) for rmt, wtv in takes] + \
                [node for node in seq if isinstance(node, ast.stmt)] + \
                [appendStmt]

        orelse = loop.orelse
        type_comment = loop.type_comment

        loopStmt = ast.For(target, niter, body, orelse, type_comment)

        return remoteList, [listInitStmt, loopStmt]

    def getParallelSeqs(self, sccStmtList):
        self.parallelSeqs = []
        # List of (seq, paraStartIdx)

        curSeq = []
        paraStartIdx = None
        isPar = True
        for idx, scc in enumerate(sccStmtList):
            if scc[0] not in self.parallelizable:
                if isinstance(scc[0], ast.expr):
                    continue
                if not isPar:
                    curSeq += scc
                else:
                    if len(curSeq) >= 1:
                        self.parallelSeqs.append((curSeq, paraStartIdx))
                    curSeq = [u for u in scc]
                    paraStartIdx = None
                    isPar = False
            else:
                if (isinstance(scc[0], ast.expr)
                    and scc[0] not in self.extensiable):
                    continue
                if isPar and idx != 0:
                    curSeq += scc
                else:
                    paraStartIdx = len(curSeq)
                    curSeq += scc
                    isPar = True
        
        if len(curSeq) >= 1:
            self.parallelSeqs.append((curSeq, paraStartIdx))
    
    
    def getReadWrite(self, seq):
        Read = self.Read
        Write = self.Write
        readVars, writeVars = set(), set()
        for stmt in seq:
            for rd in Read[stmt]:
                if rd not in writeVars:
                    readVars.add(rd)
            writeVars |= Write[stmt]
        readVars -= set({'stdin', 'stdout'})
        writeVars -= set({'stdin', 'stdout'})
        return readVars, writeVars
   
class ConcurrentBlockedLoopRewriter:
    def __init__(self, funcDef, seq, sccStmtList, loop, parallelizable, Read, Write, executorCls = 'thread'):
        assert(isinstance(funcDef, ast.FunctionDef))
        self.funcDef = funcDef

        self.nodes = seq
        self.nodeSet = set(seq)
        self.parallelizable = parallelizable
        
        # counters for generating names
        self.funcCnt = 0
        self.loopCnt = 0
        self.exprTmpCnt = 0

        self.Read = Read
        self.Write = Write

        assert(executorCls == 'thread' or executorCls == 'process')
        self.executorCls = executorCls
        self.parallel_executor = 'parallel_executor'

        assert(isinstance(loop, ast.For))

        self.getExtensiable()
        self.getParallelSeqs(sccStmtList)

        self.rewrite(loop)

    def rewrite(self, loop): 
        self.parallelFuncDefs = []
        takes = []
        resSeq = []
        
        rmt, initStmts = self.getInitStmts(loop.iter)
        wtv = set(map(lambda x: x.strip(' '), getstr(loop.target).strip(' \n()').split(',')))

        takes.append((rmt, wtv))

        # the write variable is useful only if it can be readed by following loops
        followingReads = self.getFollowingReads(self.parallelSeqs)        
        len_parallelSeqs = len(self.parallelSeqs)
        for idx, ((seq, paraStartIdx), followRds) in enumerate(zip(self.parallelSeqs, followingReads)):
            readVars, writeVars = self.getReadWrite(seq)
            #print('-' * 50)
            #print(paraStartIdx)
            #for stmt in seq:
            #    print(getstr(stmt))
            if paraStartIdx != None:
                wtVars, funcDef = self.getFuncDef(seq, takes, writeVars & followRds)

                rmt, stmts = self.getParaLoopStmt(funcDef.name, takes)

                self.parallelFuncDefs.append(funcDef)
                resSeq += stmts

                takes.append((rmt, wtVars))
            else:
                if idx == len_parallelSeqs - 1:
                    loopStmt = self.getLastSeqLoopStmt(loop, seq, takes)
                    resSeq.append(loopStmt)
                else:
                    rmt, stmts = self.getSeqLoopStmt(loop, seq, takes, writeVars & followRds)
                    resSeq += stmts

                    takes.append((rmt, list(writeVars & followRds)))

        resSeq = initStmts + resSeq


        if hasattr(loop, 'p') and hasattr(loop, 'br'):
            p, br = loop.p, loop.br
            attr = getattr(p, br)

            assert (isinstance(attr, list))
            idx = attr.index(loop)
            setattr(p, br, attr[:idx] + resSeq + attr[idx+1:])

        self.funcDef.name = self.funcDef.name + '_' + self.executorCls

    def getFollowingReads(self, parallelSeqs):
        followingReads = []
        curSeq = []
        for seq, paraStartIdx in reversed(parallelSeqs):
            rd, wt = self.getReadWrite(curSeq)
            followingReads.append(rd)
            curSeq += seq
        return list(reversed(followingReads))

    def getExtensiable(self):
        self.extensiable = set()
        for u in self.nodes:
            if (isinstance(u, ast.expr) 
                and u in self.parallelizable):
                pNode = u.p
                while pNode not in self.nodeSet:
                    pNode = pNode.p
                if pNode not in self.parallelizable:
                    self.extensiable.add(u)
    
    def getInitStmts(self, iter):
        # remoteLst0 = list(iter)
        # totalLength = len(remoteLst0)
        # BlockLength = totalLenght // NUM_BLOCK
        # while BlockLength * NUM_BLOCK < totalLength:
        #     BlockLength += 1
        # parallel_executor = xxxPoolExecutor(max_workers=NUM_BLOCK)

        self.BlockLength = 'BlockLength'

        remoteList = 'remote_list_' + str(self.loopCnt)
        self.loopCnt += 1
        
        rmtInitStmt = ast.Assign(
                        [ast.Name(remoteList)],
                        ast.Call(
                            ast.Name('list'),
                            [iter],
                            []))
        lengthStmt = ast.Assign(
                        [ast.Name('totalLength')],
                        ast.Call(
                            ast.Name('len'),
                            [ast.Name(remoteList)],
                            []))
                
        calcBlockLengthCode = '''BlockLength = totalLength // ''' + str(NUM_BLOCK) + '''
while BlockLength * ''' + str(NUM_BLOCK) + ''' < totalLength:
    BlockLength += 1''' 

        initStmts = ast.parse(calcBlockLengthCode).body
        
        self.poolExecutor = 'ThreadPoolExecutor' if self.executorCls == 'thread' else 'ProcessPoolExecutor'
        assignStmt = ast.Assign(
                        [ast.Name(self.parallel_executor)], 
                        ast.Call(
                            ast.Name(self.poolExecutor), 
                            [], 
                            [ast.keyword(
                                'max_workers', 
                                ast.Constant(NUM_BLOCK, kind=None))]))

        return remoteList, [rmtInitStmt, lengthStmt] + initStmts + [assignStmt]

    def getFuncDef(self, seq, takes, writeVars):
        # def parallel_func(remoteList_0 ...):
        #     rtLst = []
        #     for loopIdx in range(len(remoteList_0)):
        #         ... = remote_Lst_i[loopIdx]
        #         parallelStmts
        #         rtLst.append(wts)
        #     return rtLst

        funcName = self.funcDef.name + '_parallel_func_' + str(self.funcCnt)
        self.funcCnt += 1

        rtLst = 'rtLst'
        initStmt = ast.Assign(
                        [ast.Name(rtLst)],
                        ast.List([]))
        
        loopIdx = 'loopIdx'
        takeStmts = [self.getTakeStmt(rmt, wtv, loopIdx) for rmt, wtv in takes]
        
        tmpVarList = []
        bodyStmts = []
        for node in seq:
            if isinstance(node, ast.expr):
                tmpVar = 'expr_tmp_' + str(self.exprTmpCnt)
                self.exprTmpCnt += 1
                tmpVarList.append(tmpVar)
                stmt = ast.Assign([ast.Name(tmpVar)], node, None)

                p, br = node.p, node.br
                attr = getattr(p, br)
                if isinstance(attr, list):
                    idx = attr.index(node)
                    attr[idx] = ast.Name(tmpVar)
                else:
                    setattr(p, br, ast.Name(tmpVar))
            else:
                stmt = node
            bodyStmts.append(stmt)
        
        appendStmt = ast.Expr(
                        ast.Call(
                            ast.Attribute(
                                ast.Name(rtLst),
                                'append'),
                            [ast.Tuple(
                                [ast.Name(wt) for wt in tmpVarList + list(writeVars)])],
                            []))
        
        loopBody = takeStmts + bodyStmts + [appendStmt]

        rmt0 = takes[0][0]
        iterExpr = ast.Call(ast.Name('range'),
                            [ast.Call(
                                ast.Name('len'),
                                [ast.Name(rmt0)],
                                [])],
                            [])

        #For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
        forStmt = ast.For(
                    ast.Name(loopIdx),
                    iterExpr,
                    loopBody,
                    [],
                    None)

        rtStmt = ast.Return(
                    ast.Name(rtLst))               
        

        args = ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(
                                rmt,
                                annotation = None,
                                type_comment = None) 
                            for rmt, wtv in takes], 
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults = [])

        body = [initStmt, forStmt, rtStmt]

        funcDef = ast.FunctionDef(funcName, args, body, [])
        
        return tmpVarList + list(writeVars), funcDef
    
    def getTakeStmt(self, remoteList, writeVars, loopIdx):
        # targets, ... = remoteList[loopIdx]
        target = ast.Tuple([ast.Name(wt) for wt in writeVars])
        if len(writeVars) == 0:
            target = ast.Name('_')
        value = ast.Subscript(ast.Name(remoteList), ast.Index(ast.Name(loopIdx)))
        takeStmt = ast.Assign([target], value)
        return takeStmt

    def getParaLoopStmt(self, funcName, takes):
        # remoteLst = [
        #       parallel_func.remote(
        #           rmt_i[i * BlockLength: (i + 1) * BlockLength] ...) 
        #           for i in range(NUM_BLOCK)]
        #
        # remoteLst = ray.get(remoteLst)
        
        remoteList = 'remote_list_' + str(self.loopCnt)
        self.loopCnt += 1


        args = [ast.parse(rmt + '[i * ' + self.BlockLength + ': (i + 1) * ' + self.BlockLength + ']').body[0].value
                    for rmt, wtv in takes]

        assignStmt = ast.Assign(
                        [ast.Name(remoteList)],
                        ast.ListComp(
                            ast.Call(
                                ast.Attribute(
                                    ast.Name(self.parallel_executor),
                                    'submit'),
                                [ast.Name(funcName)] + args,
                                []),
                            [ast.comprehension(
                                ast.Name('i'), 
                                ast.Call(
                                    ast.Name('range'),
                                    [ast.Name(str(NUM_BLOCK))],
                                    []),
                                [])]))
        
        getCode = '''rmtTmp = ''' + remoteList + '''
''' + remoteList + ''' = []
for tmp in rmtTmp:
    ''' + remoteList + ''' += tmp.result()'''
        getStmts = ast.parse(getCode).body

        return remoteList, [assignStmt] + getStmts

    def getLastSeqLoopStmt(self, loop, seq, takes):
        # last seq loop, don't need to prepare remoteList for subsequent
        # for loopIdx, ... in enumerate(iter):
        #     ... = remoteList_i[loopIdx]
        #     ...
        #     orignal seqs

        assert(isinstance(loop, ast.For))
        loopIdx = 'loop_idx_' + str(self.loopCnt)
        self.loopCnt += 1

        # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
        target = ast.Tuple([ast.Name(loopIdx), loop.target])
        niter = ast.Call(ast.Name('enumerate'), [loop.iter], [])
        
        body = [self.getTakeStmt(rmt, wtv, loopIdx) for rmt, wtv in takes] + \
                [node for node in seq if isinstance(node, ast.stmt)]

        orelse = loop.orelse
        type_comment = loop.type_comment

        loopStmt = ast.For(target, niter, body, orelse, type_comment)

        return loopStmt

    def getSeqLoopStmt(self, loop, seq, takes, writeVars):
        # prepare_seq_loop
        # remoteList = []
        # for loopIdx, ... in enumerate(iter):
        #     ... = remoteList_i[loopIdx]
        #     ...
        #     orignal seqs
        #     remoteList.append(...)

        assert(isinstance(loop, ast.For))

        remoteList = 'remote_list_' + str(self.loopCnt)
        loopIdx = 'loop_idx_' + str(self.loopCnt)
        self.loopCnt += 1

        listInitStmt = ast.Assign([ast.Name(remoteList)], ast.List([]))
        
        # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
        target = ast.Tuple([ast.Name(loopIdx), loop.target])
        niter = ast.Call(ast.Name('enumerate'), [loop.iter], [])
        
        appendStmt = ast.Call(ast.Attribute(ast.Name(remoteList),
                                            'append'),
                            [ast.Tuple([ast.Name(var) for var in writeVars])],
                            [])
        appendStmt = ast.Expr(appendStmt)

        body = [self.getTakeStmt(rmt, wtv, loopIdx) for rmt, wtv in takes] + \
                [node for node in seq if isinstance(node, ast.stmt)] + \
                [appendStmt]

        orelse = loop.orelse
        type_comment = loop.type_comment

        loopStmt = ast.For(target, niter, body, orelse, type_comment)

        return remoteList, [listInitStmt, loopStmt]

    def getParallelSeqs(self, sccStmtList):
        self.parallelSeqs = []
        # List of (seq, paraStartIdx)

        curSeq = []
        paraStartIdx = None
        isPar = True
        for idx, scc in enumerate(sccStmtList):
            if scc[0] not in self.parallelizable:
                if isinstance(scc[0], ast.expr):
                    continue
                if not isPar:
                    curSeq += scc
                else:
                    if len(curSeq) >= 1:
                        self.parallelSeqs.append((curSeq, paraStartIdx))
                    curSeq = [u for u in scc]
                    paraStartIdx = None
                    isPar = False
            else:
                if (isinstance(scc[0], ast.expr)
                    and scc[0] not in self.extensiable):
                    continue
                if isPar and idx != 0:
                    curSeq += scc
                else:
                    paraStartIdx = len(curSeq)
                    curSeq += scc
                    isPar = True
        
        if len(curSeq) >= 1:
            self.parallelSeqs.append((curSeq, paraStartIdx))
    
    def getReadWrite(self, seq):
        Read = self.Read
        Write = self.Write
        readVars, writeVars = set(), set()
        for stmt in seq:
            for rd in Read[stmt]:
                if rd not in writeVars:
                    readVars.add(rd)
            writeVars |= Write[stmt]
        readVars -= set({'stdin', 'stdout'})
        writeVars -= set({'stdin', 'stdout'})
        return readVars, writeVars

class ThreadBlockedLoopRewriter(ConcurrentBlockedLoopRewriter):
    def __init__(self, funcDef, seq, sccStmtList, loop, parallelizable, Read, Write):
        super().__init__(funcDef, seq, sccStmtList, loop, parallelizable, Read, Write, 'thread')

class ProcessBlockedLoopRewriter(ConcurrentBlockedLoopRewriter):
    def __init__(self, funcDef, seq, sccStmtList, loop, parallelizable, Read, Write):
        super().__init__(funcDef, seq, sccStmtList, loop, parallelizable, Read, Write, 'process')


if __name__ == '__main__':
    import argparse
    import ast
    from pypar.basics.utils import slurp, getstr
    from pypar.basics.ReadWriteAnalyzer import ReadWriteAnalyzer
    from pypar.basics.LoopExtractor import LoopExtractor
    from pypar.basics.DependenceAnalyzer import DependenceAnalyzer
    from pypar.basics.LoopParallelizer import LoopParallelizer
    from pypar.basics.SequenceParallelizer import SequenceParallelizer
    from pypar.basics.ExprExtractor import ExprExtractor
    from pypar.basics.ParentExtractor import ParentExtractor

    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))
    
    filename = args.pythonfile.split('/')[-1]
    
    pe = ParentExtractor(root)
    rwa = ReadWriteAnalyzer(root)
    
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
        da.draw('graphs/' + filename + '.loop.' + str(i) + '.dg.png')
        
        lp = LoopParallelizer(nloop, da.dependence)

        lr = LoopRewriter(root, nseq, lp.sccStmtList, loop, lp.parallelizable, rwa.Readn, rwa.Writen)
        #print('=' * 50)
        #for ps in lr.parallelSeqs:
        #    print('-' * 30)
        #    for stmt in ps:
        #        print(getstr(stmt))

        #for stmt in lp.parallelizable:
        #    print(getstr(stmt))
        #for scc in lp.sccStmtList:
        #    print([getstr(stmt) for stmt in scc])

    #print(getstr(root))