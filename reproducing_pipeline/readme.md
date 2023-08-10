# Reproducing experiment results

This directory contains scripts for reproducing the experiment results in the published work.

These scripts provide following functionalities:

+ collect function calls from `pytest` scripts and example programs of target package
+ generate input of suitable size for these functions
+ discover parallelisms and rewrite
+ measure acceleration

## Requirements

```
pytest==7.2.1
ray==1.11.0
```

In the published work, we conduct experiments on 6 packages, their versions are:

```
scikit-image==0.19.3
scipy==1.9.1
librosa==0.9.2
trimesh==3.16.3
scikit-learn==1.2.2
seaborn==0.11.2
```

## Structure

`0.collect.1.py`, `0.collect.2.py`, `1.merge.py`, `2.get_scalable.py`, `3.parallelize.py`, `4.rewrite.py` and `5.eval.py` constitute a pipeline. One should run them serially  to reproduce the experiment results.

`filter.py`, `generator.py` and `inputgenerate.py` provide utilities for input generation.

`stats.py` is used to store relevant information.

`2.log.txt` and  `timing/*` are intermediate results (on package `Seaborn`).

## Workflow 

### collect function calls and their arguments

```bash
python3 0.collect.1.py
```

This script collects calls to target package's functions and their arguments from `pytest` scripts, and store them to `0.funcArgs.pkl`.  

To run the script, change `'/path_to_seaborn_package'` in the script to path to target package (usually it is `'~/.local/lib/python3.8/site-packages/package_name'`).

```bash
python3 0.collect.2.py
```

This script collects calls to target package's functions and their arguments from example programs and store them to `./pkls/` directory. The example programs are provided by many packages, for example, https://github.com/scikit-learn/scikit-learn/tree/main/examples, https://github.com/mwaskom/seaborn/tree/master/examples.

To run the script, change `'/path_to_seaborn_package'` in the script to path to target package (usually it is `'~/.local/lib/python3.8/site-packages/package_name'`). Change `'/path_to_pkls/'` in the script to absolute path of `./pkls`. Download the example programs, and change `'/path_to_example_programs'` in the script to the absolute path of the example programs.

```bash
python3 1.merge.py
```

This script merges the function calls and arguments in `0.funcArgs.pkl` and `./pkls/`, and store them to `1.funcArgs.pkl`.

The number of function calls collected should be assigned to `n_traced` in `stats.py`.

### generate inputs

This step generate inputs of proper size for function calls collected by previous step.

The generated inputs will be used to run the target function.

```bash
python3 2.get_scalable.py
```

This script finds functions that can run for longer than 1 second by scaling input arguments, and store them to `2.log.txt`.

The generated inputs in `2.log.txt` should also be assigned to `funcN` in `stats.py`.

The manually generated inputs should be stored in `funcInput` in `stats.py`.

### discover parallelisms and rewrite

```bash
python3 3.parallelize.py
```

This script uses `DynamicParallelizer` to find parallelizable functions, and store them to `3.parallelizable_funcs.pkl`.

```bash
python3 4.rewrite.py
```

This script rewrites the parallelizable functions into parallelized versions (using `concurrent.futures` and `ray`), and print them to `stdout`.

One should check the correctness of parallelisms. If the parallelism is not false positive, one can paste the parallelized version to target package.

### measure acceleration

```bash
python3 5.eval.py
```

This script runs the parallelizable functions and their parallelized versions for 100 times, and dump the timing results to `./timing/ `directory.

