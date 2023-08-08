from pypar.basics.config import COST_THRESHOLD

class SequenceParallelizer:
    def __init__(self, stmtList, dependence, cost = None):
        self.cost = cost
        self.build_graph(stmtList, dependence)
        #self.get_dominants()
        #self.dominanceAnalysis()
        #self.parallelizable = set(self.G.keys()) - self.dom["out"] - set({"in", "out"})
        #self.parallelizable = [stmt for stmt in stmtList if stmt not in self.dominants]
        self.getDepth()
        self.getParallelizable()
        #self.mostRecentDependence(stmtList)
        

    def build_graph(self, stmtList, dependence):
        self.G = {}
        self.Ginv = {}
        for stmt in stmtList:
            self.G[stmt] = set()
            self.Ginv[stmt] = set()
        for u, v in dependence:
            self.G[u].add(v)
            self.Ginv[v].add(u)
        indeg = {u: len(self.Ginv[u]) for u in self.Ginv.keys()}
        outdeg = {u: len(self.G[u]) for u in self.G.keys()}
        innodes = []
        outnodes = []
        for u in self.G.keys():
            if indeg[u] == 0:
                innodes.append(u)
                self.Ginv[u].add("in")
            if outdeg[u] == 0:
                outnodes.append(u)
                self.G[u].add("out")
        
        self.G["in"] = set(innodes)
        self.G["out"] = set()
        self.Ginv["in"] = set()
        self.Ginv["out"] = set(outnodes)

    '''def get_dominants(self):
        self.dominants = set()
        while True:
            self.dominanceAnalysis()
            if len(self.dominants) == len(self.dom['out']):
                break
            self.dominants = set()
            for u in self.dom['out']:
                self.dominants.add(u)

            dominantsList = []
            queue = ['in']
            while len(queue) > 0:
                u = queue.pop(0)
                if u in self.dominants:
                    dominantsList.append(u)
                for v in self.G[u]:
                    queue.append(v)
            
            dominantsList.append('out')

            adjDom = [
                (dominantsList[i - 1], dominantsList[i]) 
                for i in range(1, len(dominantsList))]
            
            for u, v in adjDom:
                if v in self.G[u] and len(self.G[u]) >= 2:
                    self.G[u].remove(v)
                    self.Ginv[v].remove(u)
    
    def dominanceAnalysis(self):
        self.dom = {}
        for u in self.G.keys():
            self.dom[u] = set({u})
        
        all_nodes = set(self.G.keys())
        changed = True
        while changed:
            changed = False
            for u in self.G.keys():
                preds = self.Ginv[u]
                if len(preds) == 0:
                    continue
                pds = all_nodes | set()
                for p in preds:
                    pds &= self.dom[p]
                l0 = len(self.dom[u])
                self.dom[u] |= pds
                l1 = len(self.dom[u])
                if l0 < l1:
                    changed = True
    '''

    def getDepth(self):
        self.depth = {}

        self.depth['in'] = 0
        queue = ['in']
        inqueue = set({'in'})
        
        while len(queue) != 0:
            u = queue.pop(0)
            inqueue.remove(u)

            for v in self.G[u]:
                if (v not in self.depth 
                    or self.depth[v] <= self.depth[u] + 1):
                    self.depth[v] = self.depth[u] + 1
                    if v not in inqueue:
                        inqueue.add(v)
                        queue.append(v)
    
    def getParallelSet(self, st):
        pStmts = [u for u in st if (self.cost is None or (u in self.cost and self.cost[u] >= COST_THRESHOLD))]
        if len(pStmts) >= 2:
            return set(pStmts)
        else:
            return None

    def getParallelizable(self):
        self.depSet = {}
        self.endDepth = {}
        self.stDepthSet = {d: set() for d in range(0, self.depth['out'] + 1)}
        for u in self.G.keys():
            if u == 'in' or u == 'out': continue
            d = self.depth[u]

            self.stDepthSet[d].add(u)

            md = min(
                    map(lambda v: self.depth[v], 
                        self.G[u]))
            self.endDepth[u] = md

            for di in range(d, md):
                if di not in self.depSet:
                    self.depSet[di] = set()
                self.depSet[di].add(u)
        
        self.parallelizableSets = []
        for st in self.depSet.values():
            res = self.getParallelSet(st)
            if res:
                self.parallelizableSets.append(res)
        
        self.parallelizable = set()

        for st in self.parallelizableSets:
            self.parallelizable |= st

    def mostRecentDependence(self, stmtList):
        self.MRDstmt = {}
        for u in stmtList:
            for v in stmtList:
                if v in self.G[u]:
                    self.MRDstmt[u] = v
                    break



if __name__ == '__main__':
    import argparse
    import ast
    from pypar.basics.utils import slurp, getstr
    from pypar.basics.ReadWriteAnalyzer import ReadWriteAnalyzer
    from pypar.basics.SequenceExtractor import SequenceExtractor
    from pypar.basics.DependenceAnalyzer import DependenceAnalyzer

    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))
    
    filename = args.pythonfile.split('/')[-1]
    
    rwa = ReadWriteAnalyzer(root)
    se = SequenceExtractor(root)
    
    for i, seq in enumerate(se.sequences):
        da = DependenceAnalyzer(seq, rwa.Read, rwa.Write)
        sp = SequenceParallelizer(seq, da.dependence)
        # Test of Sequence Parallelizer
        print("-" * 50)
        #for stmt in sp.parallelizable:
        #    print(getstr(stmt))
        for pset in sp.parallelizableSets:
            print("-" * 30)
            for stmt in pset:
                print(getstr(stmt))
    