if __name__ == '__main__':

    # we want to find parallelisms in function 
    #   skimage.filters.ridges.frangi
    from skimage.filters.ridges import frangi 
    
    # prepare input for DynamicParallelizer
    import numpy as np
    N = 1000
    np.random.seed(1)
    image = np.random.uniform(size=(N, N), low=0.0, high=1.0)
    
    # code to run the target function
    code = 'frangi(image)'

    from pypar import DynamicParallelizer

    # discover parallelisms        
    parallelizer = DynamicParallelizer(
        code=code, 
        glbs=globals(),
        lcls=locals())

    # print the parallelism report
    from pypar import print_parallelizables
    print_parallelizables(parallelizer)

    # auto-rewrite target function into parallelized version
    from pypar import print_rewrite
    print_rewrite(parallelizer, 0)