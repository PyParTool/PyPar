# utils

The directory `pypar/utils/` provides high level interfaces to use the PyPar tool and utilities for experiments.

## Dynamic parallelizer

`class DynamicParallelizer`  in `pypar/utils/DynamicParallelizer.py`discovers parallelisms and uses dynamic selection strategy to find ones that can introduce considerable acceleration.

`class DynamicParallelizerWithWriteObj`  in  `pypar/utils/DynamicParallelizer.py` also discovers parallelisms and adopts dynamic selection strategy. In addition, it uses dynamic dependence analysis to reduce false negatives. It can find more parallelisms than `DynamicParallelizer` in some cases.

### Prepare input

Suppose we want to find parallelisms in function `skimage.filters.ridges.frangi`:


```python
from skimage.filters.ridges import frangi 
```

Prepare input for this function:

```python
import numpy as np
N = 1000
np.random.seed(1)
image = np.random.uniform(size=(N, N), low=0.0, high=1.0)
```

The code to run the target function:

```python
code = 'frangi(image)'
```

### Discover parallelism

Use `DynamicParallelizer` to find parallelisms:

```python
from pypar import DynamicParallelizer        
parallelizer = DynamicParallelizer(
    code=code, 
    glbs=globals(),
    lcls=locals())
```

The detected parallelisms are recorded in `DynamicParallelizer` object.

### Print parallelism report

```python
from pypar import print_parallelizables
print_parallelizables(parallelizer)
```

The parallelism report is like this:

```
==================================================
('/path_to_skimage_package/skimage/filters/ridges.py', 'ridges', 'frangi')
Loop
--------------------------------------------------
Code:
for (i, sigma) in enumerate(sigmas):
    (lambda1, *lambdas) = compute_hessian_eigenvalues(image, sigma, sorting='abs', mode=mode, cval=cval)
    r_a = (np.inf if (ndim == 2) else (_divide_nonzero(*lambdas) ** 2))
    filtered_raw = (np.abs(np.multiply.reduce(lambdas)) ** (1 / len(lambdas)))
    r_b = (_divide_nonzero(lambda1, filtered_raw) ** 2)
    r_g = sum(([(lambda1 ** 2)] + [(lambdai ** 2) for lambdai in lambdas]))
    filtered_array[i] = (((1 - np.exp(((- r_a) / alpha_sq))) * np.exp(((- r_b) / beta_sq))) * (1 - np.exp(((- r_g) / gamma_sq))))
    lambdas_array[i] = np.max(lambdas, axis=0)
--------------------------------------------------
compute_hessian_eigenvalues(image, sigma, sorting='abs', mode=mode, cval=cval)
--------------------------------------------------
N_loop:  5
parallel_degree:  5
expected parallel time:  0.4581724658450882
```

`('/path_to_skimage_package/skimage/filters/ridges.py', 'ridges', 'frangi')` gives the parallelizable function.

`Loop` indicates the parallelism is within a loop.

`Code: ...` gives the code piece that has parallelization possibilities.

`compute_hessian_eigenvalues(image, sigma, sorting='abs', mode=mode, cval=cval)` gives the parallelizable task.

`expected parallel time:  0.4581724658450882` gives the expected running time  after parallelization.

### Print parallelized code

```python
from pypar import print_rewrite
print_rewrite(parallelizer, 0)
```

This prints the parallelized code (using Ray).

## Static parallelizer

`class DynamicParallelizer`  in `pypar/utils/DynamicParallelizer.py`discovers parallelisms but does not use dynamic selection strategy. Thus, it can discover many parallelisms that can not yield acceleration.

Usage:

```python
from skimage.filters.ridges import frangi 
from pypar import StaticParallelizer
parallelizer = StaticParallelizer(frangi)

from pypar import print_parallelizables
print_parallelizables(parallelizer)
```

Output:

```
==================================================
('/path_to_skimage_package/skimage/filters/ridges.py', '8/site-packages/skimage/filters/ridges', 'frangi')
Seq
--------------------------------------------------
Code:
warn('Use keyword parameter `sigmas` instead of `scale_range` and `scale_range` which will be removed in version 0.17.', stacklevel=2)
sigmas = np.arange(scale_range[0], scale_range[1], scale_step)
--------------------------------------------------
warn('Use keyword parameter `sigmas` instead of `scale_range` and `scale_range` which will be removed in version 0.17.', stacklevel=2)
sigmas = np.arange(scale_range[0], scale_range[1], scale_step)
--------------------------------------------------

==================================================
('/path_to_skimage_package/skimage/filters/ridges.py', '8/site-packages/skimage/filters/ridges', 'frangi')
Seq
--------------------------------------------------
Code:
check_nD(image, [2, 3])
sigmas = _check_sigmas(sigmas)
alpha_sq = (2 * (alpha ** 2))
beta_sq = (2 * (beta ** 2))
gamma_sq = (2 * (gamma ** 2))
ndim = image.ndim
--------------------------------------------------
ndim = image.ndim
gamma_sq = (2 * (gamma ** 2))
alpha_sq = (2 * (alpha ** 2))
check_nD(image, [2, 3])
sigmas = _check_sigmas(sigmas)
beta_sq = (2 * (beta ** 2))
--------------------------------------------------

==================================================
('/path_to_skimage_package/skimage/filters/ridges.py', '8/site-packages/skimage/filters/ridges', 'frangi')
Seq
--------------------------------------------------
Code:
(lambda1, *lambdas) = compute_hessian_eigenvalues(image, sigma, sorting='abs', mode=mode, cval=cval)
r_a = (np.inf if (ndim == 2) else (_divide_nonzero(*lambdas) ** 2))
filtered_raw = (np.abs(np.multiply.reduce(lambdas)) ** (1 / len(lambdas)))
r_b = (_divide_nonzero(lambda1, filtered_raw) ** 2)
r_g = sum(([(lambda1 ** 2)] + [(lambdai ** 2) for lambdai in lambdas]))
filtered_array[i] = (((1 - np.exp(((- r_a) / alpha_sq))) * np.exp(((- r_b) / beta_sq))) * (1 - np.exp(((- r_g) / gamma_sq))))
lambdas_array[i] = np.max(lambdas, axis=0)
--------------------------------------------------
lambdas_array[i] = np.max(lambdas, axis=0)
(lambda1, *lambdas) = compute_hessian_eigenvalues(image, sigma, sorting='abs', mode=mode, cval=cval)
r_a = (np.inf if (ndim == 2) else (_divide_nonzero(*lambdas) ** 2))
filtered_raw = (np.abs(np.multiply.reduce(lambdas)) ** (1 / len(lambdas)))
--------------------------------------------------
lambdas_array[i] = np.max(lambdas, axis=0)
r_b = (_divide_nonzero(lambda1, filtered_raw) ** 2)
r_g = sum(([(lambda1 ** 2)] + [(lambdai ** 2) for lambdai in lambdas]))
r_a = (np.inf if (ndim == 2) else (_divide_nonzero(*lambdas) ** 2))
--------------------------------------------------
lambdas_array[i] = np.max(lambdas, axis=0)
filtered_array[i] = (((1 - np.exp(((- r_a) / alpha_sq))) * np.exp(((- r_b) / beta_sq))) * (1 - np.exp(((- r_g) / gamma_sq))))
--------------------------------------------------

==================================================
('/path_to_skimage_package/skimage/filters/ridges.py', '8/site-packages/skimage/filters/ridges', 'frangi')
Loop
--------------------------------------------------
Code:
for (i, sigma) in enumerate(sigmas):
    (lambda1, *lambdas) = compute_hessian_eigenvalues(image, sigma, sorting='abs', mode=mode, cval=cval)
    r_a = (np.inf if (ndim == 2) else (_divide_nonzero(*lambdas) ** 2))
    filtered_raw = (np.abs(np.multiply.reduce(lambdas)) ** (1 / len(lambdas)))
    r_b = (_divide_nonzero(lambda1, filtered_raw) ** 2)
    r_g = sum(([(lambda1 ** 2)] + [(lambdai ** 2) for lambdai in lambdas]))
    filtered_array[i] = (((1 - np.exp(((- r_a) / alpha_sq))) * np.exp(((- r_b) / beta_sq))) * (1 - np.exp(((- r_g) / gamma_sq))))
    lambdas_array[i] = np.max(lambdas, axis=0)
--------------------------------------------------
sum(([(lambda1 ** 2)] + [(lambdai ** 2) for lambdai in lambdas]))
--------------------------------------------------
np.exp(((- r_b) / beta_sq))
--------------------------------------------------
np.multiply.reduce(lambdas)
--------------------------------------------------
np.max(lambdas, axis=0)
--------------------------------------------------
_divide_nonzero(lambda1, filtered_raw)
--------------------------------------------------
np.exp(((- r_a) / alpha_sq))
--------------------------------------------------
compute_hessian_eigenvalues(image, sigma, sorting='abs', mode=mode, cval=cval)
--------------------------------------------------
np.exp(((- r_g) / gamma_sq))
--------------------------------------------------
len(lambdas)
--------------------------------------------------
np.abs(np.multiply.reduce(lambdas))
--------------------------------------------------

==================================================
('/path_to_skimage_package/skimage/filters/ridges.py', '8/site-packages/skimage/filters/ridges', 'frangi')
Comp
--------------------------------------------------
[(lambdai ** 2) for lambdai in lambdas]
--------------------------------------------------
```

## Function call tracer

`class FuncTracer` in `pypar/utils/FuncCallTracer.py` traces all function calls in a Python program. It is a helper class for experiment.

For its usage, see `seaborn_pipeline/0.collect.1.py` and `seaborn_pipeline/0.collect.2.py`. 

## Evaluator

`class Evaluator` in `pypar/utils/Evaluator.py` evaluates the accelerations brought by parallelization. It is a helper class for experiment.

For its usage, see `seaborn_pipeline/5.eval.py`.

## Rewriter

Function `rewrite` in `pypar/utils/Rewriter.py` provides an easy-to-use API for rewriting parallelizable functions into parallelized versions. One can choose to use `ray`, `concurrent.futures.ThreadPoolExecutor` or `concurrent.futures.ProcessPoolExecutor`  by specifying the `framework` argument.