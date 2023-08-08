def print_parallelizables(parallelizer):
    # print parallelizables
    for dumpStr, pklLst, func in parallelizer.parallelizables:
        print('=' * 50)
        print(func)
        print(dumpStr)
        #print(pklLst)

def print_rewrite(parallelizer, idx):
    # rewrite target function into parallelized version
    from pypar import rewrite
    from pypar.basics.utils import getstr

    assistantFuncDefs, funcDef = rewrite(parallelizer.parallelizables[idx][1], framework='ray')

    for aFuncDef in assistantFuncDefs:
        print(getstr(aFuncDef))
    print(getstr(funcDef))