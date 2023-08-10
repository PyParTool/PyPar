# PyPar

PyPar is a tool for automatically discovering parallelization possibilities in Python programs. It leverages data dependence analysis and graph-theoretic methods to find parallelisms and uses dynamic analysis to select useful parallelisms.

## Published Work

Discovering Parallelisms in Python Programs, ESEC/FSE 2023.

## Installation

### requirements:

```
python==3.8.10
astunparse==1.6.3
```

If you want to run `usage.py`, install:

```
scikit-image==0.19.3
```

### install:

```shell
python3 setup.py sdist
python3 setup.py install --prefix ~/.local/
```

## Usage

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

`Loop` indicates that parallelism is within a loop.

`Code: ...` gives the code piece that has parallelization possibilities.

`compute_hessian_eigenvalues(image, sigma, sorting='abs', mode=mode, cval=cval)` gives the parallelizable task.

`expected parallel time:  0.4581724658450882` gives the expected running time  after parallelization.

### Print parallelized code

```python
from pypar import print_rewrite
print_rewrite(parallelizer, 0)
```

This prints the parallelized code (using Ray).

### More

For more information, see `docs/`

## Reproducing

To reproduce the experiment results in the published work, one should use a set of scripts to:

+ collect function calls from `pytest` scripts and example programs of the target package
+ generate input of suitable size for these functions
+ discover parallelisms and rewrite
+ measure acceleration

We provide these scripts in the directory `reproducing_pipeline/`. It is immediately executable for package `Seaborn`. One can change the package directory in these scripts to reproduce results on other packages.

See `reproducing_pipeline/readme.md` for more information.

