import ast
from pypar.basics.config import COST_THRESHOLD

class CompParallelizer:
    def __init__(self, comps, Read, Write, cost):
        self.cost = cost
        self.Read = {}
        self.Write = {}
        self.loopVars = {}
        self.parallelizableComps = []
        for comp in comps:
            self.getLoopVariables(comp)
            self.getReadWrite(comp, Read, Write)
            if self.isParallelizable(comp):
                self.parallelizableComps.append(comp)
    def getReadWrite(self, comp, Read, Write):
        if isinstance(comp, ast.ListComp):
            self.Read[comp] = Read[comp.elt] - self.loopVars[comp]
            self.Write[comp] = Write[comp.elt] - self.loopVars[comp]
        elif isinstance(comp, ast.DictComp):
            self.Read[comp] = (Read[comp.key] | Read[comp.value]) - self.loopVars[comp]
            self.Write[comp] = (Write[comp.key] | Write[comp.value]) - self.loopVars[comp]

    def isParallelizable(self, comp):
        WT = self.Write[comp]
        RD = self.Read[comp] 
        return len(WT) == 0 and len(WT & RD) == 0 
        # ignore comp const
        # assume is essential
                #and\
                # self.cost[comp.elt] >= COST_THRESHOLD
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
        self.loopVars[comp] = set()
        for g in comp.generators:
            self.loopVars[comp] |= self.getVars(g.target)

if __name__ == '__main__':
    import argparse
    from pypar.basics.utils import slurp, getstr
    from pypar.basics.ReadWriteAnalyzer import ReadWriteAnalyzer
    from pypar.basics.CompExtractor import CompExtractor

    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))

    rwa = ReadWriteAnalyzer(root)
    ce = CompExtractor(root)
    cp = CompParallelizer(ce.comps, rwa.Read, rwa.Write)

    for comp in cp.parallelizableComps:
        print(getstr(comp))