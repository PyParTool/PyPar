import copy
MAX_TIME = 40
class Evaluator:
    def __init__(self, 
                N_WARMUP = 2, N_REPEAT = 5,
                METHOD_DICT = None,
                init_code = None,
                run_code = None,
                prepare_code = None,
                extra_locals = {}):
        from time import monotonic as _time
        import numpy as np
        import ray

        np.random.seed(1)

        timings = {}

        for k, v in extra_locals.items():
            locals()[k] = v
        
        exec(init_code, globals(), locals())

        for method, func in METHOD_DICT:
            print('Running Method', method)
            tims = []
            if method == 'ray2':
                ray.init()
            for i in range(N_REPEAT + N_WARMUP):
                print(i, '/', N_REPEAT + N_WARMUP)
                if method == 'ray':
                    ray.init()
                if prepare_code:
                    exec(prepare_code, globals(), locals())
                st = _time()
                exec(run_code, globals(), locals())
                if i >= N_WARMUP:
                    tims.append(_time() - st)
                if method == 'ray':
                    ray.shutdown()
                one_time = _time() - st
                if one_time >= MAX_TIME:
                    tims.append(_time() - st)
                    break
            if method == 'ray2':
                ray.shutdown()
            timings[method] = (np.mean(tims), np.std(tims))
            print(timings[method][0], '+-', timings[method][1])

        for method, (t, std) in timings.items():
            print(method, "%.3f" % t, '+-', "%.3f" % std)

        self.timings = timings
        