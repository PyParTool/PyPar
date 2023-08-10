import numpy as np
from math import floor, ceil
from pandas.core.frame import DataFrame
import sys
np.random.seed(1)

## generators
# generate function must follow the scheme
# def generate_xxx(N, referenced_object)
# generate a obj of size N refering to existing obj

def generate_ndarray(refered_arr, shape):
    assert(isinstance(refered_arr, np.ndarray))

    dtype = refered_arr.dtype
    
    mi = 0
    ma = 1
    try:
        mi = max(np.min(refered_arr), -100)
        ma = min(np.max(refered_arr), 100)
    except:
        pass
    if mi >= ma:
        mi, ma = ma, mi
    
    if 'float' in dtype.__str__():
        try:
            res = np.random.uniform(size=shape, low=mi, high=ma)
        except Exception as e:
            res = np.random.uniform(size=shape, low=0, high=1)
        return res
    elif 'int' in dtype.__str__():
        return np.random.randint(size=shape, low=mi, high=ma + 1, dtype=dtype)
    elif 'bool' in dtype.__str__():
        return np.random.randint(size=shape, low=0, high=2) > 0
    elif 'complex' in dtype.__str__():
        return np.random.normal(size=shape) + \
                    1.0j * np.random.normal(size=shape)
    elif '<U' in dtype.__str__():
        letters = [chr(i + 65) for i in range(26)]
        return np.random.choice(letters, size=shape)
    elif 'object' in dtype.__str__():
        return refered_arr
    else:
        print(dtype.__str__())
        raise

def generate_one_ndarray(refered_arr, N):
    assert(isinstance(refered_arr, np.ndarray))
    
    ndim = refered_arr.ndim

    ratio = (N / refered_arr.size) ** (1 / ndim)
    nshape = [ceil(ratio * d) for d in refered_arr.shape]

    return generate_ndarray(refered_arr, nshape)

def generate_two_ndarrays(refered_arr1, refered_arr2, N):
    # generate new arrs by scale the two given arrs in the same ratio
    assert(isinstance(refered_arr1, np.ndarray))
    assert(isinstance(refered_arr2, np.ndarray))

    ndim1 = refered_arr1.ndim
    ndim2 = refered_arr2.ndim

    if ndim1 == ndim2:
        ratio = (N / (refered_arr1.size + refered_arr2.size)) ** (1 / ndim1)
    elif ndim1 < ndim2:
        ratio = (N / (refered_arr2.size)) ** (1 / ndim2)
    elif ndim1 > ndim2:
        ratio = (N / (refered_arr1.size)) ** (1 / ndim1)
    else:
        # other cases: too few and don't consider
        raise

    nshape1 = [ceil(ratio * d) for d in refered_arr1.shape]
    nshape2 = [ceil(ratio * d) for d in refered_arr2.shape]

    return generate_ndarray(refered_arr1, nshape1), \
            generate_ndarray(refered_arr2, nshape2)

def get_ndarray_idxs(all_kargs):
    idxs = []
    for k, v in all_kargs.items():
        if isinstance(v, np.ndarray):
            idxs.append(k)
    return idxs

## previous version
'''def generate_args_kargs_ndarray(args, kargs, N):
    all_kargs = {}
    for i, arg in enumerate(args):
        all_kargs[i] = arg
    for k, v in kargs.items():
        all_kargs[k] = v
    
    idxs = get_ndarray_idxs(all_kargs)

    if len(idxs) == 1:
        idx = idxs[0]
        all_kargs[idx] = generate_one_ndarray(all_kargs[idx], N)
    elif len(idxs) == 2:
        idx1, idx2 = idxs
        all_kargs[idx1], all_kargs[idx2] = generate_two_ndarrays(all_kargs[idx1], all_kargs[idx2], N)
    else:
        # other cases
        # should have been filtered
        raise

    for k, v in all_kargs.items():
        if isinstance(k, int):
            args[k] = v
        elif isinstance(k, str):
            kargs[k] = v
        else:
            raise
    
    return args, kargs
'''

import linecache
import inspect
import ast
## get source from funcobj
def getSourceCode(func):
    file = func.__code__.co_filename
    lineno = func.__code__.co_firstlineno

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

def getAllArgs(code):
    root = ast.parse(code)
    assert(isinstance(root, ast.Module))
    funcDef = root.body[0]
    assert(isinstance(funcDef, ast.FunctionDef))

    vararg = funcDef.args.vararg
    if vararg:
        vararg = vararg.arg
    
    kwarg = funcDef.args.kwarg
    if kwarg:
        kwarg = kwarg.arg

    argNames = list(map(lambda x: x.arg, funcDef.args.args))

    argNames = [argName for argName in argNames if argName != vararg and argName != kwarg]
    return argNames

def rescale_scalar(arg, ratio):
    if arg is None:
        return None
    if isinstance(arg, int):
        arg = ceil(arg * ratio)
    elif isinstance(arg, float):
        arg = arg * ratio
    elif isinstance(arg, tuple):
        arg = (rescale_scalar(a, ratio) for a in arg)
    elif isinstance(arg, list):
        arg = [rescale_scalar(a, ratio) for a in arg]
    else:
        print(type(arg))
        #print(arg)
        raise
    
    return arg

def is_size_shape_name(name):
    possible_Names = [
        'shape',
        'size',
        'sz'
    ]
    for nm in possible_Names:
        if nm in name:
            return True
        else:
            return False

def printAST(funcobj):
    code = getSourceCode(funcobj)
    root = ast.parse(code)
    assert(isinstance(root, ast.Module))
    funcDef = root.body[0]
    assert(isinstance(funcDef, ast.FunctionDef))
    print(ast.dump(funcDef.args))

def is_list_tuple_of_ndarray(arg):
    if isinstance(arg, tuple) or \
        isinstance(arg, list):
        if len(arg) == 0:
            return False
        for a in arg:
            if not isinstance(a, np.ndarray):
                return False
        return True
    else:
        return False

def generate_args_kargs_ndarray(funcobj, args, kargs, N, min_ratio = 1.0):
    # N = -1, return original input
    if N == -1:
        return args, kargs
    # rescale all ndarray parameters with the same ratio
    # also rescale scalar values such as shape, size
    
    # get the argument name for args
    code = getSourceCode(funcobj)
    argNames = getAllArgs(code)
    argNames = [argName for argName in argNames if argName not in kargs]

    # get the max ndim of all ndarray arguments
    idxs = []
    max_ndim = -1
    for i, arg in enumerate(args):
        if isinstance(arg, np.ndarray) and arg.ndim >= 1:
            idxs.append(i)
            max_ndim = max(max_ndim, arg.ndim)
        elif is_list_tuple_of_ndarray(arg):
            idxs.append(i)
            mndim = max(map(lambda a: a.ndim, arg))
            max_ndim = max(max_ndim, mndim)
    for k, arg in kargs.items():
        if isinstance(arg, np.ndarray) and arg.ndim >= 1:
            idxs.append(k)
            max_ndim = max(max_ndim, arg.ndim)
        elif is_list_tuple_of_ndarray(arg):
            idxs.append(k)
            mndim = max(map(lambda a: a.ndim, arg))
            max_ndim = max(max_ndim, mndim)
    # the func should have ndarray args
    assert(len(idxs) > 0)

    # calculate the rescale ratio
    total_size = 0
    for k in idxs:
        if isinstance(k, int):
            arg = args[k]
        else:
            arg = kargs[k]

        if isinstance(arg, np.ndarray):
            if arg.ndim == max_ndim:
                total_size += arg.size
        else:
            assert(is_list_tuple_of_ndarray(arg))
            for a in arg:
                assert(isinstance(a, np.ndarray))
                if a.ndim == max_ndim:
                    total_size += a.size
    
    if total_size == 0:
        # avoid divided by zero
        total_size = 1
        
    ratio = max((N / total_size) ** (1 / max_ndim), min_ratio)

    # rescale ndarray parameters
    for k in idxs:
        if isinstance(k, int):
            arg = args[k]
        else:
            arg = kargs[k]

        if isinstance(arg, np.ndarray):
            nshape = [ceil(ratio * d) for d in arg.shape]
            narg = generate_ndarray(arg, nshape)
        else:
            assert(is_list_tuple_of_ndarray(arg))
            narg = []
            for a in arg:
                assert(isinstance(a, np.ndarray))
                nshape = [ceil(ratio * d) for d in a.shape]
                narg.append(generate_ndarray(a, nshape))

        if isinstance(k, int):
            args[k] = narg
        else:
            kargs[k] = narg
    
    # rescale scalars with name shape, size ...
    for i, arg in enumerate(args):
        if i >= len(argNames):
            continue
        k = argNames[i]
        if is_size_shape_name(k):
            args[i] = rescale_scalar(arg, ratio)

    for k, arg in kargs.items():
        if is_size_shape_name(k):
            #print(k, arg)
            #print(kargs)
            kargs[k] = rescale_scalar(arg, ratio)
    
    return args, kargs

def size_of(args, kargs):
    siz = 0
    for v in args:
        siz += sys.getsizeof(v)
    for k, v in kargs.items():
        siz += sys.getsizeof(v)
    return siz

def try_convert_to_ndarray(funcobj, args, kargs):
    import sys
    for i in range(len(args)):
        orig_a = args[i]
        if 'scipy.sparse' in str(orig_a.__class__) and \
            'matrix' in str(orig_a.__class__):
            try:
                args[i] = orig_a.toarray()
                funcobj(*args, **kargs)
            except:
                args[i] = orig_a
        elif isinstance(orig_a, DataFrame):
            try:
                args[i] = orig_a.values
                funcobj(*args, **kargs)
            except:
                args[i] = orig_a
    
    for k in kargs.keys():
        orig_v = kargs[k]
        if 'scipy.sparse' in str(orig_v.__class__) and \
            'matrix' in str(orig_v.__class__):
            try:
                kargs[k] = orig_v.toarray()
                funcobj(*args, **kargs)
            except:
                kargs[k] = orig_v
        elif isinstance(orig_v, DataFrame):
            try:
                kargs[k] = orig_v.values
                funcobj(*args, **kargs)
            except:
                kargs[k] = orig_v
    
    '''if size_of(args, kargs) >= 100000000:
        #o_args, o_kargs = args, kargs
        args, kargs = generate_args_kargs_ndarray(funcobj, args, kargs, 10000000, min_ratio=0.0)
    '''
    '''try:
            funcobj(*args, **kargs)
            return args, kargs
        except:
            return o_args, o_kargs
        '''
    return args, kargs

if __name__ == '__main__':
    from scipy.signal._signaltools import _freq_domain_conv
    from scipy.optimize._numdiff import approx_derivative
    #code = getSourceCode(approx_derivative)
    #allArgs = getAllArgs(code)
    #print(allArgs)

    '''np.random.seed(1)
    N = 10 ** 2
    shape = [2 * N - 1]
    axes = [0]
    rng = np.random.default_rng(1234)
    a = rng.standard_normal(N)
    b = rng.standard_normal(N)

    args = [a, b, axes, shape]
    kargs = {'calc_fast_len': True}

    args, kargs = generate_args_kargs_ndarray(_freq_domain_conv, args, kargs, 10000)

    for arg in args:
        if isinstance(arg, np.ndarray):
            print(arg.shape, end = ' ')
        else:
            print(arg, end = ' ')
    print()
    '''

    from scipy.stats import _cdf_distance
    N = 10
    rng = np.random.default_rng(12345678)
    u_values = rng.random(N) * 10
    u_weights = rng.random(N) * 10
    v_values = rng.random(N) * 10
    v_weights = rng.random(N) * 10

    args = [2, u_values, v_values, u_weights, v_weights]
    kargs = {}
    args, kargs = generate_args_kargs_ndarray(_cdf_distance, args, kargs, 10000)
    for arg in args:
        if isinstance(arg, np.ndarray):
            print(arg.shape, end = ' ')
        else:
            print(arg, end = ' ')
    print()