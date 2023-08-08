import ast
from pypar.basics.utils import getstr

class LoopExtractor:
    def __init__(self, root):
        self.loops = []
        self.parent = {}
        self.getLoops(root.body, root, "body")
        self.filtLoops()
        
    def getLoops(self, stmtList, parent, branch):
        for stmt in stmtList:
            # FunctionDef
            if (isinstance(stmt, ast.FunctionDef)
                or isinstance(stmt, ast.ClassDef)):
                self.getLoops(stmt.body, stmt, "body")
            elif (isinstance(stmt, ast.For) 
                or isinstance(stmt, ast.While)):
                self.getLoops(stmt.body, stmt, "body")
                self.getLoops(stmt.orelse, stmt, "orelse")
                self.loops.append(stmt)
                self.parent[stmt] = (parent, branch)
            elif isinstance(stmt, ast.If):
                self.getLoops(stmt.body, stmt, "body")
                self.getLoops(stmt.orelse, stmt, "orelse")
            elif (isinstance(stmt, ast.Return)
                or isinstance(stmt, ast.Break)
                #or isinstance(stmt, ast.Continue)
                or isinstance(stmt, ast.Assert)):
                break
            elif (isinstance(stmt, ast.Assign)
                or isinstance(stmt, ast.Expr)
                or isinstance(stmt, ast.Import)
                or isinstance(stmt, ast.ImportFrom)
                or isinstance(stmt, ast.AugAssign)
                or isinstance(stmt, ast.Raise)
                or isinstance(stmt, ast.With)
                or isinstance(stmt, ast.Try)
                # added continue
                or isinstance(stmt, ast.Continue)):
                continue
            else:
                continue 
                #print(stmt.__class__.__name__)
                #raise

    def isValidNode(self, node):
        if isinstance(node, list):
            for nd in node:
                if not self.isValidNode(nd):
                    return False
            return True    
        elif (isinstance(node, ast.Assign)
            or isinstance(node, ast.Expr)
            or isinstance(node, ast.AugAssign)
            or isinstance(node, ast.AnnAssign)):
            return True
        elif (isinstance(node, ast.If)):
            return self.isValidNode(node.body) \
                    and self.isValidNode(node.orelse)
        else:
            return False

    # retain loops whose body consists only of Expr and Assign
    def isValid(self, loop):
        return isinstance(loop, ast.For) and self.isValidNode(loop.body)

    def filtLoops(self):
        self.loops = [loop for loop in self.loops if self.isValid(loop)]


if __name__ == '__main__':
    import argparse
    from pypar.basics.utils import slurp, getstr
    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))
    le = LoopExtractor(root)

    for loop in le.loops:
        print('-----------------------')
        print(getstr(loop))
