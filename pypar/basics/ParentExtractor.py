import ast
from pypar.basics.utils import getstr

class ParentExtractor:
    def __init__(self, root):
        #print('=' * 50)
        #print(getstr(root))
        self.dfs(root)
    def dfs(self, u):
        for attr in dir(u):
            if attr[0] == '_' or attr == 'p' or attr =='br':
                continue
            attr_obj = getattr(u, attr)
            if isinstance(attr_obj, list):
                #print(getstr(attr_obj))
                #print(ast.dump(attr_obj))
                '''print('case 1', '=' * 50)
                print(ast.dump(u))
                print('[')
                for v in attr_obj:
                    print(ast.dump(v))
                print(']')
                '''
                for v in attr_obj:
                    if (isinstance(v, ast.mod)
                        or isinstance(v, ast.stmt)
                        or isinstance(v, ast.expr)):
                        self.dfs(v)
                        v.p = u
                        v.br = attr
            elif (isinstance(attr_obj, ast.mod)
                        or isinstance(attr_obj, ast.stmt)
                        or isinstance(attr_obj, ast.expr)):
                #print(getstr(attr_obj))
                '''print('case 2', '=' * 50)
                print(ast.dump(u))
                print(ast.dump(attr_obj))
                '''
                self.dfs(attr_obj)
                attr_obj.p = u
                attr_obj.br = attr
    def print(self, u):
        print('='*50)
        print(getstr(u))
        print(u.__class__)
        if hasattr(u, 'p'):
            print('-'*30)
            print(getstr(u.p))
            print(u.p.__class__)
        if hasattr(u, 'br'):
            print('-'*30)
            print(u.br)
        
        for attr in dir(u):
            if attr[0] == '_' or attr == 'p' or attr == 'br':
                continue
            attr_obj = getattr(u, attr)
            if isinstance(attr_obj, list):
                for v in attr_obj:
                    if (isinstance(v, ast.mod)
                        or isinstance(v, ast.stmt)
                        or isinstance(v, ast.expr)):
                        self.print(v)
            elif (isinstance(attr_obj, ast.mod)
                        or isinstance(attr_obj, ast.stmt)
                        or isinstance(attr_obj, ast.expr)):
                self.print(attr_obj)
if __name__ == '__main__':
    import argparse
    from pypar.basics.utils import slurp, getstr
    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))
    pe = ParentExtractor(root)
    pe.print(root)
