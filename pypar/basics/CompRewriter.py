import ast
from pypar.basics.utils import getstr
from pypar.basics.config import PUTSIZE, NUM_BLOCK

class CompRewriter:
    def __init__(self, root, parallelizableComps, Read):
        self.root = root
        for i, comp in enumerate(parallelizableComps):
            funcDef = self.getFuncDef(i, comp.elt, Read[comp.elt])
            getExpr = self.getGetExpr(funcDef.name, comp, Read[comp.elt])
            
            putStmts = []
            readVars = Read[comp.elt] - self.getLoopVariables(comp)
            for var in readVars:
                putStmts.append(self.getPutStmt(var))
            self.rewrite(comp, funcDef, getExpr, putStmts)
            #print('='*50)
            #print(getstr(comp))
            #print('-'*30)
            #print(getstr(funcDef))
            #print('-'*30)
            #print(getstr(getExpr))
    def getFuncDef(self, id, elt, readVars):
        funcName = 'comp_parallel_func_' + str(id)
        
        rtExpr = elt
        rtStmt = ast.Return(elt)
        body = [rtStmt]

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
        
        decorator_list = [ast.Attribute(ast.Name('ray'), attr='remote')]

        funcDef = ast.FunctionDef(funcName, args, body, decorator_list)
        
        return funcDef
    def getGetExpr(self, funcName, comp, readVars):
        # ListComp(expr elt, comprehension* generators)
        elt = ast.Call(
                ast.Attribute(ast.Name(funcName), 'remote'), 
                [ast.Name(rd) for rd in readVars],
                [])
        
        compStmt = ast.ListComp(elt, comp.generators)
        getStmt = ast.Call(
                ast.Attribute(ast.Name('ray'), 'get'), 
                [compStmt],
                [])

        return getStmt
    
    def rewrite(self, comp, funcDef, getExpr, putStmts):
        self.insertStmts(comp, putStmts + [funcDef])
        self.replaceComp(comp, getExpr)
    def replaceComp(self, comp, getExpr):
        p, br = comp.p, comp.br
        attr = getattr(p, br)
        if isinstance(attr, list):
            idx = attr.index(comp)
            attr[idx] = getExpr
        else:
            setattr(p, br, getExpr)

    def getParStmt(self, comp):
        u = comp
        while not isinstance(u, ast.stmt):
            u = u.p
        return u

    def insertStmts(self, comp, stmts):
        pStmt = self.getParStmt(comp)
        p, br = pStmt.p, pStmt.br
        stmtList = getattr(p, br)
        assert(isinstance(stmtList, list))

        idx = stmtList.index(pStmt)
        for stmt in stmts:
            stmtList.insert(idx, stmt)

    def getPutStmt(self, var):
        getSizeExpr = ast.Call(ast.Attribute(ast.Name('sys'), 'getsizeof'), 
                            [ast.Name(var)], 
                            [])
        getClassExpr = ast.Call(ast.Name('isinstance'),
                                [ast.Name(var),
                                    ast.Attribute(ast.Attribute(ast.Name('ray'), 
                                                                '_raylet'),
                                                    'ObjectRef')],
                                [])
        testSizeExpr = ast.Compare(getSizeExpr, 
                                [ast.Gt()], 
                                [ast.Constant(PUTSIZE, '')])
        testClassExpr = ast.UnaryOp(ast.Not(), getClassExpr)
        testExpr = ast.BoolOp(ast.And(), [testClassExpr, testSizeExpr])
        
        putExpr = ast.Call(ast.Attribute(ast.Name('ray'), 
                                        'put'),
                            [ast.Name(var)],
                            [])
        assignStmt = ast.Assign([ast.Name(var)],
                                putExpr,
                                None)
        putStmt = ast.If(testExpr, 
                        [assignStmt],
                        [])
        return putStmt

    def getVars(self, expr):
        if isinstance(expr, ast.Name):
            return set({expr.id})
        elif isinstance(expr, ast.Tuple):
            res = set()
            for u in expr.elts:
                res |= self.getVars(u)
            return res
        else:
            raise    
    def getLoopVariables(self, comp):
        loopVars = set()
        for g in comp.generators:
            loopVars |= self.getVars(g.target)
        return loopVars

    def code(self):
        return getstr(self.root)

class BlockedCompRewriter:
    def __init__(self, comp, Read):
        lst = comp.generators[0].iter
        readVars = Read[comp.elt] - self.getLoopVariables(comp)

        funcName, funcDef = self.getFuncDef(comp, readVars)
        getBlockLengthStmt, getLstsStmt = self.getLstsStmt(lst)
        getStmt, mergeInitStmt, mergeForStmt = self.getGetStmt(funcName, readVars)

        self.stmtList = [funcDef, getBlockLengthStmt, getLstsStmt, getStmt, mergeInitStmt, mergeForStmt]
    def getLstsStmt(self, lst):
        # blockLength = len(lst) / NUM_BLOCK
        getBlockLengthStmt = ast.Assign(
                                targets=[ast.Name('blockLength')], 
                                value=ast.BinOp(
                                        left=ast.Call(
                                            func=ast.Name('len'), 
                                            args=[lst],
                                            keywords=[]),
                                        right=ast.Constant(NUM_BLOCK, kind=None),
                                        op=ast.FloorDiv()))
        # lsts = [lst[i*blockLength: (i+1)*blockLength] for i in range(NUM_BLOCK)]
        generators = [
            ast.comprehension(
                target=ast.Name('i'),
                iter=ast.Call(ast.Name('range'),
                            args=[ast.Constant(NUM_BLOCK, kind=None)],
                            keywords=[]),
                ifs=[])
        ]
        lstComp = ast.ListComp(elt=ast.Subscript(value=lst, 
                                                slice=ast.Slice(lower=ast.BinOp(left=ast.Name('blockLength'),
                                                                                right=ast.Name('i'),
                                                                                op=ast.Mult()),
                                                                upper=ast.BinOp(left=ast.Name('blockLength'),
                                                                                right=ast.BinOp(left=ast.Name('i'),
                                                                                                right=ast.Constant(1, kind=None),
                                                                                                op=ast.Add()),
                                                                                op=ast.Mult()),
                                                                step=None)),
                                generators=generators)
        getLstsStmt = ast.Assign(targets=[ast.Name('lsts')],
                                    value=lstComp)
        
        return getBlockLengthStmt, getLstsStmt

    def getFuncDef(self, comp, readVars):
        funcName = 'blocked_comp_parallel_func'
        
        ncomp = ast.ListComp(
                    elt=comp.elt,
                    generators=[ast.comprehension(
                                    target=comp.generators[0].target,
                                    iter=ast.Name('lst'),
                                    ifs=comp.generators[0].ifs)])
        rtStmt = ast.Return(ncomp)
        body = [rtStmt]

        args = ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(
                                rd,
                                annotation = None,
                                type_comment = None) 
                            for rd in readVars] +\
                         [ast.arg(
                                'lst',
                                annotation = None,
                                type_comment = None
                                    )], 
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults = [])
        
        decorator_list = [ast.Attribute(ast.Name('ray'), attr='remote')]

        funcDef = ast.FunctionDef(funcName, args, body, decorator_list)
        
        return funcName, funcDef

    def getGetStmt(self, funcName, readVars):
        listComp = ast.ListComp(
                        elt=ast.Call(
                                func=ast.Attribute(
                                            value=ast.Name(funcName), 
                                            attr='remote'),
                                args=[ast.Name(rd) for rd in list(readVars) + ['lst']],
                                keywords=[]),
                        generators=[ast.comprehension(
                                            target=ast.Name('lst'),
                                            iter=ast.Name('lsts'),
                                            ifs=[])])
        getStmt = ast.Assign(
                        targets=[ast.Name('ress')],
                        value=ast.Call(
                                func=ast.Attribute(
                                        value=ast.Name('ray'),
                                        attr='get'),
                                args=[listComp],
                                keywords=[]))
        mergeInitStmt = ast.Assign(
                            targets=[ast.Name('res')],
                            value=ast.List(elts=[]))
        mergeForStmt = ast.For(
                            target=ast.Name('lst'),
                            iter=ast.Name('ress'),
                            body=[
                                ast.AugAssign(
                                    target=ast.Name('res'),
                                    value=ast.Name('lst'),
                                    op=ast.Add())],
                            orelse=[])
        return getStmt, mergeInitStmt, mergeForStmt

    def getVars(self, expr):
        if isinstance(expr, ast.Name):
            return set({expr.id})
        elif isinstance(expr, ast.Tuple):
            res = set()
            for u in expr.elts:
                res |= self.getVars(u)
            return res
        else:
            raise    
    def getLoopVariables(self, comp):
        loopVars = set()
        for g in comp.generators:
            loopVars |= self.getVars(g.target)
        return loopVars

if __name__ == '__main__':
    import argparse
    from pypar.basics.utils import slurp, getstr
    from pypar.basics.ReadWriteAnalyzer import ReadWriteAnalyzer
    from pypar.basics.CompExtractor import CompExtractor
    from pypar.basics.CompParallelizer import CompParallelizer

    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))

    rwa = ReadWriteAnalyzer(root)
    ce = CompExtractor(root)
    cp = CompParallelizer(ce.comps, rwa.Read, rwa.Write)

    #for comp in cp.parallelizableComps:
    #    print(getstr(comp))

    #print()
    #print()

    from pypar.basics.ParentExtractor import ParentExtractor
    pe = ParentExtractor(root)
    cr = CompRewriter(root, cp.parallelizableComps, rwa.Readn)
    print(cr.code())