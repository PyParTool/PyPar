# input: pickle files in ./pkls , 0.funcArgs.pkl
# this program merges these pkl files into one
# output: 1.funcArgs.pkl

if __name__ == '__main__':
    import pickle
    import os
    #from stats import fileDct
    import importlib
    import sys
    #from assist import *
    funcArgs = {}

    orig_stdout = sys.stdout 
    orig_stderr = sys.stderr
    sys.stdout = open('/dev/null', 'w')
    sys.stderr = open('/dev/null', 'w')
    for file in os.listdir('./pkls'):
        if file.endswith('.pkl'):
            print('process', file, file=orig_stdout)
            #input()
            try:
                idx = int(file.split('/')[-1].split('.')[0])
                nfuncArgs = pickle.load(open('./pkls/' + file, 'rb'))
                for this_func, (funcobj, args, kargs) in nfuncArgs.items():
                    if this_func not in funcArgs:
                        #print(this_func, file=orig_stdout)
                        funcArgs[this_func] = (funcobj, args, kargs) 
                print(len(nfuncArgs), file=orig_stdout)
            except Exception as e:
                #print(targetFile, file = orig_stdout)
                print(file, file = orig_stdout)
                print(e, file = orig_stdout)
                input()
    try:
        nfuncArgs = pickle.load(open('0.funcArgs.pkl', 'rb'))
        for this_func, (funcobj, args, kargs) in nfuncArgs.items():
            if this_func not in funcArgs:
                funcArgs[this_func] = (funcobj, args, kargs) 
        print(len(nfuncArgs), file=orig_stdout)
    except Exception as e:
        print('orig', file = orig_stdout)
        print(e, file = orig_stdout)
        input()

    sys.stdout = orig_stdout
    sys.stderr = orig_stderr

    
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["NUM_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    nfuncArgs = {}

    exe = False
    Last = False
    for this_func, (funcobj, args, kargs)in funcArgs.items():
        print(this_func)
        if this_func[2] == 'Birch.fit':
            Last = True
        try:
            #if 'fit' in this_func[2]:
            print(this_func)
            if exe:
                funcobj(*args, **kargs)
            if Last:
                exe = True
            pickle.dumps((funcobj, args, kargs))
            nfuncArgs[this_func] = (funcobj, args, kargs)
        except Exception as e:
            print(e)
            input()
            
    print(len(nfuncArgs))
    

    pickle.dump(nfuncArgs, open('1.funcArgs.pkl', 'wb'))