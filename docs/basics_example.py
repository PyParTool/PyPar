import ast
from pypar.basics.utils import getstr

code = '''
h = hello()
w = world()
r = hw(h, w)
'''
stmts = ast.parse(code).body

from pypar.basics.ExprExtractor import ExprExtractor

programUnits = []
dependences = set()

for stmt in stmts:
    ee = ExprExtractor(stmt)
    programUnits += ee.exprs
    dependences |= ee.dependence

print('Program Units:')
for node in programUnits:
    print('    ', getstr(node))

print('Compose Dependence Relation:')
for u, v in dependences:
    print('    %s --> %s' % (getstr(u), getstr(v)))


from pypar.basics.ReadWriteAnalyzer import ReadWriteAnalyzer
rwa = ReadWriteAnalyzer(stmts)

print('Use Set:')
for node, st in rwa.Read.items():
    if node in programUnits:
        print('    ', getstr(node), ':', st)

print('Def Set:')
for node, st in rwa.Write.items():
    if node in programUnits:
        print('    ', getstr(node), ':', st)

from pypar.basics.DependenceAnalyzer import DependenceAnalyzer
da = DependenceAnalyzer(programUnits, rwa.Read, rwa.Write, kind="sequential")
da.dependence |= dependences

print('Data Dependence Relation:')
for u, v in da.dependence:
    print('    %s --> %s' % (getstr(u), getstr(v)))

# DependenceAnalyzer.draw requires pygraphviz
da.draw('output.png')

from pypar.basics.CostAnalyzer import CostAnalyzer
funcCost = {
    'hello' : 1.0,
    'world' : 1.0,
    'hw'    : 1.0,
}
ca = CostAnalyzer(programUnits, funcCost=funcCost)

print('Program Units Cost:')
for node, t in ca.cost.items():
    if node in programUnits:
        print('    ', getstr(node), ':', t)

from pypar.basics.SequenceParallelizer import SequenceParallelizer
sp = SequenceParallelizer(programUnits, da.dependence, ca.cost)

print('Parallelizables:')
for st in sp.parallelizableSets:
    print('-' * 30)
    for node in st:
        print('    ', getstr(node))

from pypar.basics.SequenceRewriter import RaySequenceRewriter
funcDef = ast.FunctionDef(
    'helloworld', 
    ast.arguments(
        posonlyargs=[],
        args=[], 
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults = []),
    stmts,
    [])

from pypar.basics.ParentExtractor import ParentExtractor
pe = ParentExtractor(funcDef)

rewriter = RaySequenceRewriter(funcDef, stmts, sp.stDepthSet, sp.endDepth, sp.parallelizable, rwa.Read, rwa.Write)

print('Code of assistant functions:')
for fDef in rewriter.parallelFuncDefs:
    print('-' * 30)
    print(getstr(fDef))
print()

print('Code of parallelized function:')
print('-' * 30)
print(getstr(rewriter.funcDef))
