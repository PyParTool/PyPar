# collect function call args from example program
import os

trace_code  = '''
from pypar.utils.FuncCallTracer import FuncTracer
import sys
seaborn_dir = \'/path_to_seaborn_package\'
tracer = FuncTracer(
    errorFile=open(\'/tmp/seaborn.%d.\' + __file__.split(\'/\')[-1] + \'.txt\', \'w\'), 
    interestingFilePrefixs=[seaborn_dir])
sys.setprofile(tracer.globaltrace)

'''

dump_code = \
'''
sys.setprofile(None)
tracer.dumpErrs()
tracer.dump(\'/path_to_pkls/%d.%s.pkl\')
'''

dump_code_tab = \
'''    sys.setprofile(None)
    tracer.dumpErrs()   
    tracer.dump(\'/path_to_pkls/%d.%s.pkl\')
'''

def run_examples():
    files = []
    # path to seaborn example programs
    # for the example programs, see https://github.com/mwaskom/seaborn/tree/master/examples
    examples_dir = '/path_to_example_programs'
    for fname in os.listdir(examples_dir):
        if fname.endswith('.py'):
                fpath = examples_dir + '/' + fname
                files.append(fpath)
    print(files)
    print(len(files))

    skips = []

    for i, file in enumerate(files):
        if i in skips:
            continue
        print(i, '/', len(files), file)
        with open(file, 'r') as f:
            code = f.read(-1)
        if '__main__' in code: 
            modified = (trace_code % (i)) + code + (dump_code_tab % (i, file.split('/')[-1]))
        else:
            modified = (trace_code % (i)) + code + (dump_code % (i, file.split('/')[-1]))

        with open(file, 'w') as f:
            f.write(modified)
        
        #input()
        #os.system('python3 ' + tmpPy)
    
    from concurrent.futures import ProcessPoolExecutor
    e = ProcessPoolExecutor(max_workers=15)
    
    tasks = []
    for file in files:
        tasks.append(e.submit(os.system, 'python3 ' + file + ' >/dev/null 2>/dev/null'))

    for i, file in enumerate(files):
        print(i, '/', len(files), file)
        tasks[i].result()

if __name__ == '__main__':
    run_examples()