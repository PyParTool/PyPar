from pypar.utils.Evaluator import Evaluator
import importlib
import sys

def timing_func(moduleName, clsName, funcName, args, kargs, TEST_MODE = False):
    pac = importlib.import_module(moduleName)

    if not clsName:    
        seq_func = getattr(pac, funcName)
        ray_func = getattr(pac, funcName + '_ray')
        thread_func = getattr(pac, funcName + '_thread')
        process_func = getattr(pac, funcName + '_process')
    else:
        cls = getattr(pac, clsName)
        seq_func = getattr(cls, funcName)
        ray_func = getattr(cls, funcName + '_ray')
        thread_func = getattr(cls, funcName + '_thread')
        process_func = getattr(cls, funcName + '_process')

    init_code = ''
    run_code = 'func(*args, **kargs)'

    METHOD_DICT = [
        ('sequence', seq_func),
        ('concurrent_thread', thread_func),
        ('concurrent_process', process_func),
        ('ray2', ray_func),
    ]

    if TEST_MODE:
        N_REPEAT = 1
        N_WARMUP = 0
    else:
        N_REPEAT = 100
        N_WARMUP = 2
        f = open('timing/' + moduleName + '-' + str(clsName) + '-' + funcName + '.res', 'w')
        origStdout = sys.stdout
        sys.stdout = f

    Evaluator(
        N_REPEAT=N_REPEAT,
        N_WARMUP=N_WARMUP,
        METHOD_DICT=METHOD_DICT, 
        init_code=init_code, 
        run_code=run_code,
        extra_locals={
            'args': args,
            'kargs': kargs,
        })
    
    if not TEST_MODE:
        f.close()
        sys.stdout = origStdout

if __name__ == '__main__':
    import os
    # to import ray
    os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

    from stats import parallelizables, funcN, funcInput
    import pickle
    from generator import generate_args_kargs_ndarray, try_convert_to_ndarray

    funcArgs = pickle.load(open('1.funcArgs.pkl', 'rb'))

    print(len(parallelizables))

    for i, this_func in enumerate(parallelizables):
        if this_func in funcInput:
            args, kargs = funcInput[this_func]
        else:
            N = funcN[this_func]
            
            funcobj, args, kargs = funcArgs[this_func]
            args, kargs = try_convert_to_ndarray(funcobj, args, kargs)
            args, kargs = generate_args_kargs_ndarray(funcobj, args, kargs, N)

        file, module, func = this_func
        moduleName = '.'.join(file.split('/')[7:])[:-3]
        if '.' in func:
            className, funcName = func.split('.')
        else:
            className = None
            funcName = func
        print('=' * 50)
        print(i, '/', len(parallelizables), moduleName, className, funcName)

        timing_func(moduleName, className, funcName, args, kargs, TEST_MODE=False)

