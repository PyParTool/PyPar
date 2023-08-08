from trace import Trace
import sys
import ast
from pypar.basics.utils import getstr
import linecache
import inspect
import importlib

class DepTracer(Trace):
    def __init__(self):
        super().__init__(ignoredirs=(sys.prefix, sys.exec_prefix))
        self.NameMap = {}
        self.globaltrace = self._globaltrace

    def _globaltrace(self, frame, why, arg):
        if why == 'call':
            this_func = (self.file_module_function_of(frame))
            
            funcName = this_func[2]
            if '.' in funcName:
                funcName = funcName.split('.')[1]
            
                self.NameMap[funcName] = this_func

            return None

def getSource(this_func):
    file, module, func = this_func
    if file.startswith('/home/siwei/.local/lib/python3.8/site-packages'):
        if 'egg' in file:
            moduleName = '.'.join(file.split('/')[8:])[:-3]
        else:
            moduleName = '.'.join(file.split('/')[7:])[:-3]
    elif file.startswith('/usr/lib/python3.8'):
        moduleName = '.'.join(file.split('/')[4:])[:-3]
    else:
        return ''
    if '.' in func:
        className, funcName = func.split('.')
    else:
        className = None
        funcName = func
    #print(moduleName)
    try:
        pac = importlib.import_module(moduleName)
        if not className:    
            funcobj = getattr(pac, funcName)
        else:
            cls = getattr(pac, className)
            funcobj = getattr(cls, funcName)
    except Exception as e:
        # cannot import
        return ''
    if not hasattr(funcobj, '__code__'):
        return ''
    lineno = funcobj.__code__.co_firstlineno
    lines = linecache.getlines(file)
    nlines = inspect.getblock(lines[(lineno - 1):])
    # remove redundant \t
    def removeTab(line):
        if line[:4] == '    ':
            return line[4:]
        else:
            return line
    while nlines[0][:4] == '    ':
        nlines = [removeTab(line) for line in nlines]
    return ''.join(nlines)

class RWAnalyzer:
    # input: class method
    # find whether modify self
    #   (1). self.func2(xxx) dependends on func2
    #   (2). self.v = xxx    modifies
    #   (3). otherwise       do not modify
    def __init__(self, this_func):
        self.depends = set()
        self.modifies_obj = False

        code = getSource(this_func)
        if code != '':
            root = ast.parse(code)
            self.recursiveAnalyze(root)
        
    def recursiveAnalyze(self, node):
        if node is None: 
            return
        fname = "on_%s" % node.__class__.__name__.lower()
        if hasattr(self, fname):
            fn = getattr(self, fname)
            fn(node)
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
                            self.recursiveAnalyze(v)
                elif (isinstance(attr_obj, ast.mod)
                            or isinstance(attr_obj, ast.stmt)
                            or isinstance(attr_obj, ast.expr)):
                    self.recursiveAnalyze(attr_obj)
   
    # Assign(expr* targets, expr value, string? type_comment)
    # get write on LHS
    def getAssign(self, expr):
        if isinstance(expr, ast.Name):            
            return set({expr.id})
        elif isinstance(expr, ast.Attribute):
            return self.getAssign(expr.value)
        elif isinstance(expr, ast.Subscript):
            if (isinstance(expr.value, ast.Name)
                and isinstance(expr.slice, ast.Index)
                and isinstance(expr.slice.value, ast.Name)):
                return set({(expr.value.id, expr.slice.value.id)})
            else: 
                return self.getAssign(expr.value)
            # return set()
        elif isinstance(expr, ast.Call):
            return set()
        elif isinstance(expr, ast.Tuple):
            res = set()
            for u in expr.elts:
                res |= self.getAssign(u)
            return res
        elif isinstance(expr, ast.List):
            res = set()
            for u in expr.elts:
                res |= self.getAssign(u)
            return res
        elif isinstance(expr, ast.Constant):
            return set()
        else:
            return set()
            #print(ast.dump(expr))
            #print(getstr(expr))
            #raise
    
    def on_assign(self, node):
        target = node.targets[0]
        self.recursiveAnalyze(node.value)
        self.recursiveAnalyze(target)

        assignTargets = self.getAssign(target)
        #print(getstr(node))
        #print(assignTargets)
        if 'self' in assignTargets:
            self.modifies_obj = True
        
    # AugAssign(expr target, operator op, expr value)
    def on_augassign(self, node):
        target = node.target
        self.recursiveAnalyze(node.value)
        self.recursiveAnalyze(node.target)

        assignTargets = self.getAssign(target)
        if 'self' in assignTargets:
            self.modifies_obj = True
       
    # AnnAssign(expr target, expr annotation, expr? value, int simple)
    def on_annassign(self, node):
        target = node.target
        self.recursiveAnalyze(node.value)
        self.recursiveAnalyze(node.target)

        assignTargets = self.getAssign(target)
        if 'self' in assignTargets:
            self.modifies_obj = True

    def getFuncname(self, expr):
        if isinstance(expr, ast.Name):
            return expr.id
        elif isinstance(expr, ast.Attribute):
            return expr.attr
        else:
            return None
    
    
    # Call(expr func, expr* args, keyword* keywords)
    # Assume function call won't write arguments
    # which may not be true in practice
    # f(args): read f, args write None
    # a.b(args): read a, args, write a
    # expr(args): read Read[expr], args, write Write[expr]
    def on_call(self, node):
        for arg in node.args:
            self.recursiveAnalyze(arg)
        for kwd in node.keywords:
            self.recursiveAnalyze(kwd.value)
        self.recursiveAnalyze(node.func)

        assignTargets = self.getAssign(node.func)
        funcname = self.getFuncname(node.func)
        if 'self' in assignTargets and\
            funcname != None:
            self.depends.add(funcname)

class WriteObjAnalyzer:
    def __init__(self, nameMap) -> None:
        self.nameMap = nameMap
        self.rwas = {nm : RWAnalyzer(nameMap[nm]) for nm in nameMap.keys()}
        self.writeObj = {}

        for nm in self.nameMap:
            self.recursiveAna(nm)

    def recursiveAna(self, nm, dep=0):
        if dep >= 20:
            self.writeObj[nm] = False
            return False

        if nm in self.writeObj:
            return self.writeObj[nm]
        
        rwa = self.rwas[nm]
        assert(isinstance(rwa, RWAnalyzer))
        if rwa.modifies_obj:
            self.writeObj[nm] = True
            return True
        for funcnm in rwa.depends:
            if funcnm not in self.nameMap:
                continue
            res = self.recursiveAna(funcnm, dep + 1)
            if res:
                self.writeObj[nm] = True
                return True
        self.writeObj[nm] = False
        return False
