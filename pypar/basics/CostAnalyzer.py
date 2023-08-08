import ast
from pypar.basics.config import LOOP_MULT

class CostAnalyzer:
    def __init__(self, root, funcCost, astCost = {}):
        self.funcCost = funcCost
        self.cost = {}
        self.astCost = astCost
        self.getCost(root)

    def getCalled(self, funcExpr):
        if isinstance(funcExpr, ast.Name):
            return funcExpr.id
        elif isinstance(funcExpr, ast.Attribute):
            return funcExpr.attr
        else:
            return None

    def getCost(self, node):
        if isinstance(node, list):
            for nd in node:
                self.getCost(nd)
            return

        self.cost[node] = 0

        for attr in dir(node):
            if attr[0] == '_' or attr == 'p' or attr == 'br':
                continue
            attr_obj = getattr(node, attr)
            if isinstance(attr_obj, list):
                for v in attr_obj:
                    if (isinstance(v, ast.mod)
                        or isinstance(v, ast.stmt)
                        or isinstance(v, ast.expr)):
                        self.cost[node] += self.getCost(v)
            elif (isinstance(attr_obj, ast.mod)
                or isinstance(attr_obj, ast.stmt)
                or isinstance(attr_obj, ast.expr)):
                self.cost[node] += self.getCost(attr_obj)
        
        if isinstance(node, ast.Call):
            funcName = self.getCalled(node.func)
            if funcName in self.funcCost:
                self.cost[node] += self.funcCost[funcName]
            else:
                self.cost[node] += 0 # 1
        elif (isinstance(node, ast.For) 
            or isinstance(node, ast.While)):
            self.cost[node] *= LOOP_MULT

        if node in self.astCost:
            self.cost[node] = self.astCost[node]

        return self.cost[node]

'''class TracedCostAnalyzer:
    def __init__(self, root, funcTime, ASTTime):
        self.funcTime = funcTime
        self.ASTTime = ASTTime
        self.cost = {}
        self.getCost(root)

    def getCalled(self, funcExpr):
        if isinstance(funcExpr, ast.Name):
            return funcExpr.id
        elif isinstance(funcExpr, ast.Attribute):
            return funcExpr.attr
        else:
            return None

    def getCost(self, node):
        if node in self.ASTTime:
            self.cost[node] = 
        self.cost[node] = 0

        for attr in dir(node):
            if attr[0] == '_' or attr == 'p' or attr == 'br':
                continue
            attr_obj = getattr(node, attr)
            if isinstance(attr_obj, list):
                for v in attr_obj:
                    if (isinstance(v, ast.mod)
                        or isinstance(v, ast.stmt)
                        or isinstance(v, ast.expr)):
                        self.cost[node] += self.getCost(v)
            elif (isinstance(attr_obj, ast.mod)
                or isinstance(attr_obj, ast.stmt)
                or isinstance(attr_obj, ast.expr)):
                self.cost[node] += self.getCost(attr_obj)
        
        if isinstance(node, ast.Call):
            funcName = self.getCalled(node.func)
            if funcName in self.funcCost:
                self.cost[node] += self.funcCost[funcName]
            else:
                self.cost[node] += 0 # 1
        elif (isinstance(node, ast.For) 
            or isinstance(node, ast.While)):
            self.cost[node] *= LOOP_MULT

        return self.cost[node]
'''
if __name__ == '__main__':
    import argparse
    from pypar.basics.utils import slurp, getstr
    from pypar.basics.FunctionCostAnalyzer import FunctionCostAnalyzer
    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed', nargs='+')
    args = parser.parse_args()
    roots = [ast.parse(slurp(f)) for f in args.pythonfile]
    root = roots[0]

    fca = FunctionCostAnalyzer(roots)
    for k, v in fca.cost.items():
        print(k, v)
    ca = CostAnalyzer(root, fca.cost)
    
    '''for k, v in ca.cost.items():
        if v <= 20:
            continue
        print('='*50)
        print(getstr(k))
        print(v)'''