from time import monotonic as _time
import multiprocessing
import copy
from generator import generate_args_kargs_ndarray
from filter import ndarray_args
import numpy as np
import sys
import signal
import os
def worker(f, rtDct, args, kargs):
    os.setpgid(os.getpid(), os.getpid())
    try:
        origStdout = sys.stdout
        origStdErr = sys.stderr

        sys.stdout = open('/dev/null', 'w')
        sys.stderr = open('/dev/null', 'w')

        st = _time()
        f(*args, **kargs)
        rtDct['time'] = _time() - st

        sys.stdout = origStdout
        sys.stderr = origStdErr

    except Exception as e:
        rtDct['error'] = e

        sys.stdout = origStdout
        sys.stderr = origStdErr
        
class InputGenerator:
    # for scipy
    def __init__(self, f, args=[], kargs={}, MAX_TIMEOUT=2, MIN_RUNTIME=0.1, max_r=10 ** 9):
        self.f = f
        self.args = args
        self.kargs = kargs

        self.N = None
        self.reason = None
        self.suitable = None
        self.runTime = None
        
        self.MAX_TIMEOUT = MAX_TIMEOUT
        self.MIN_RUNTIME = MIN_RUNTIME

        l = 100
        r = max_r

        rt, tmpargs, tmpkargs = self.runWithSize(-1) # run with the original input
        if rt >= MIN_RUNTIME:
            # done, find the suitable input size
            self.N = -1
            self.suitable = (tmpargs, tmpkargs)
            self.runTime = rt
            return

        rt, tmpargs, tmpkargs = self.runWithSize(l)
        #self.suitable = (tmpargs, tmpkargs)
        #return
        if rt == -1:
            # error occurs
            self.reason = 'error'
            return
        elif rt >= MAX_TIMEOUT:
            # too slow
            self.reason = 'left too slow'
            return
        elif rt >= MIN_RUNTIME:
            # done, find the suitable input size
            self.N = l
            self.suitable = (tmpargs, tmpkargs)
            self.runTime = rt
            return
        
        rt, tmpargs, tmpkargs = self.runWithSize(r)
        if rt == -1:
            # error occurs
            self.reason = 'error'
            return
        elif rt < MIN_RUNTIME:
            # too quick
            self.reason = 'right too quick'
            return
        elif rt < MAX_TIMEOUT:
            # done, find the suitable input size
            self.N = r
            self.suitable = (tmpargs, tmpkargs)
            self.runTime = rt
            return
        
        while l < r:
            m = (l + r) // 2
            rt, tmpargs, tmpkargs = self.runWithSize(r)
            #print(l, r, rt)
            if rt == -1:
                # error occurs
                self.reason = 'error'
                return
            elif rt < MIN_RUNTIME:
                # too quick
                l = m
            elif rt > MAX_TIMEOUT:
                # too slow
                r = m
            else:
                # done find suitable input size
                self.N = m
                self.suitable = (tmpargs, tmpkargs)
                self.runTime = rt
                return   

            if r - l <= 5:
                self.N = m
                self.suitable = (tmpargs, tmpkargs)
                self.runTime = rt
                #self.reason = 'can not find suitable'
                return

    def runWithSize(self, N):
        args = copy.deepcopy(self.args)
        kargs = copy.deepcopy(self.kargs)

        if N != -1:
            args, kargs = generate_args_kargs_ndarray(self.f, args, kargs, N)

        return self.runOnce(self.f, args, kargs), args, kargs
        
    def runOnce(self, f, args, kargs):
        rtDct = multiprocessing.Manager().dict()
        p = multiprocessing.Process(target=worker, args=(f, rtDct, args, kargs))
        p.start()
        p.join(timeout=self.MAX_TIMEOUT)

        if 'time' in rtDct:
            # run normally, return the time
            return rtDct['time']
        elif 'error' in rtDct:
            # error occurs
            return -1
        else:
            # exceed maximum time
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except Exception as e:
                pass
            return 100
            

if __name__ == '__main__':
    from scipy.signal._signaltools import _freq_domain_conv

    np.random.seed(1)
    N = 10 ** 2
    shape = [2 * N - 1]
    axes = [0]
    rng = np.random.default_rng(1234)
    a = rng.standard_normal(N)
    b = rng.standard_normal(N)

    args = [a, b, axes, shape]
    print(list(map(lambda x: x.__class__, args)))
    kargs = {'calc_fast_len': True}
    
    ig = InputGenerator(f=_freq_domain_conv, args=args, kargs=kargs)
    print(ig.N)
    print(ig.reason)

    import scipy.fft._pocketfft.realtransforms
    '''from skimage.filters import sato
    import numpy as np
    np.random.seed(1)

    image = np.random.uniform(size=(2, 2), low=0.0, high=1.0)
    args = []
    kargs = {'image': image}

    ig = InputGenerator(f=sato, args=args, kargs=kargs)
    print(ig.N)

    '''