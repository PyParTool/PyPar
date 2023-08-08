# input: 3.parallelizable_funcs.pkl
# rewrite parallelizable functions into parallelized versions
# output: stdout

import pickle
import stats
from pypar import rewrite
from pypar.basics.utils import getstr

if __name__ == '__main__':
    parallelizable_funcs = pickle.load(open('3.parallelizable_funcs.pkl', 'rb'))
    parallelizables = {func:parallelizable_funcs[func][0] for func in stats.parallelizables}

    for f, (dumpStr, pklLst, func, this_func) in parallelizables.items():
        print('=' * 50)
        print(func)
        print(this_func)
        print(dumpStr)
        input()

        for frame in ['thread', 'process', 'ray']:
            funcDefs, pfuncdef = rewrite(pklLst, framework=frame)
            for funcdef in funcDefs:
                print(getstr(funcdef))
            print(getstr(pfuncdef))
            
            input()

