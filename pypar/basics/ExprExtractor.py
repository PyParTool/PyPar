import ast
#import pygraphviz
from pypar.basics.utils import getstr

class ExprExtractor:
    def __init__(self, stmt):
        self.exprs = []
        self.dependence = set()
        self.extractExpr(stmt)
    
    def getSub(self, expr, p):
        # modified
        # to add subexpr within try_except
        if isinstance(expr, ast.BinOp):
            self.getSub(expr.left, p)
            self.getSub(expr.right, p)
        elif isinstance(expr, ast.UnaryOp):
            self.getSub(expr.operand, p)
        elif isinstance(expr, ast.Call):
            if isinstance(p, ast.Expr) and expr is p.value:
                for arg in expr.args:
                    self.getSub(arg, p)
            else:
                self.dependence.add((expr, p))
                for arg in expr.args:
                    self.getSub(arg, expr)
                self.exprs.append(expr)
        else:
            return
    
    def extractExpr(self, stmt):
        if isinstance(stmt, ast.Assign):
            self.getSub(stmt.value, stmt)
        elif isinstance(stmt, ast.AugAssign):
            self.getSub(stmt.value, stmt)
        elif isinstance(stmt, ast.Expr):
            self.getSub(stmt.value, stmt)
        
        # newly added for try
        elif isinstance(stmt, ast.Try):
            for substmt in stmt.body + stmt.orelse:
                self.extractExpr(substmt)
        # newly added for if
        elif isinstance(stmt, ast.If):
            for substmt in stmt.body + stmt.orelse:
                self.extractExpr(substmt)
        
        else:
            pass
        self.exprs.append(stmt)

    def draw(self, filename='dep.png'):
        pass
        '''G = pygraphviz.AGraph(directed=True)
        for expr in self.exprs:
            exprText = str(expr.lineno) + ': ' + getstr(expr)
            G.add_node(exprText)
        for u, v in self.dependence:
            uText = str(u.lineno) + ': ' + getstr(u)
            vText = str(v.lineno) + ': ' + getstr(v)
            G.add_edge(uText, vText)
        G.draw(filename, prog='dot')
        '''