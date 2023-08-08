import ast
from pypar.basics.config import COST_THRESHOLD

class LoopParallelizer:
    def __init__(self, loop, dependence, cost = None):
        self.cost = cost

        if isinstance(loop, ast.While):
            self.build_graph([loop.test] + loop.body, dependence)
        elif isinstance(loop, ast.For):
            self.build_graph(loop.body, dependence)
        else:
            raise
        self.getSCC()
        self.removeControlFlowChange()
        self.topoSort()
        self.sccStmtList = [[stmt for stmt in loop.body if self.sccMap[stmt] == scc] for scc in self.sccList]

    def build_graph(self, stmtList, dependence):
        self.G = {}
        self.Ginv = {}
        for stmt in stmtList:
            self.G[stmt] = set()
            self.Ginv[stmt] = set()
        for u, v in dependence:
            self.G[u].add(v)
            self.Ginv[v].add(u)

    def getSCC(self):
        self.SCCs = {}
        self.sccMap = {}
        self.unparallelizable = set()

        def dfs(u, dfn, low, stk, instk, cnt):
            dfn[u] = cnt.cnt
            low[u] = cnt.cnt
            cnt.cnt += 1
            
            stk.append(u)
            instk.add(u)

            for v in self.G[u]:
                if v not in dfn:
                    dfs(v, dfn, low, stk, instk, cnt)
                    if low[u] > low[v]:
                        low[u] = low[v]
                elif v in instk:
                    if low[u] > dfn[v]:
                        low[u] = dfn[v]
            
            if dfn[u] == low[u]:
                scc = set()
                while True:
                    v = stk.pop(-1)
                    instk.remove(v)
                    scc.add(v)
                    if v == u:
                        break

                for v in scc:
                    self.sccMap[v] = dfn[u]

                self.SCCs[dfn[u]] = scc
                
                if len(scc) >= 2:
                    self.unparallelizable |= set(scc)
                elif len(scc) == 1:
                    u = list(scc)[0]
                    if u in self.G[u] or (self.cost and (u not in self.cost or self.cost[u] < COST_THRESHOLD)):
                        self.unparallelizable.add(u)
        dfn = {}
        low = {}
        stk = []
        instk = set()
        class Cnt:
            def __init__(self):
                self.cnt = 0
        cnt = Cnt()

        for u in self.G.keys():
            if u not in dfn:
                dfs(u, dfn, low, stk, instk, cnt)

        self.parallelizable = set(self.G.keys()) - self.unparallelizable

    def hasControlFlowChange(self, u):
        if isinstance(u, ast.Break) or\
            isinstance(u, ast.Continue) or\
            isinstance(u, ast.Raise):
            return True
        for attr in dir(u):
            if attr[0] == '_' or attr == 'p' or attr =='br':
                continue
            attr_obj = getattr(u, attr)
            if isinstance(attr_obj, list):
                for v in attr_obj:
                    if (isinstance(v, ast.mod)
                        or isinstance(v, ast.stmt)
                        or isinstance(v, ast.expr)):
                        if self.hasControlFlowChange(v):
                            return True
            elif (isinstance(attr_obj, ast.mod)
                        or isinstance(attr_obj, ast.stmt)
                        or isinstance(attr_obj, ast.expr)):
                if self.hasControlFlowChange(attr_obj):
                    return True
        return False

    def removeControlFlowChange(self):
        # remove all statements in parallelizable which contains control flow change
        # e.g. break continue raise
        self.parallelizable = set([stmt for stmt in self.parallelizable 
                                            if not self.hasControlFlowChange(stmt)])

    def topoSort(self):
        self.sccG = {scc: set() for scc in self.SCCs}
        inDeg = {scc: 0 for scc in self.SCCs}
        
        for u in self.G:
            for v in self.G[u]:
                sccU = self.sccMap[u]
                sccV = self.sccMap[v]
                if sccU != sccV:
                    self.sccG[sccU].add(sccV)
                    inDeg[sccV] += 1
        
        queue = [u for u in self.SCCs if inDeg[u] == 0]
        self.sccList = []
        while len(queue) != 0:
            u = queue.pop(0)
            self.sccList.append(u)
            for v in self.sccG[u]:
                inDeg[v] -= 1
                if inDeg[v] == 0:
                    queue.append(v)





if __name__ == '__main__':
    '''class Loop:
        def __init__(self):
            self.body = [0, 1, 2, 3, 4, 5, 6, 7]
            self.dependence = [
                (1, 2),
                (1, 3),
                (3, 4),
                (4, 1),
                (2, 5),
                (5, 2),
                (0, 6),
                (6, 7),
                (7, 0)]
    loop = Loop()
    lp = LoopParallelizer(loop, loop.dependence)
    for scc in lp.SCCs:
        print(scc)'''
    import argparse
    from pypar.basics.utils import slurp, getstr
    from pypar.basics.ReadWriteAnalyzer import ReadWriteAnalyzer
    from pypar.basics.LoopExtractor import LoopExtractor
    from pypar.basics.DependenceAnalyzer import DependenceAnalyzer
    #from LoopSplitter import LoopSplitter

    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))

    rwa = ReadWriteAnalyzer(root)
    le = LoopExtractor(root)

    for loop in le.loops:
        da = DependenceAnalyzer(loop, rwa.Read, rwa.Write, kind='loop')
        lp = LoopParallelizer(loop, da.dependence)

        print('_' * 50)
        for stmt in lp.parallelizable:
            print(getstr(stmt))

