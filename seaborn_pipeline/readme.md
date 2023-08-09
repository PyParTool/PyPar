# Reproducing experiment results on Seaborn

This directory contains code for reproducing the experiment results in the published work on package `Seaborn`. Code for reproducing experiment results on other packages are essentially the same.

## Requirements

```
seaborn==0.11.2
pytest==7.2.1
ray==1.11.0
```

## Workflow

### collect function calls and their arguments

```bash
python3 0.collect.1.py
```

This program collect calls of functions in `seaborn` and their arguments from `pytest` scripts, and store them to `0.funcArgs.pkl`.

```bash
python3 0.collect.2.py
```

This program collect calls of functions in `seaborn` and their arguments from `seaborn` example programs (see [seaborn examples](https://github.com/mwaskom/seaborn/tree/master/examples)), and store them to `./pkls/` directory.

```bash
python3 1.merge.py
```

This program merge the function calls and arguments in `0.funcArgs.pkl` and `./pkls/`, and store them to `1.funcArgs.pkl`.

### generate inputs

This step generate inputs of proper size for function calls collected by previous step.

The generated inputs will be used to run the target function.

```bash
python3 2.get_scalable.py
```

This program find functions that can run for longer than 1 second by scaling input arguments, and store them to `2.log.txt`.

### discover parallelisms and rewrite

```bash
python3 3.parallelize.py
```

This program use `DynamicParallelizer` to find parallelizable functions, and store them to `3.parallelizable_funcs.pkl`.

```bash
python3 4.rewrite.py
```

This program rewrite the parallelizable functions into parallelized versions (using `concurrent.futures` and `ray`), and print them to `stdout`.

One should check the correctness of parallelisms. If the parallelism is not false positives, one can paste the parallelized version to `seaborn` package.

### measure acceleration

```bash
python3 5.eval.py
```

This program run the parallelizable functions and their parallelized versions for 100 times, and dump the timing results to `./timing/ `directory.

