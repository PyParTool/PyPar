import astunparse
import os
import ast
import inspect

def slurp(f):
    with open(f, 'r') as f: return f.read()

def getstr(stmt):
    if isinstance(stmt, str):
        return stmt
    else:
        return astunparse.unparse(stmt).strip()

class RuntimeCalculator:
    # calculate the run time of target program
    def __init__(self, filepath):
        f = open(filepath, 'r')
        dirPath = '/'.join(filepath.split('/')[:-1])
        code = f.read(-1)
        codeLines = code.split('\n')
        idxStart = -1
        for i, line in enumerate(codeLines):
            nline = line.strip().split(' ')
            if (len(nline) >= 4
                and ((nline[0] == 'if' 
                    and nline[1] == '__name__'
                    and nline[2] == '==')
                    or
                    (nline[0] == 'if' 
                    and nline[1] == '(__name__'
                    and nline[2] == '=='))
                ):
                idxStart = i
                break
        
        assert(idxStart != -1)

        codeLines = codeLines[:idxStart] +\
                ['import time', 'startTime = time.time()'] +\
                codeLines[idxStart:] +\
                ['print(time.time()-startTime, file=open(\'time.txt\', \'w\'))']
        ncode = '\n'.join(codeLines)
        
        testCodePath = dirPath + '/testCode.py'
        testTimePath = dirPath + '/time.txt'
        os.system('rm ' + testCodePath + ' 2>/dev/null')
        os.system('rm ' + testTimePath + ' 2>/dev/null')
        with open(testCodePath, 'w') as ftst:
            ftst.write(ncode)
        
        os.system('cd ' + dirPath + ';' + 'timeout 60 python3 testCode.py' + ' 2>/dev/null >/dev/null')
        
        if os.path.exists(testTimePath):
            with open(testTimePath) as timeF:
                rtime = timeF.read(-1).strip()
            self.runtime = float(rtime)
        else:
            self.runtime = None

        os.system('rm ' + testCodePath + ' 2>/dev/null')

def getAST(f):
    # input: function object
    # output: its AST
    src = inspect.getsource(f)
    lines = src.split('\n')
    if lines[0][:4] == ' ' * 4:
        for i, line in enumerate(lines):
            if len(line) >= 4 and line[:4] == ' ' * 4:
                lines[i] = line[4:]
    src = '\n'.join(lines)
    return ast.parse(src).body[0]