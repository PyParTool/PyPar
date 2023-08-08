import astunparse
import ast
from pypar.basics.utils import getstr

class DependenceAnalyzer:
    def __init__(self, node, Read, Write, kind = 'sequential'):
        self.dependence = set()
        if kind == 'sequential':
            self.stmtList = node
            self.sequential(node, Read, Write)
        elif kind == 'loop':
            loopStmt = node
            if isinstance(loopStmt, ast.While):
                self.stmtList = [loopStmt.test] + loopStmt.body
            elif isinstance(loopStmt, ast.For):
                self.stmtList = loopStmt.body
            else:
                raise
            self.loopVars = self.getLoopVariables(loopStmt)
            self.loop(loopStmt.body, Read, Write)
            if isinstance(loopStmt, ast.While):
                testStmt = loopStmt.test
                self.dependence.add((testStmt, testStmt))
        else:
            raise
    def sequential(self, stmtList, Read, Write):
        if len(stmtList) == 0: return
        wtin = {}
        for stmt in stmtList:
            for rd in Read[stmt]:
                if isinstance(rd, tuple):
                    rd = rd[0]
                if rd in wtin:
                    self.dependence.add((wtin[rd], stmt))
                    #WR dependence
            for wt in Write[stmt]:
                if isinstance(wt, tuple):
                    wt = wt[0]
                if wt in wtin:
                    self.dependence.add((wtin[wt], stmt))
                    # WW dependence
            for wt in Write[stmt]:
                wtin[wt] = stmt
        rdin = {}
        for stmt in stmtList:
            for wt in Write[stmt]:
                if isinstance(wt, tuple):
                    wt = wt[0]
                if wt in rdin:
                    rdwtlst = rdin[wt]
                    for rdstmt in rdwtlst:
                        self.dependence.add((rdstmt, stmt))
                        # RW dependence
            for rd in Read[stmt]:
                if isinstance(rd, tuple):
                    rd = rd[0]
                if rd in rdin:
                    rdin[rd].add(stmt)
                else:
                    rdin[rd] = set()
                    rdin[rd].add(stmt)
    def loop(self, stmtList, Read, Write):
        if len(stmtList) == 0: return
        
        wtin = {}
        # wtin: key = variable, value = last write stmt
        
        for stmt in stmtList:
            for rd in Read[stmt]:
                if isinstance(rd, tuple):
                    if rd[1] in self.loopVars:
                        pass
                    else:
                        rd = rd[0]
                
                if rd in wtin:
                    self.dependence.add((wtin[rd], stmt))
                    # WR
            for wt in Write[stmt]:
                if isinstance(wt, tuple):
                    if wt[1] in self.loopVars:
                        pass
                    else:
                        wt = wt[0]

                if wt in wtin:
                    self.dependence.add((wtin[wt], stmt))
                    # WW
                wtin[wt] = stmt
        # loop again but change value of loopVar
        for stmt in stmtList:
            for rd in Read[stmt]:
                if isinstance(rd, tuple):
                    if rd[1] in self.loopVars:
                        rd = (rd[0], rd[1] + '_iter')
                    else:
                        rd = rd[0]
                elif rd in self.loopVars:
                    rd = rd + '_iter'
                if rd in wtin:
                    self.dependence.add((wtin[rd], stmt))
            for wt in Write[stmt]:
                if isinstance(wt, tuple):
                    if wt[1] in self.loopVars:
                        wt = (wt[0], wt[1] + '_iter')
                    else:
                        wt = wt[0]
                elif wt in self.loopVars:
                    wt = wt + '_iter'
                if wt in wtin:
                    self.dependence.add((wtin[wt], stmt))
                wtin[wt] = stmt
        
        rdin = {}
        # rdin: key = variable, value = last read stmt

        for stmt in stmtList:
            for wt in Write[stmt]:
                if isinstance(wt, tuple):
                    if wt[1] in self.loopVars:
                        pass
                    else:
                        wt = wt[0]
                
                if wt in rdin:
                    rdwtlst = rdin[wt]
                    for rdstmt in rdwtlst:
                        self.dependence.add((rdstmt, stmt))
                        # RW
            for rd in Read[stmt]:
                if isinstance(rd, tuple):
                    if rd[1] in self.loopVars:
                        pass
                    else:
                        rd = rd[0]
                
                if rd in rdin:
                    rdin[rd].add(stmt)
                else:
                    rdin[rd] = set()
                    rdin[rd].add(stmt)
        # loop again but change value of loopVar
        for stmt in stmtList:
            for wt in Write[stmt]:
                if wt in self.loopVars:
                    wt = wt + '_iter'
                if wt in rdin:
                    rdwtlst = rdin[wt]
                    for rdstmt in rdwtlst:
                        # self.dependence.add((rdstmt, stmt))
                        # RW
                        # remove RW
                        pass
            for rd in Read[stmt]:
                if rd in self.loopVars:
                    rd = rd + '_iter'
                if rd in rdin:
                    rdin[rd].add(stmt)
                else:
                    rdin[rd] = set()
                    rdin[rd].add(stmt)
    def getVars(self, expr):
        if isinstance(expr, ast.Name):
            return set({expr.id})
        elif isinstance(expr, ast.Tuple):
            res = set()
            for u in expr.elts:
                res |= self.getVars(u)
            return res
        elif isinstance(expr, ast.Attribute):
            return set({expr.attr})
        else:
            print(expr.__class__.__name__)
            raise    
    def getLoopVariables(self, loop):
        if isinstance(loop, ast.For):
            return self.getVars(loop.target)
        elif isinstance(loop, ast.While):
            return set()
        else:
            raise
    def draw(self, filename='dep.png'):
        import pygraphviz
        G = pygraphviz.AGraph(directed=True)
        for stmt in self.stmtList:
            stmtText = getstr(stmt)#str(stmt.lineno) + ': ' + getstr(stmt)#[:30]
            if isinstance(stmt, ast.stmt):
                G.add_node(stmtText, shape='box')
            else:
                G.add_node(stmtText)
        for u, v in self.dependence:
            uText = getstr(u) #str(u.lineno) + ': ' + getstr(u)#[:30]
            vText = getstr(v) #str(v.lineno) + ': ' + getstr(v)#[:30]
            G.add_edge(uText, vText)
        G.draw(filename, prog='dot')
        
if __name__ == '__main__':
    import argparse
    from pypar.basics.utils import slurp
    from pypar.basics.ReadWriteAnalyzer import ReadWriteAnalyzer
    from pypar.basics.SequenceExtractor import SequenceExtractor
    from pypar.basics.LoopExtractor import LoopExtractor

    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))
    
    filename = args.pythonfile.split('/')[-1]
    
    rwa = ReadWriteAnalyzer(root)
    
    # sequential
    se = SequenceExtractor(root)
    for i, seq in enumerate(se.sequences):
        da = DependenceAnalyzer(seq, rwa.Read, rwa.Write, kind='sequential')
        da.draw('graphs/' + filename + '.seq.' + str(i) + '.dg.png')

    #loop
    le = LoopExtractor(root)
    for i, loop in enumerate(le.loops):
        da = DependenceAnalyzer(loop, rwa.Read, rwa.Write, kind='loop')
        da.draw('graphs/' + filename + '.loop.' + str(i) + '.dg.png')
    