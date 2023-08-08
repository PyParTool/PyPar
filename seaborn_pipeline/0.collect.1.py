# collect function call args from pytest scripts
import os
from pytest import console_main
from pypar.utils.FuncCallTracer import FuncTracer

def handle_mod(cur_dir):
    # path to your seaborn package
    seaborn_dir = '~/.local/lib/python3.8/site-packages/seaborn'
    os.chdir(seaborn_dir)
    #console_main()
    tracer = FuncTracer(
            interestingFilePrefixs=[seaborn_dir], 
            reportFile=open('/tmp/seaborn.res.txt', 'w'),
            errorFile=open('/tmp/seaborn.error.txt', 'w'))
    code = 'console_main()'
    tracer.runctx(code, globals=globals(), locals=locals())
    tracer.dump(outFile=cur_dir + '/0.funcArgs.pkl')
    tracer.dumpErrs()
    
if __name__ == '__main__':
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    handle_mod(cur_dir)
    