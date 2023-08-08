import sys
import os
import socket
import pickle
import copy
import io

class FuncCallTracer:
    def __init__(self, libName, libPath, forbiddenPath = None):
        self.libPath = libPath
        self.forbiddenPath = forbiddenPath
        self.funcArgs = {}
        self.myStdout = open('/dev/null', 'w')
        
        self.socketName = '/tmp/funcCallCollectServer' + libName

    def validFileName(self, fileName):    
        return len(fileName) >= len(self.libPath) and\
            fileName[:len(self.libPath)] == self.libPath and\
            (self.forbiddenPath is None or
                (len(fileName) < len(self.forbiddenPath) or
                    fileName[:len(self.forbiddenPath)] != self.forbiddenPath))

    def validFuncName(self, funcName):
        return funcName[0] != '<' and\
            funcName != 'check_fpu_mode' and\
            funcName != 'set_workers' and\
            funcName[:2] != '__'

    def profileFunc(self, frame, event, arg):
        if event == 'call':
            try:
                if (self.validFileName(frame.f_code.co_filename) and
                    self.validFuncName(frame.f_code.co_name)):
                    if frame.f_code.co_name in frame.f_globals or\
                        ('self' in frame.f_locals and
                        frame.f_code.co_name in dir(frame.f_locals['self'].__class__)):
                        if frame.f_code.co_name in frame.f_globals:
                            funcObj = frame.f_globals[frame.f_code.co_name]
                            args = frame.f_locals
                        else:
                            funcObj = getattr(frame.f_locals['self'].__class__, frame.f_code.co_name)
                            args = frame.f_locals
                        if hasattr(funcObj, '__code__') and funcObj.__code__ == frame.f_code:
                            self.funcArgs[funcObj] = args #frame.f_locals
                            try:
                                data = pickle.dumps((funcObj, args)) #frame.f_locals))
                            except Exception:
                                data = None
                            if data:
                                pass
                                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                                    s.connect(self.socketName)
                                    s.sendall(data)
            except Exception:
                pass
        return None
    
    def finalize(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(self.socketName)
            s.sendall(b'kill')
        
        '''print(len(self.funcArgs), file=self.myStdout)
        for func in self.funcArgs.keys():
            print(func.__code__.co_name, func.__code__.co_filename, file=self.myStdout)
        '''


def inst_copy_dict(kargs):
    n_kargs = {}
    for k, v in kargs.items():
        if k == '__class__':
            continue
        try:
            v = copy.deepcopy(v)
        except:
            pass
        n_kargs[k] = v
    return n_kargs

from trace import Trace
# without server
class FuncTracer(Trace):
    def __init__(self, 
                interestingFilePrefixs = None, 
                ignoreFilePrefixs = None, 
                reportFile=open('/dev/null', 'w'),#sys.stdout,
                errorFile=sys.stdout
                ):
        super().__init__(ignoredirs=(sys.prefix, sys.exec_prefix))
        
        self.funcArgs = {} # file_module_func -> (funcobj, args, kargs)
        self.file = reportFile

        self.errorFuncs = {}
        self.errorfile = errorFile

        self.interestingFilePrefixs = interestingFilePrefixs
        self.ignoreFilePrefixs = ignoreFilePrefixs

        self.globaltrace = self._globaltrace
        self.localtrace = None

    def isInterestingFunc(self, file, module, func):
        # ignore useless functions such as builtins
        # assume interesting and ignore do not intersect

        if (len(file) == 0 or file[0] == '<') \
            or (len(module) == 0 or module[0] == '<') \
            or (len(func) == 0 or func[0] == '<'):
            return False
        if 'tests' in file.split('/'):
            # ignore all test code
            return False
        #if func[-8:] == '__init__':
        #    return False
        if self.interestingFilePrefixs:
            for prefix in self.interestingFilePrefixs:
                if file.startswith(prefix):
                    return True
            return False
        if self.ignoreFilePrefixs:
            for prefix in self.ignoreFilePrefixs:
                if file.startswith(prefix):
                    return False
        return True
    
    def from_import_module(self, frame):
        max_depth = 3

        cframe = frame
        depth = 0
        while cframe.f_back:
            file, module, func = self.file_module_function_of(cframe.f_back)
            if func == '<module>':
                return True
            cframe = cframe.f_back
            
            depth += 1
            if depth >= max_depth:
                break
        return False

    def _globaltrace(self, frame, why, arg):
        if why == 'call':
            this_func = (self.file_module_function_of(frame))
            if not self.isInterestingFunc(*this_func):
                return None
            
            file, module, funcname = this_func

            if this_func in self.funcArgs:
                return None
            
            if '.' in funcname:
                # is a class method
                clsname, funcname = funcname.split('.')
                # ignore __init__
                #if funcname == '__init__':
                #    return None
                if 'self' in frame.f_locals:
                    funcobj = getattr(frame.f_locals['self'].__class__, funcname)
                elif 'cls' in frame.f_locals:
                    funcobj = getattr(frame.f_locals['cls'], funcname)
                else:
                    if funcname == 'wrapper':
                        return None
                    print(this_func)
                    print(frame.f_locals)
                    raise
                #kargs.pop('self')
            elif funcname in frame.f_globals:
                clsname = None
                # is a global function
                funcobj = frame.f_globals[funcname]
            else:
                # otherwise, is inner function, ignored
                #print('not cls & not global', file=self.file)

                return None


            kargs = inst_copy_dict(frame.f_locals)
            args = []
            try:
                # try to pickle function object and kargs
                pickleSuccess = False
                data = pickle.dumps(funcobj)
                data = pickle.dumps(args)
                data = pickle.dumps(kargs)
                pickleSuccess = True
                
                # copy args, kargs, in case funcobj change it
                args_copy = []
                kargs_copy = inst_copy_dict(kargs)

                # test whether can func execute successfully
                funcobj(*args_copy, **kargs_copy)

                # if can successfully run & pickle, save it
                self.funcArgs[this_func] = (funcobj, args, kargs) 

                print('-' * 50, file=self.file)
                print(this_func, file=self.file)
                print('f_locals: ', list(frame.f_locals), file=self.file)
                print('len args:', len(args), file=self.file)
                print('kargs keys:', list(kargs.keys()), file=self.file)               
                print('run normally', file=self.file)

            except Exception as e:
                f = io.StringIO()
                print('-' * 50, file=f)
                print(this_func, file=f)
                print('f_locals: ', list(frame.f_locals), file=f)
                #try:
                #    print(args, file=f)
                #    print(kargs, file=f)
                #except:
                #    pass
                try:
                    print('len args:', len(args), file=f)
                    print('kargs keys:', list(kargs.keys()), file=f)          
                except:
                    pass
                
                if not pickleSuccess:
                    print('pickleError', file=f)
                else:
                    print('execError', file=f)
                
                import traceback
                print(e, file=f)
                traceback.print_tb(e.__traceback__, file=f)

                self.errorFuncs[this_func] = f.getvalue()
            return None

    def dump(self, outFile = 'res.pkl'):
        #pass
        pickle.dump(self.funcArgs, open(outFile, 'wb'))

    def dumpErrs(self):
        cnt = 0
        for this_func, message in self.errorFuncs.items():
            if this_func in self.funcArgs:
                continue
            cnt += 1

        print('n_collected: ', len(self.funcArgs), file=self.errorfile)
        print('n_error: ', cnt, file=self.errorfile)
        
        for this_func, message in self.errorFuncs.items():
            if this_func in self.funcArgs:
                continue
            print('=' * 50, file=self.errorfile)
            print(this_func, file=self.errorfile)
            print(message, file=self.errorfile)

        print(file=self.errorfile)
        print('#' * 100, file=self.errorfile)
        print(file=self.errorfile)
        
        for this_func in self.funcArgs:
            print(this_func, file=self.errorfile)


# without server
class FuncTracer_scipy(Trace):
    def __init__(self, 
                interestingFilePrefixs = None, 
                ignoreFilePrefixs = None, 
                reportFile=open('/tmp/res.txt', 'w'),#sys.stdout,
                errorFile=open('/tmp/reserror.txt', 'w'),#sys.stderr
                default_outFile='',
                ):
        super().__init__(ignoredirs=(sys.prefix, sys.exec_prefix))
        
        self.funcDct = {}
        self.funcArgs = {} # file_module_func -> (funcobj, args, kargs)
        self.file = reportFile
        self.errorfile = errorFile
        self.default_outFile = default_outFile

        self.interestingFilePrefixs = interestingFilePrefixs
        self.ignoreFilePrefixs = ignoreFilePrefixs

        self.globaltrace = self._globaltrace
        self.localtrace = None

        self.errorFunc = {} # errorfunc -> errorMessage

    def isInterestingFunc(self, file, module, func):
        # ignore useless functions such as builtins
        # assume interesting and ignore do not intersect

        if (len(file) == 0 or file[0] == '<') \
            or (len(module) == 0 or module[0] == '<') \
            or (len(func) == 0 or func[0] == '<'):
            return False
        if 'tests' in file.split('/'):
            # ignore all test code
            return False
        if self.interestingFilePrefixs:
            for prefix in self.interestingFilePrefixs:
                if file.startswith(prefix):
                    return True
            return False
        if self.ignoreFilePrefixs:
            for prefix in self.ignoreFilePrefixs:
                if file.startswith(prefix):
                    return False
        return True
    
    def from_import_module(self, frame):
        max_depth = 3

        cframe = frame
        depth = 0
        while cframe.f_back:
            file, module, func = self.file_module_function_of(cframe.f_back)
            if func == '<module>':
                return True
            cframe = cframe.f_back
            
            depth += 1
            if depth >= max_depth:
                break
        return False

    def rearrange_args(self, frame, funcname, clsname):
        kargs = copy.deepcopy(frame.f_locals)
        args = []

        argsWords = [
            (None, ['ks_1samp', 
                    'kstest', 
                    '_wrap_scalar_function_maxfun_validation', 
                    'fsolve',
                    '_check_func',
                    'leastsq',
                    'solve_ivp',
                    'nquad',
                    'quadrature',
                    'vectorize1',
                    '_root_hybr'
                    ], 'args'),
            (['kruskal'], None, 'samples')
        ]
        kwargsWords = [
            (None, None, 'kwargs'), 
            (None, None, 'kw'), 
            (None, None, 'filter_params'), 
            (None, None, 'attr'), 
            (None, ['wilcoxon_outputs', '_moment_outputs'], 'kwds'),
            (['_root_hybr'], None, 'unknown_options'),
            (['set_integrator'], None, 'integrator_params'),
        ]
        for onlys, forbiddens, argsWord in argsWords:
            if onlys and funcname not in onlys:
                continue
            if forbiddens and funcname in forbiddens:
                continue
            if argsWord in kargs:
                keys = list(kargs.keys())
                # take all arguments before args as args (without key)
                for k in keys:
                    if k == argsWord:
                        break
                    args.append(kargs[k])
                    kargs.pop(k)

                args += list(kargs[argsWord])
                kargs.pop(argsWord)
                break
        
        
        for onlys, forbiddens, kwargsWord in kwargsWords:
            if onlys and funcname not in onlys:
                continue
            if forbiddens and funcname in forbiddens:
                continue
            if kwargsWord in kargs:
                kwargs = kargs[kwargsWord]
                for k, v in kwargs.items():
                    kargs[k] = v
                kargs.pop(kwargsWord)
                break
        if '__class__' in kargs:
            kargs.pop('__class__')
        if not clsname and 'self' in kargs:
            kargs.pop('self')
        
        return args, kargs

    def _globaltrace(self, frame, why, arg):
        if why == 'call':
            # XXX Should do a better job of identifying methods
            this_func = (self.file_module_function_of(frame))

            if not self.isInterestingFunc(*this_func):
                return None

            if this_func not in self.funcDct:
                self.funcDct[this_func] = 1
            else:
                self.funcDct[this_func] += 1

            file, module, funcname = this_func

            if this_func in self.funcArgs:
                # only consider calls to each function once
                # for speeding up
                #print('repeated call', file=self.file)
                return None
            
            if self.from_import_module(frame):
                # ignore calls from module import
                return None
                #print('from import statement, ignored', file=self.file)
            
            # for test
            #print('-' * 50)
            #print(this_func)
            #print(frame.f_locals.keys())
            #print(frame.f_locals)
            #parent_func = self.file_module_function_of(frame.f_back)
            #print(parent_func, file = self.file)

            #print(funcobj)
            
            if '.' in funcname:
                # is a class method
                clsname, funcname = funcname.split('.')
                # ignore __init__
                #if funcname == '__init__':
                #    return None
                if 'self' in frame.f_locals:
                    funcobj = getattr(frame.f_locals['self'].__class__, funcname)
                elif 'cls' in frame.f_locals:
                    funcobj = getattr(frame.f_locals['cls'], funcname)
                else:
                    print(this_func)
                    print(frame.f_locals)
                    raise
                #kargs.pop('self')
            elif funcname in frame.f_globals:
                clsname = None
                # is a global function
                funcobj = frame.f_globals[funcname]
            else:
                # otherwise, is inner function, ignored
                #print('not cls & not global', file=self.file)

                '''
                ## dump to error
                print('-' * 50, file=self.errorfile)
                print(this_func, file=self.errorfile)
                print(frame.f_locals.keys(), file=self.errorfile)
                print('not cls & not global', file=self.errorfile)
                '''

                return None

            try:
                rearrangeSuccess = False
                args, kargs = self.rearrange_args(frame, funcname, clsname)
                rearrangeSuccess = True

                # try to pickle function object and kargs
                pickleSuccess = False
                data = pickle.dumps(funcobj)
                data = pickle.dumps(args)
                data = pickle.dumps(kargs)
                pickleSuccess = True
                
                # copy args, kargs, in case funcobj change it
                args_copy = copy.deepcopy(args)
                kargs_copy = copy.deepcopy(kargs)

                # test whether can func execute successfully
                funcobj(*args_copy, **kargs_copy)

                # if can successfully run & pickle, save it
                self.funcArgs[this_func] = (funcobj, args, kargs) 

                print('-' * 50, file=self.file)
                print(this_func, file=self.file)
                print('f_locals: ', list(frame.f_locals), file=self.file)
                print('len args:', len(args), file=self.file)
                print('kargs keys:', list(kargs.keys()), file=self.file)               
                print('run normally', file=self.file)
                
                # if this_func fail previously
                # remove error message
                if this_func in self.errorFunc:
                    self.errorFunc.pop(this_func)

            except Exception as e:
                f = io.StringIO()
                print('-' * 50, file=f)
                print(this_func, file=f)
                print('f_locals: ', list(frame.f_locals), file=f)
                #try:
                #    print(args, file=f)
                #    print(kargs, file=f)
                #except:
                #    pass
                try:
                    print('len args:', len(args), file=f)
                    print('kargs keys:', list(kargs.keys()), file=f)          
                except:
                    pass
                
                if not rearrangeSuccess:
                    print('rearrangeError', file=f)
                elif not pickleSuccess:
                    print('pickleError', file=f)
                else:
                    print('execError', file=f)
                
                #known_flaws = [
                #    '__neg__'
                #]
                #if funcname not in known_flaws:
                import traceback
                print(e, file=f)
                traceback.print_tb(e.__traceback__, file=f)

                self.errorFunc[this_func] = f.getvalue()
                    # dump to errorfile
                '''print('-' * 50, file=self.errorfile)
                if pickleSuccess:
                    print('execError', file=self.errorfile)
                else:
                    print('pickleError', file=self.errorfile)
                print(this_func, file=self.errorfile)
                print(frame.f_locals.keys(), file=self.errorfile)
                print(kargs, file=self.errorfile)
                print(e, file=self.errorfile)
                traceback.print_tb(e.__traceback__, file=self.errorfile)
                '''
            '''if frame.f_code.co_name in frame.f_globals or\
                ('self' in frame.f_locals and
                frame.f_code.co_name in dir(frame.f_locals['self'].__class__)):
                if frame.f_code.co_name in frame.f_globals:
                    funcObj = frame.f_globals[frame.f_code.co_name]
                    args = frame.f_locals
                else:
                    funcObj = getattr(frame.f_locals['self'].__class__, frame.f_code.co_name)
                    args = frame.f_locals
                if hasattr(funcObj, '__code__') and funcObj.__code__ == frame.f_code:
                    self.funcArgs[funcObj] = args #frame.f_locals
                    try:
                        data = pickle.dumps((funcObj, args)) #frame.f_locals))
                    except Exception:
                        data = None
                    if data:
                        pass
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                            s.connect(self.socketName)
                            s.sendall(data)
            '''
            '''# profile call relation
            #parent_func = self.file_module_function_of(frame.f_back)
            # if (parent_func, this_func) not in self._callers:
            #    self._callers[(parent_func, this_func)] = 1
            # else:
            #    self._callers[(parent_func, this_func)] += 1
            '''
        return None

    def dump(self, outFile = 'res.pkl'):
        pickle.dump(self.funcArgs, open(outFile, 'wb'))

    def dumpErrs(self):
        for func, message in self.errorFunc.items():
            print(message, file=self.errorfile)

# with server
class FuncTracer2(Trace):
    def __init__(self,
                libName, 
                interestingFilePrefixs = None, 
                ignoreFilePrefixs = None, 
                #reportFile=open('/tmp/res.txt', 'w'),#sys.stdout,
                #errorFile=open('/tmp/reserror.txt', 'w'),#sys.stderr
                ):
        super().__init__(ignoredirs=(sys.prefix, sys.exec_prefix))
        
        #self.funcDct = {}
        #self.funcArgs = {} # file_module_func -> (funcobj, kargs)
        #self.file = reportFile
        #self.errorfile = errorFile
        
        self.interestingFilePrefixs = interestingFilePrefixs
        self.ignoreFilePrefixs = ignoreFilePrefixs

        self.globaltrace = self._globaltrace
        self.localtrace = None

        self.errorFunc = {} # errorfunc -> errorMessage

        self.socketName = '/tmp/funcCallCollectServer' + libName      
    
    def isInterestingFunc(self, file, module, func):
        # ignore useless functions such as builtins
        # assume interesting and ignore do not intersect

        if (len(file) == 0 or file[0] == '<') \
            or (len(module) == 0 or module[0] == '<') \
            or (len(func) == 0 or func[0] == '<'):
            return False
        if 'tests' in file.split('/'):
            # ignore all test code
            return False
        if self.interestingFilePrefixs:
            for prefix in self.interestingFilePrefixs:
                if file.startswith(prefix):
                    return True
            return False
        if self.ignoreFilePrefixs:
            for prefix in self.ignoreFilePrefixs:
                if file.startswith(prefix):
                    return False
        return True
    
    def from_import_module(self, frame):
        max_depth = 3

        cframe = frame
        depth = 0
        while cframe.f_back:
            file, module, func = self.file_module_function_of(cframe.f_back)
            if func == '<module>':
                return True
            cframe = cframe.f_back
            
            depth += 1
            if depth >= max_depth:
                break
        return False

    def rearrange_args(self, frame, funcname, clsname):
        kargs = copy.deepcopy(frame.f_locals)
        args = []

        argsWords = [
            (None, ['ks_1samp', 
                    'kstest', 
                    '_wrap_scalar_function_maxfun_validation', 
                    'fsolve',
                    '_check_func',
                    'leastsq',
                    'solve_ivp',
                    'nquad',
                    'quadrature',
                    'vectorize1',
                    '_root_hybr'
                    ], 'args'),
            (['kruskal'], None, 'samples')
        ]
        kwargsWords = [
            (None, None, 'kwargs'), 
            (None, None, 'kw'), 
            (None, None, 'filter_params'), 
            (None, None, 'attr'), 
            (None, ['wilcoxon_outputs', '_moment_outputs'], 'kwds'),
            (['_root_hybr'], None, 'unknown_options'),
            (['set_integrator'], None, 'integrator_params'),
        ]
        for onlys, forbiddens, argsWord in argsWords:
            if onlys and funcname not in onlys:
                continue
            if forbiddens and funcname in forbiddens:
                continue
            if argsWord in kargs:
                keys = list(kargs.keys())
                # take all arguments before args as args (without key)
                for k in keys:
                    if k == argsWord:
                        break
                    args.append(kargs[k])
                    kargs.pop(k)

                args += list(kargs[argsWord])
                kargs.pop(argsWord)
                break
        
        
        for onlys, forbiddens, kwargsWord in kwargsWords:
            if onlys and funcname not in onlys:
                continue
            if forbiddens and funcname in forbiddens:
                continue
            if kwargsWord in kargs:
                kwargs = kargs[kwargsWord]
                for k, v in kwargs.items():
                    kargs[k] = v
                kargs.pop(kwargsWord)
                break
        if '__class__' in kargs:
            kargs.pop('__class__')
        if not clsname and 'self' in kargs:
            kargs.pop('self')
        
        return args, kargs

    def _globaltrace(self, frame, why, arg):
        if why == 'call':
            # XXX Should do a better job of identifying methods
            this_func = (self.file_module_function_of(frame))

            if not self.isInterestingFunc(*this_func):
                return None
            
            file, module, funcname = this_func
            
            if self.from_import_module(frame):
                # ignore calls from module import
                return None
                #print('from import statement, ignored', file=self.file)
            
            if '.' in funcname:
                # is a class method
                clsname, funcname = funcname.split('.')
                # ignore __init__
                #if funcname == '__init__':
                #    return None
                funcobj = getattr(frame.f_locals['self'].__class__, funcname)
                #kargs.pop('self')
            elif funcname in frame.f_globals:
                clsname = None
                # is a global function
                funcobj = frame.f_globals[funcname]
            else:
                # otherwise, is inner function, ignored
                #print('not cls & not global', file=self.file)

                '''
                ## dump to error
                print('-' * 50, file=self.errorfile)
                print(this_func, file=self.errorfile)
                print(frame.f_locals.keys(), file=self.errorfile)
                print('not cls & not global', file=self.errorfile)
                '''

                return None

            # for test
            #print('-' * 50, file=self.file)
            #print(this_func, file=self.file)
            #print(frame.f_locals.keys(), file=self.file)
            #parent_func = self.file_module_function_of(frame.f_back)
            #print(parent_func, file = self.file)

            #print(funcobj)
            #print(frame.f_locals)
            try:
                rearrangeSuccess = False
                args, kargs = self.rearrange_args(frame, funcname, clsname)
                rearrangeSuccess = True

                # try to pickle function object and kargs
                pickleSuccess = False
                data = pickle.dumps(funcobj)
                data = pickle.dumps(args)
                data = pickle.dumps(kargs)
                pickleSuccess = True
                
                # copy args, kargs, in case funcobj change it
                args_copy = copy.deepcopy(args)
                kargs_copy = copy.deepcopy(kargs)

                # test whether can func execute successfully
                funcobj(*args_copy, **kargs_copy)

                # if can successfully run & pickle, save it
                try:
                    data = pickle.dumps((this_func, funcobj, args, kargs))
                except Exception:
                    data = None
                if data:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                        s.connect(self.socketName)
                        s.sendall(data)
                #self.funcArgs[this_func] = (funcobj, args, kargs) 

                print('-' * 50, file=self.file)
                print(this_func, file=self.file)
                print('f_locals: ', list(frame.f_locals), file=self.file)
                print('len args:', len(args), file=self.file)
                print('kargs keys:', list(kargs.keys()), file=self.file)               
                print('run normally', file=self.file)

                # if this_func fail previously
                # remove error message
                if this_func in self.errorFunc:
                    self.errorFunc.pop(this_func)

            except Exception as e:
                f = io.StringIO()
                print('-' * 50, file=f)
                print(this_func, file=f)
                print('f_locals: ', list(frame.f_locals), file=f)
                #try:
                #    print(args, file=f)
                #    print(kargs, file=f)
                #except:
                #    pass
                try:
                    print('len args:', len(args), file=f)
                    print('kargs keys:', list(kargs.keys()), file=f)          
                except:
                    pass
                
                if not rearrangeSuccess:
                    print('rearrangeError', file=f)
                elif not pickleSuccess:
                    print('pickleError', file=f)
                else:
                    print('execError', file=f)
                
                import traceback
                print(e, file=f)
                traceback.print_tb(e.__traceback__, file=f)

                self.errorFunc[this_func] = f.getvalue()
        return None

    def dumpErrs(self):
        for func, message in self.errorFunc.items():
            print(message, file=self.errorfile)

def image_in_kargs(kargs):
    for argName in kargs:
        if 'image' in argName or\
            'img' in argName or\
            'arr' in argName or\
            'mask' in argName:
            return True
    return False
class CallGraphTracer(Trace):
    def __init__(self, 
                interestingFilePrefixs = None, 
                ignoreFilePrefixs = None, 
                #reportFile=open('/tmp/res.txt', 'w'),#sys.stdout,
                #errorFile=open('/tmp/reserror.txt', 'w'),#sys.stderr
                ):
        super().__init__(ignoredirs=(sys.prefix, sys.exec_prefix))
        
        self.interestingFilePrefixs = interestingFilePrefixs
        self.ignoreFilePrefixs = ignoreFilePrefixs

        self.globaltrace = self._globaltrace
        self.localtrace = None

        self.calledG = {}
        self.allFuncs = set()
        self.imageFuncs = set()

    def isInterestingFunc(self, file, module, func):
        # ignore useless functions such as builtins
        # assume interesting and ignore do not intersect

        if (len(file) == 0 or file[0] == '<') \
            or (len(module) == 0 or module[0] == '<') \
            or (len(func) == 0 or func[0] == '<'):
            return False
        if 'tests' in file.split('/'):
            # ignore all test code
            return False
        if self.interestingFilePrefixs:
            for prefix in self.interestingFilePrefixs:
                if file.startswith(prefix):
                    return True
            return False
        if self.ignoreFilePrefixs:
            for prefix in self.ignoreFilePrefixs:
                if file.startswith(prefix):
                    return False
        return True

    def _globaltrace(self, frame, why, arg):
        if why == 'call':
            # XXX Should do a better job of identifying methods
            this_func = (self.file_module_function_of(frame))
            parent_func = self.file_module_function_of(frame.f_back)

            if self.isInterestingFunc(*this_func):
                self.allFuncs.add(this_func)
                if image_in_kargs(frame.f_locals):
                    self.imageFuncs.add(this_func)
                if self.isInterestingFunc(*parent_func):
                    if this_func not in self.calledG:
                        self.calledG[this_func] = set()
                    self.calledG[this_func].add(parent_func)
           
        return None

    def dump(self, outFile = 'calledG.pkl'):
        pickle.dump(self.calledG, open(outFile, 'wb'))

if __name__ == '__main__':
    pass