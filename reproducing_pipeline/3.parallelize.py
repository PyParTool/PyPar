# input: 1.funcArgs.pkl, 2.log.txt
# use DynamicParallelizer to find parallelizables, and store them
# output: 3.parallelizable_funcs.pkl

import os
# to import ray
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

from generator import generate_args_kargs_ndarray, try_convert_to_ndarray
import pickle
from pypar import DynamicParallelizer, DynamicParallelizerWithWriteObj

if __name__ == '__main__':
    funcN = {}
    with open('2.log.txt', 'r') as f:
        while True:
            stri = f.readline(-1)
            if not stri:
                break
            file, module, func, N = stri.strip().split(' ')
            this_func = (file, module, func)
            N = int(N)
            funcN[this_func] = N
    
    print(len(funcN))

    funcArgs = pickle.load(open('1.funcArgs.pkl', 'rb'))

    parallelizable_funcs = {}

    #tasks = [0 for _ in range(len(funcN))]

    nfuncArgs = {}

    forbiddens = [] 

    for i, (this_func, N) in enumerate(funcN.items()):
        print(i, '/', len(funcN), this_func, N)
        #if i <= 26:
        #    continue
        if i in forbiddens:
            continue

        funcobj, args, kargs = funcArgs[this_func]
        args, kargs = try_convert_to_ndarray(funcobj, args, kargs)
        args, kargs = generate_args_kargs_ndarray(funcobj, args, kargs, N)

        code = 'funcobj(*args, **kargs)'

        parallelizer = DynamicParallelizer(  # DynamicParallelizerWithWriteObj
            code=code, 
            glbs=globals(),
            lcls=locals()
        )

        for dumpStr, pklLst, func in parallelizer.parallelizables:
            print('=' * 50)
            print(func)
            print(dumpStr)

            if func not in parallelizable_funcs:
                parallelizable_funcs[func] = []
            
            parallelizable_funcs[func].append((dumpStr, pklLst, func, this_func))

        del args
        del kargs
        del parallelizer

    pickle.dump(parallelizable_funcs, open('3.parallelizable_funcs.pkl', 'wb'))

   