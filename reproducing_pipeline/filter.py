import numpy as np

def ndarray_args(item):
    func, (funcobj, args, kargs) = item
    ndarray_args = []
    for arg in args:
        if isinstance(arg, np.ndarray) and arg.ndim >= 1:
            ndarray_args.append(('None', arg))
    for k, arg in kargs.items():
        if isinstance(arg, np.ndarray) and arg.ndim >= 1:
            ndarray_args.append((k, arg))
    return ndarray_args

def filter_no_ndarray(item):
    arr_args = ndarray_args(item)
    return len(arr_args) > 0
    
def filter_ndarray_more_than_one(item):
    arr_args = ndarray_args(item)
    return len(arr_args) > 1
