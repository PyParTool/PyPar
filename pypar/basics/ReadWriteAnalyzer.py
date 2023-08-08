import ast
from pypar.basics.utils import getstr

class ReadWriteAnalyzer:
    # input: AST of target program
    # find read\write of stmt & expr
    def __init__(self, root, Libs = set(), writeObj = {}):
        self.Read = {None: set()}
        self.Write = {None: set()}
        self.Libs = Libs
        self.writeObj = writeObj  
        # methodname -> bool, whether it modifies self

        # collect all index variable in for loops
        self.forIters = set()
        # collect all arrays that accessed not by index
        self.violatedArrays = set()

        if isinstance(root, list):
            for nd in root:
                self.recursiveAnalyze(nd)
        else:
            self.recursiveAnalyze(root)
        self.removeViolatedArrays()
        self.getRWn()

    # remove a[i] where i is not array index in Read Write
    # such a[i] -> Read a, i, Write a
    def removeViolatedArrays(self):
        for k, st in self.Read.items():
            nst = []
            for v in st:
                if isinstance(v, tuple):
                    if v[0] in self.violatedArrays:
                        nst += [v[0], v[1]]
                    else:
                        nst += [v]
                else:
                    nst += [v]
            self.Read[k] = set(nst)
        
        for k, st in self.Write.items():
            nst = []
            for v in st:
                if isinstance(v, tuple):
                    if v[0] in self.violatedArrays:
                        nst += [v[0]]
                    else:
                        nst += [v]
                else:
                    nst += [v]
            self.Write[k] = set(nst)

    # remove index variable
    # in RW, we let a[i] to be a single unit
    # in RWn, we let a[i] to be both RW a, i
    def getRWn(self):
        self.Readn = {}
        self.Writen = {}

        for k, st in self.Read.items():
            nst = []
            for v in st:
                if isinstance(v, tuple):
                    nst += [v[0], v[1]]
                else:
                    nst += [v]
            self.Readn[k] = set(nst)
        
        for k, st in self.Write.items():
            nst = []
            for v in st:
                if isinstance(v, tuple):
                    nst += [v[0]]
                    #pass
                    #nst += [v[0], v[1]]
                else:
                    nst += [v]
            self.Writen[k] = set(nst)
    def recursiveAnalyze(self, node):
        if node is None: return
        fname = "on_%s" % node.__class__.__name__.lower()
        if hasattr(self, fname):
            fn = getattr(self, fname)
            fn(node)
        else:
            print(ast.dump(node))
            print(getstr(node))
            print(node.__class__.__name__)
            raise
    # Module(stmt* body, type_ignore* type_ignores)
    def on_module(self, node):
        for n in node.body:
            self.recursiveAnalyze(n)
    '''    
        # Interactive(stmt* body)
        # Expression(expr body)
        # FunctionType(expr* argtypes, expr returns)
    '''
    # FunctionDef      
    def on_functiondef(self, node):
        # test code for other module
        #if node.name == 'min':
        #    print(getstr(node))
        #    input()
        # end
        for n in node.body:
            self.recursiveAnalyze(n)

        self.Read[node] = set()
        self.Write[node] = set({node.name})

    # AsyncFunctionDef
    def on_asyncfunctiondef(self, node):
        self.on_functiondef(node)

    # ClassDef
    def on_classdef(self, node):
        for n in node.body:
            self.recursiveAnalyze(n)
        
        self.Read[node] = set()
        self.Write[node] = set()

        for n in node.body:
            self.Read[node] |= self.Read[n]
            self.Write[node] |= self.Write[n]
        
        self.Write[node].add(node.name)

    
    # Return(expr? value)
    def on_return(self, node):
        self.recursiveAnalyze(node.value)
        self.Read[node] = self.Read[node.value]
        self.Write[node] = self.Write[node.value]
    
    # Delete(expr* targets)
    def on_delete(self, node):
        self.Read[node] = set()
        self.Write[node] = set()
        for t in node.targets:
            self.Write[node] |= self.getAssign(t)

    # Assign(expr* targets, expr value, string? type_comment)
    # get write on LHS
    def getAssign(self, expr):
        if isinstance(expr, ast.Name):
            if expr.id in self.Libs:
                return set()
            else:
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

        self.Write[node] = self.Write[node.value] | self.Write[target] | assignTargets
        self.Read[node] = self.Read[node.value] | (self.Read[target] - assignTargets)
        
    # AugAssign(expr target, operator op, expr value)
    def on_augassign(self, node):
        self.recursiveAnalyze(node.value)
        self.recursiveAnalyze(node.target)

        self.Write[node] = self.Write[node.value] | self.Write[node.target] | self.getAssign(node.target)
        self.Read[node] = self.Read[node.value] | self.Read[node.target]
    
    # AnnAssign(expr target, expr annotation, expr? value, int simple)
    def on_annassign(self, node):
        target = node.target
        self.recursiveAnalyze(node.value)
        self.recursiveAnalyze(target)

        self.Write[node] = self.Write[node.value] | self.Write[target] | self.getAssign(target)
        self.Read[node] = self.Read[node.value]

    # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
    def on_for(self, node):
        self.recursiveAnalyze(node.iter)
        # update for loop iter variables
        self.forIters |= self.Read[node.iter]

        for n in (node.body + node.orelse):
            self.recursiveAnalyze(n)

        self.Read[node] = set()
        self.Write[node] = set()
    
        for n in (node.orelse + [node.iter]):
            self.Read[node] |= self.Read[n]
            self.Write[node] |= self.Write[n]
        
        loopVars = self.getTarget(node.target)
        for n in node.body:
            self.Read[node] |= self.Read[n] - loopVars
            self.Write[node] |= self.Write[n] - loopVars
    '''    
        # AsyncFor(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
    '''
    # While(expr test, stmt* body, stmt* orelse)
    def on_while(self, node):
        for n in (node.body + node.orelse):
            self.recursiveAnalyze(n)
        self.Read[node] = set()
        self.Write[node] = set()
        for n in (node.body + node.orelse):
            self.Read[node] |= self.Read[n]
            self.Write[node] |= self.Write[n]
    
    # If(expr test, stmt* body, stmt* orelse)
    def on_if(self, node):
        for n in (node.body + node.orelse + [node.test]):
            self.recursiveAnalyze(n)
        self.Read[node] = set()
        self.Write[node] = set()
        for n in (node.body + node.orelse + [node.test]):
            self.Read[node] |= self.Read[n]
            self.Write[node] |= self.Write[n]
        
    
    # With(withitem* items, stmt* body, string? type_comment)
    def getWithVars(self, var):
        if isinstance(var, ast.Name):
            return set({var.id})
        elif isinstance(var, ast.Tuple):
            ret = set()
            for v in var.elts:
                ret |= self.getWithVars(v)
            return ret
        elif isinstance(var, ast.Attribute):
            return set({var.attr})
        else:
            #return set()
            print(var.__class__.__name__)
            raise
    def on_with(self, node):
        # withitem = (expr context_expr, expr? optional_vars)
        for it in node.items:
            self.recursiveAnalyze(it.context_expr)
        for n in node.body:
            self.recursiveAnalyze(n)
        
        self.Read[node] = set()
        self.Write[node] = set()
        
        withVars = set()
        for it in node.items:
            self.Read[node] |= self.Read[it.context_expr]
            self.Write[node] |= self.Write[it.context_expr]

            if it.optional_vars:
                var = it.optional_vars
                withVars |= self.getWithVars(var)
                '''
                if isinstance(var, ast.Name):
                    withVars.add(var.id)
                else:
                    print(ast.dump(node))
                    print(getstr(node))
                    raise
                '''
        for n in node.body:
            self.Read[node] |= (self.Read[n] - withVars)
            self.Write[node] |= (self.Write[n] - withVars)
        
    '''
        # AsyncWith(withitem* items, stmt* body, string? type_comment)
        # Match(expr subject, match_case* cases)
    '''
    # Raise(expr? exc, expr? cause)
    def on_raise(self, node):
        self.recursiveAnalyze(node.exc)
        self.recursiveAnalyze(node.cause)

        self.Read[node] = self.Read[node.exc] | self.Read[node.cause]
        self.Write[node] = self.Write[node.exc] | self.Write[node.cause]
    
    # Try(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)
    def on_try(self, node):
        for n in (node.body + node.orelse + node.finalbody):
            self.recursiveAnalyze(n)
        
        self.Read[node] = set()
        self.Write[node] = set()

        for n in (node.body + node.orelse + node.finalbody):
            self.Read[node] |= self.Read[n]
            self.Write[node] |= self.Write[n]
    
    # Assert(expr test, expr? msg)
    def on_assert(self, node):
        self.recursiveAnalyze(node.test)
        self.Read[node] = self.Read[node.test]
        self.Write[node] = self.Write[node.test]

    # Import(alias* names)
    # import statement define the library imported
    def on_import(self, node):
        self.Read[node] = set()
        self.Write[node] = set()
        for als in node.names:
            nm = als.name if als.asname is None else als.asname
            lib = nm.split('.')[0]
            self.Write[node].add(lib)
            self.Libs.add(lib)
    
    # ImportFrom(identifier? module, alias* names, int? level)
    def on_importfrom(self, node):
        self.Read[node] = set()
        self.Write[node] = set()
        for als in node.names:
            nm = als.name if als.asname is None else als.asname
            lib = nm.split('.')[0]
            self.Write[node].add(lib)
            self.Libs.add(lib)
    
    # Global(identifier* names)
    def on_global(self, node):
        self.Read[node] = set()
        self.Write[node] = set()
        for n in node.names:
            self.Write[node].add(n) 

    # Nonlocal(identifier* names)
    def on_nonlocal(self, node):
        self.on_global(node)
    
    # Expr(expr value)
    def on_expr(self, node):
        self.recursiveAnalyze(node.value)
        self.Read[node] = self.Read[node.value]
        self.Write[node] = self.Write[node.value]
    
    # Pass
    def on_pass(self, node):
        self.Read[node] = set()
        self.Write[node] = set()
    
    # Break | 
    def on_break(self, node):
        self.Read[node] = set()
        self.Write[node] = set()
    
    # Continue
    def on_continue(self, node):
        self.Read[node] = set()
        self.Write[node] = set()
    
    # BoolOp(boolop op, expr* values)
    def on_boolop(self, node):
        for e in node.values:
            self.recursiveAnalyze(e)
        
        self.Write[node] = set()
        for e in node.values:
            self.Write[node] |= self.Write[e]
        
        self.Read[node] = set()
        for e in node.values:
            self.Read[node] |= self.Read[e]
    
    # NamedExpr(expr target, expr value)
    def on_namedexpr(self, node):
        target = node.target
        self.recursiveAnalyze(node.value)
        self.recursiveAnalyze(target)

        self.Write[node] = self.Write[node.value] | self.Write[target] | self.getAssign(target)
        self.Read[node] = self.Read[node.value]

    # BinOp(expr left, operator op, expr right)
    def on_binop(self, node):
        self.recursiveAnalyze(node.left)
        self.recursiveAnalyze(node.right)
        
        self.Write[node] = self.Write[node.left] | self.Write[node.right]
        self.Read[node] = self.Read[node.left] | self.Read[node.right]
    
    # UnaryOp(unaryop op, expr operand)
    def on_unaryop(self, node):
        self.recursiveAnalyze(node.operand)
        self.Write[node] = self.Write[node.operand]
        self.Read[node] = self.Read[node.operand]
    
    
    # Lambda(arguments args, expr body)
    def on_lambda(self, node):
        self.recursiveAnalyze(node.body)
        self.Read[node] = set()
        self.Write[node] = set()
    # IfExp(expr test, expr body, expr orelse)
    def on_ifexp(self, node):
        self.recursiveAnalyze(node.test)
        self.recursiveAnalyze(node.body)
        self.recursiveAnalyze(node.orelse)

        self.Read[node] = self.Read[node.test] | self.Read[node.body] | self.Read[node.orelse]
        self.Write[node] = self.Write[node.test] | self.Write[node.body] | self.Write[node.orelse]

    # Dict(expr* keys, expr* values)
    def on_dict(self, node):
        for u in (node.keys + node.values):
            self.recursiveAnalyze(u)
        
        self.Write[node] = set()
        self.Read[node] = set()
        for u in (node.keys + node.values):
            self.Write[node] |= self.Write[u]
            self.Read[node] |= self.Read[u]

    
    # Set(expr* elts)
    def on_set(self, node):
        for u in node.elts:
            self.recursiveAnalyze(u)
        
        self.Write[node] = set()
        self.Read[node] = set()
        for u in node.elts:
            self.Write[node] |= self.Write[u]
            self.Read[node] |= self.Read[u]

    def getTarget(self, node):
        if isinstance(node, ast.Name):
            return set({node.id})
        elif isinstance(node, ast.Tuple):
            res = set()
            for e in node.elts:
                res |= self.getTarget(e)
            return res
        elif isinstance(node, ast.List):
            res = set()
            for e in node.elts:
                res |= self.getTarget(e)
            return res
        elif isinstance(node, ast.Attribute):
            return set({node.attr})
        elif isinstance(node, ast.Starred):
            return self.getTarget(node.value)
        else:
            print(node.__class__.__name__)
            print(ast.dump(node))
            raise

    # ListComp(expr elt, comprehension* generators)
    def on_listcomp(self, node):
        self.recursiveAnalyze(node.elt)
        loopVars = set()
        for g in node.generators:
            # comprehension = (expr target, expr iter, expr* ifs, int is_async)
            self.recursiveAnalyze(g.iter)
            for u in g.ifs:
                self.recursiveAnalyze(u)
            loopVars |= self.getTarget(g.target)
        
        self.Read[node] = set()
        self.Write[node] = set()
        self.Read[node] |= self.Read[node.elt]
        self.Write[node] |= self.Write[node.elt]
        for g in node.generators:
            self.Read[node] |= self.Read[g.iter]
            self.Write[node] |= self.Write[g.iter]
            for u in g.ifs:
                self.Read[node] |= self.Read[u]
                self.Write[node] |= self.Write[u]
        self.Read[node] -= loopVars
        self.Write[node] -= loopVars


    # | SetComp(expr elt, comprehension* generators)
    def on_setcomp(self, node):
        self.on_listcomp(node)
    
    # | DictComp(expr key, expr value, comprehension* generators)
    def on_dictcomp(self, node):
        self.recursiveAnalyze(node.key)
        self.recursiveAnalyze(node.value)
        loopVars = set()
        for g in node.generators:
            # comprehension = (expr target, expr iter, expr* ifs, int is_async)
            self.recursiveAnalyze(g.iter)
            for u in g.ifs:
                self.recursiveAnalyze(u)
            loopVars |= self.getTarget(g.target)
        
        self.Read[node] = self.Read[node.key] | self.Read[node.value]
        self.Write[node] = self.Write[node.key] | self.Write[node.value]
        for g in node.generators:
            self.Read[node] |= self.Read[g.iter]
            self.Write[node] |= self.Write[g.iter]
            for u in g.ifs:
                self.Read[node] |= self.Read[u]
                self.Write[node] |= self.Write[u]
        self.Read[node] -= loopVars
        self.Write[node] -= loopVars

    
    # | GeneratorExp(expr elt, comprehension* generators)
    def on_generatorexp(self, node):
        self.on_listcomp(node)
    
    # Asynchronous
    
    # | Await(expr value)
    def on_await(self, node):
        self.on_yield(node)

    # | Yield(expr? value)
    def on_yield(self, node):
        self.recursiveAnalyze(node.value)
        self.Read[node] = set() | self.Read[node.value]
        self.Write[node] = set() | self.Write[node.value]
    
    # | YieldFrom(expr value)
    def on_yieldfrom(self, node):
        self.on_yield(node)

    #Compare(expr left, cmpop* ops, expr* comparators)
    def on_compare(self, node):
        self.recursiveAnalyze(node.left)
        for u in node.comparators:
            self.recursiveAnalyze(u)
        
        self.Read[node] = self.Read[node.left]
        for u in node.comparators:
            self.Read[node] |= self.Read[u]
        self.Write[node] = self.Write[node.left]
        for u in node.comparators:
            self.Write[node] |= self.Write[u]

    # Call(expr func, expr* args, keyword* keywords)
    # Assume function call won't write arguments
    # which may not be true in practice
    # f(args): read f, args write None
    # a.b(args): read a, args, write a
    # expr(args): read Read[expr], args, write Write[expr]
    def getFuncname(self, expr):
        if isinstance(expr, ast.Name):
            return expr.id
        elif isinstance(expr, ast.Attribute):
            return expr.attr
        else:
            return None
    def on_call(self, node):
        for arg in node.args:
            self.recursiveAnalyze(arg)
        for kwd in node.keywords:
            self.recursiveAnalyze(kwd.value)
        self.recursiveAnalyze(node.func)
        self.Read[node] = set()
        self.Write[node] = set()

        for arg in node.args:
            self.Read[node] |= self.Read[arg]
            self.Write[node] |= self.Write[arg]
        for kwd in node.keywords:
            self.Read[node] |= self.Read[kwd.value]
            self.Write[node] |= self.Write[kwd.value]
        
        self.Read[node] |= self.Read[node.func]
        self.Write[node] |= self.Write[node.func]

        if isinstance(node.func, ast.Name):
            if node.func.id == 'print':
                self.Write[node].add('stdout')
            elif node.func.id == 'input':
                self.Write[node].add('stdin')
        else:
            funcname = self.getFuncname(node.func)
            if funcname not in self.writeObj or\
                self.writeObj[funcname]:
                self.Write[node] |= self.getAssign(node.func)
    
    #| FormattedValue(expr value, int conversion, expr? format_spec)
    def on_formattedvalue(self, node):
        self.recursiveAnalyze(node.value)
        self.recursiveAnalyze(node.format_spec)

        self.Read[node] = self.Read[node.value] | self.Read[node.format_spec]
        self.Write[node] = self.Write[node.value] | self.Write[node.format_spec]

    #| JoinedStr(expr* values)
    def on_joinedstr(self, node):
        for v in node.values:
            self.recursiveAnalyze(v)

        self.Read[node] = set()
        self.Write[node] = set()

        for v in node.values:
            self.Read[node] |= self.Read[v]
            self.Write[node] |= self.Write[v]

    # Constant(constant value, string? kind)
    def on_constant(self, node):
        self.Read[node] = set()
        self.Write[node] = set()
    
    # Attribute(expr value, identifier attr, expr_context ctx)
    def on_attribute(self, node):
        self.recursiveAnalyze(node.value)
        self.Read[node] = self.Read[node.value]
        self.Write[node] = self.Write[node.value]
         
    # Subscript(expr value, expr slice, expr_context ctx)
    def on_subscript(self, node):
        if isinstance(node.value, ast.Name):
            # only for a[i] where i is loop index
            if (isinstance(node.slice, ast.Index)
                and isinstance(node.slice.value, ast.Name)
                and node.slice.value.id in self.forIters
                ):
                self.Read[node] = set({(node.value.id, node.slice.value.id)})
                self.Read[node].add(node.slice.value.id)
                self.Write[node] = set()
                return
            # otherwise the array a is violated
            else:
                self.violatedArrays.add(node.value.id)
        
        self.recursiveAnalyze(node.value)
        self.recursiveAnalyze(node.slice)
        self.Read[node] = self.Read[node.value] | self.Read[node.slice]
        self.Write[node] = self.Write[node.value] | self.Write[node.slice]
    
    
    # Starred(expr value, expr_context ctx)
    def on_starred(self, node):
        self.recursiveAnalyze(node.value)
        self.Read[node] = self.Read[node.value]
        self.Write[node] = self.Write[node.value]

    # Name(identifier id, expr_context ctx)
    def on_name(self, node):
        self.Write[node] = set()
        self.Read[node] = set({node.id})
        
        # for super() which modifies self
        if node.id == 'super':
            self.Write[node].add('self')
             
    # List(expr* elts, expr_context ctx)
    def on_list(self, node):
        for u in node.elts:
            self.recursiveAnalyze(u)
        
        self.Write[node] = set()
        self.Read[node] = set()
        for u in node.elts:
            self.Write[node] |= self.Write[u]
            self.Read[node] |= self.Read[u]
    
    # Tuple(expr* elts, expr_context ctx)
    def on_tuple(self, node):
        for u in node.elts:
            self.recursiveAnalyze(u)
        
        self.Write[node] = set()
        self.Read[node] = set()
        for u in node.elts:
            self.Write[node] |= self.Write[u]
            self.Read[node] |= self.Read[u]
    
    # -- can appear only in Subscript
    # Slice(expr? lower, expr? upper, expr? step)
    def on_slice(self, node):
        self.recursiveAnalyze(node.lower)
        self.recursiveAnalyze(node.upper)
        self.recursiveAnalyze(node.step)
        self.Read[node] = self.Read[node.lower] | self.Read[node.upper] | self.Read[node.step]
        self.Write[node] = self.Write[node.lower] | self.Write[node.upper] | self.Write[node.step]

    # removed in higher python version
    # ExtSlice
    def on_extslice(self, node):
        for u in node.dims:
            self.recursiveAnalyze(u)
        self.Read[node] = set()
        self.Write[node] = set()
        for u in node.dims:
            self.Read[node] |= self.Read[u]
            self.Write[node] |= self.Write[u]
    
    #Index
    def on_index(self, node):
        self.recursiveAnalyze(node.value)
        self.Read[node] = self.Read[node.value]
        self.Write[node] = self.Write[node.value]

if __name__ == '__main__':
    import argparse
    from pypar.basics.utils import slurp, getstr
    parser = argparse.ArgumentParser()
    parser.add_argument('pythonfile', help='The python file to be analyzed')
    args = parser.parse_args()
    root = ast.parse(slurp(args.pythonfile))
    rwa = ReadWriteAnalyzer(root)

    #Test of read write   
    print('-----------------------------')
    print('Write:')
    for key, value in rwa.Write.items():
        if isinstance(key, ast.stmt):
            print(getstr(key), ': ', value)

    print('-----------------------------')
    print('Read:')
    for key, value in rwa.Read.items():
        if isinstance(key, ast.stmt):
            print(getstr(key), ': ', value)
