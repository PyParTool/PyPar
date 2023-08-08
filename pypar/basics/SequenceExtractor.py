import ast

class SequenceExtractor:
    def __init__(self, root):
        self.sequences = []
        self.parent = {}
        self.getSeqs(root.body, root, "body")
    
    def getSeqs(self, stmtList, parent, branch):
        curseqs = []
        for stmt in stmtList:
            self.parent[stmt] = (parent, branch)
            # FunctionDef
            if (isinstance(stmt, ast.FunctionDef)
                or isinstance(stmt, ast.ClassDef)
                or isinstance(stmt, ast.With)
                or isinstance(stmt, ast.AsyncFunctionDef)):
                self.getSeqs(stmt.body, stmt, "body")
                if len(curseqs) != 0:
                    self.sequences.append(curseqs)
                curseqs = []
            elif isinstance(stmt, ast.Try):
                self.getSeqs(stmt.body, stmt, "body")
                self.getSeqs(stmt.orelse, stmt, "orelse")
                self.getSeqs(stmt.finalbody, stmt, "finalbody")
                if len(curseqs) != 0:
                    self.sequences.append(curseqs)
                curseqs = []
            elif (isinstance(stmt, ast.For) 
                or isinstance(stmt, ast.While) 
                or isinstance(stmt, ast.If)):
                self.getSeqs(stmt.body, stmt, "body")
                self.getSeqs(stmt.orelse, stmt, "orelse")
                if len(curseqs) != 0:
                    self.sequences.append(curseqs)
                curseqs = []
            elif (isinstance(stmt, ast.Return)
                or isinstance(stmt, ast.Break)
                or isinstance(stmt, ast.Continue)
                or isinstance(stmt, ast.Raise)
                or isinstance(stmt, ast.Assert)):
                break
            elif (isinstance(stmt, ast.Assign)
                or isinstance(stmt, ast.Expr)
                or isinstance(stmt, ast.AugAssign)
                or isinstance(stmt, ast.AnnAssign)):
                curseqs.append(stmt)
            elif (isinstance(stmt, ast.Import)
                or isinstance(stmt, ast.ImportFrom)
                or isinstance(stmt, ast.Pass)
                or isinstance(stmt, ast.Delete)
                or isinstance(stmt, ast.Global)
                or isinstance(stmt, ast.Nonlocal)):
                continue
            else: 
                print(stmt.__class__.__name__)
                raise
        if len(curseqs) != 0:
            self.sequences.append(curseqs)

if __name__ == '__main__':
    import argparse
    from pypar.basics.utils import slurp, getstr
    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))
    se = SequenceExtractor(root)

    #Test of Sequence Extractor
    for seq in se.sequences:
        print('---------------------------')
        for stmt in seq:
            print(getstr(stmt))

    '''#Test parent
    for stmt, pir in se.parent.items():
        print("-------------------------------")
        print(getstr(stmt))
        parent, branch = pir
        print(getstr(parent))
        print(branch)

    '''