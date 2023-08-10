# input: 1.funcArgs.pkl
# find functions that can run for longer than 1 second by scaling input arguments, store them to 2.log.txt
# output: 2.log.txt

from inputgenerate import InputGenerator
from filter import ndarray_args
import pickle
import numpy as np
from generator import generate_args_kargs_ndarray, try_convert_to_ndarray, size_of

if __name__ == '__main__':
    import sys
    outFile = sys.stdout #open('2.get_scalable.out', 'a+')

    #orig_stdout = sys.stdout
    #orig_stderr = sys.stderr
    #sys.stdout = open('/dev/null', 'w')
    #sys.stderr = open('/dev/null', 'w')
    
    
    funcArgs = pickle.load(open('1.funcArgs.pkl', 'rb'))
    cnt = 0
    
    for i, (this_func, (funcobj, args, kargs)) in enumerate(funcArgs.items()):
        args, kargs = try_convert_to_ndarray(funcobj, args, kargs)
        if len(ndarray_args((this_func, (funcobj, args, kargs)))) == 0:
            continue

        print(i, '/', len(funcArgs), this_func, file=outFile)

        ig = InputGenerator(funcobj, args, kargs, MIN_RUNTIME=5.0, MAX_TIMEOUT=20.0)
        if not ig.N:
            print(ig.reason, file=outFile)
            continue
        print(ig.N, ig.runTime,file=outFile)
        with open ('2.log.txt', 'a+') as logf:
            file, module, func = this_func
            print(file, module, func, ig.N, file=logf)
        del ig
        del args
        del kargs

        outFile.flush()
        #nfuncArgs[this_func] = (funcobj, args, kargs)

    #sys.stdout = orig_stdout
    #ssys.stderr = orig_stderr
