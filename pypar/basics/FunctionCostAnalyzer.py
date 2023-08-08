import ast
import json
from pypar.basics.config import LOOP_MULT

BUILTINS = dir(__builtins__) + ['print', 'input', 'max', 'min', 'set', 'int', 'str', 'list', 'range', 'append']

class FunctionCostAnalyzer:
    def __init__(self, roots):
        # dependence relation funcName : (inLoop, calledFunc)
        self.depends = {}

        # estimated cost funcName: integer
        self.cost = {}

        # which root a functionDef is in
        self.funcIdx = {}
        self.idx = 0
        for root in roots:
            self.getDepends(root)
            self.idx += 1
        
        self.getCost()
        #self.dump()
    
    def getDepends(self, node, className=None):
        if isinstance(node, ast.FunctionDef):
            if className and node.name == '__init__':
                if className not in self.funcIdx:     #
                    self.funcIdx[className] = set()   #
                self.funcIdx[className].add(self.idx) #for funcIdx
                if className not in self.depends:
                    self.depends[className] = []
                self.getFuncDepends(node, className, False)
            else:
                if node.name not in self.funcIdx:     #
                    self.funcIdx[node.name] = set()   #
                self.funcIdx[node.name].add(self.idx) #for funcIdx
                if node.name not in self.depends:
                    self.depends[node.name] = []
                self.getFuncDepends(node, node.name, False)
        elif isinstance(node, ast.ClassDef):
            for u in node.body:
                self.getDepends(u, node.name)
        else:
            for attr in dir(node):
                if attr[0] == '_':
                    continue
                attr_obj = getattr(node, attr)
                if isinstance(attr_obj, list):
                    for v in attr_obj:
                        if (isinstance(v, ast.mod)
                            or isinstance(v, ast.stmt)
                            or isinstance(v, ast.expr)):
                            self.getDepends(v, className)
                elif (isinstance(attr_obj, ast.mod)
                            or isinstance(attr_obj, ast.stmt)
                            or isinstance(attr_obj, ast.expr)):
                    self.getDepends(attr_obj, className)

    def getCalled(self, funcExpr):
        if isinstance(funcExpr, ast.Name):
            return funcExpr.id
        elif isinstance(funcExpr, ast.Attribute):
            return funcExpr.attr
        else:
            return None

    def getFuncDepends(self, node, funcName, inLoop):
        if isinstance(node, ast.Call):
            calledName = self.getCalled(node.func)
            if calledName:
                self.depends[funcName].append((inLoop, calledName))
        elif (isinstance(node, ast.For)
            or isinstance(node, ast.While)):
            inLoop = True
        
        for attr in dir(node):
            if attr[0] == '_':
                continue
            attr_obj = getattr(node, attr)
            if isinstance(attr_obj, list):
                for v in attr_obj:
                    if (isinstance(v, ast.mod)
                        or isinstance(v, ast.stmt)
                        or isinstance(v, ast.expr)):
                        self.getFuncDepends(v, funcName, inLoop)
            elif (isinstance(attr_obj, ast.mod)
                        or isinstance(attr_obj, ast.stmt)
                        or isinstance(attr_obj, ast.expr)):
                self.getFuncDepends(attr_obj, funcName, inLoop)
    
    def getCost(self):
        for k in BUILTINS:
            if k in self.depends:
                self.depends.pop(k)

        self.G = {u: set() for u in self.depends.keys()}
        #print(BUILTINS)
        #print(self.G.keys())
        #input()
        self.Ginv = {u: set() for u in self.depends.keys()}
        
        for u, st in self.depends.items():
            for lp, v in st:
                if v in self.G and v != u:
                    self.G[u].add(v)
                    self.Ginv[v].add(u)
        
        #for u in self.G.keys():
        #    print(u)
        #    print(self.G[u])

        deg = {u: len(self.G[u]) for u in self.G.keys()}
        
        queue = [u for u in self.G.keys() if deg[u] == 0]
        while len(queue) != 0:
            u = queue.pop(0)
            #print(u)
            if u not in self.cost:
                self.cost[u] = 0
            for lp, v in self.depends[u]:
                if v not in self.G.keys():
                    self.cost[v] = 1
                
                if lp:
                    self.cost[u] += LOOP_MULT * self.cost[v]
                else:
                    self.cost[u] += self.cost[v]
            for v in self.Ginv[u]:
                deg[v] -= 1
                if deg[v] == 0:
                    queue.append(v)

    def dump(self, filename='graphs/funcCost.json'):
        with open(filename, 'w') as f:
            f.write(json.dumps(self.cost))
    
    def degreeDistibution(self, filename='graphs/degdist.png'):
        import numpy as np
        import matplotlib.pyplot as plt
        
        degs = {u: len(self.G[u]) + len(self.Ginv[u]) for u in self.G.keys()}
        mDegs = max([v for u, v in degs.items()])
        degdist = [0 for i in range(mDegs + 1)]

        nds = list(self.G.keys())
        nds.sort(key=lambda x: -degs[x])
        for i, nd in enumerate(nds):
            if i == 20:
                break
            print(nd, degs[nd])

        for u, v in degs.items():
            degdist[v] += 1
        
        Xs = np.array(range(mDegs + 1), dtype=np.float)
        Ys = np.array(degdist, dtype=np.float)
        plt.scatter(np.log(Xs), np.log(Ys))
        plt.savefig(filename)
        #plt.show()
    

if __name__ == '__main__':
    import argparse
    from pypar.basics.utils import slurp, getstr
    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed', nargs='+')
    args = parser.parse_args()
    roots = [ast.parse(slurp(f)) for f in args.pythonfile]
    root = roots[0]

    fca = FunctionCostAnalyzer(roots)
    #for k, st in fca.depends.items():
    #    print('='*50)
    #    print(k)
    #    print(st)
    for k, v in fca.cost.items():
        print(k, v)