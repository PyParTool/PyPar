import ast

class CompExtractor:
    def __init__(self, root):
        self.comps = []
        self.getComps(root)
    
    def getComps(self, node):
        if node is None: return
        
        if (isinstance(node, ast.Module)
            or isinstance(node, ast.FunctionDef)
            or isinstance(node, ast.ClassDef)):
            for n in node.body:
                self.getComps(n)
        elif (isinstance(node, ast.Return)
            or isinstance(node, ast.Assign)
            or isinstance(node, ast.AugAssign)
            or isinstance(node, ast.Expr)):
            self.getComps(node.value)
        elif (isinstance(node, ast.For)):
            for n in node.body + node.orelse:
                self.getComps(n)
        elif (isinstance(node, ast.While)
            or isinstance(node, ast.If)):
            for n in [node.test] + node.body + node.orelse:
                self.getComps(n)
        elif (isinstance(node, ast.Try)):
            for n in node.body + node.orelse + node.finalbody:
                self.getComps(n)
        elif (isinstance(node, ast.BoolOp)):
            for v in node.values:
                self.getComps(v)
        elif (isinstance(node, ast.BinOp)):
            self.getComps(node.left)
            self.getComps(node.right)
        elif (isinstance(node, ast.UnaryOp)):
            self.getComps(node.operand)
        elif (isinstance(node, ast.IfExp)):
            self.getComps(node.test)
            self.getComps(node.body)
            self.getComps(node.orelse)
        elif (isinstance(node, ast.ListComp)):
            #or isinstance(node, ast.DictComp)):
            # do not take DictComp into Consideration
            self.comps.append(node)
        elif (isinstance(node, ast.Call)):
            self.getComps(node.func)
            for u in node.args:
                self.getComps(u)
        else:
            return

if __name__ == '__main__':
    import argparse
    from pypar.basics.utils import slurp, getstr
    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))
    ce = CompExtractor(root)

    #Test of Sequence Extractor
    for comp in ce.comps:
        print(getstr(comp))
