import copy
from pypar.basics.ParentExtractor import ParentExtractor
from pypar.basics.SequenceRewriter import RaySequenceRewriter, ThreadSequenceRewriter, ProcessSequenceRewriter
from pypar.basics.LoopRewriter import RayBlockedLoopRewriter, ThreadBlockedLoopRewriter, ProcessBlockedLoopRewriter
from pypar.basics.LoopRewriter import RayLoopRewriter, ThreadLoopRewriter, ProcessLoopRewriter

seqRewriters = {
    'ray': RaySequenceRewriter,
    'thread': ThreadSequenceRewriter,
    'process': ProcessSequenceRewriter
}

BLOCK_THRESHOLD = 20
LoopRewriters = {
    'ray': RayLoopRewriter,
    'thread': ThreadLoopRewriter,
    'process': ProcessLoopRewriter
}
blockedLoopRewriters = {
    'ray': RayBlockedLoopRewriter,
    'thread': ThreadBlockedLoopRewriter,
    'process': ProcessBlockedLoopRewriter
}

def rewrite(pklLst, 
    framework = 'ray' # can be 'thread', 'process', 'ray'
    ):
    if pklLst[0] == 'Seq':
        return rewriteSeq(pklLst[1], seqRewriters[framework])
    elif pklLst[0] == 'Loop':
        N_loop = pklLst[1][4]
        if N_loop > BLOCK_THRESHOLD:
            return rewriteLoop(pklLst[1], blockedLoopRewriters[framework])
        else:
            return rewriteLoop(pklLst[1], LoopRewriters[framework])

def rewriteSeq(pklLst, Rewriter):
    pklLst = copy.deepcopy(pklLst)
    funcDef, rt, sp, rwa = pklLst
    pe = ParentExtractor(funcDef)
    sr = Rewriter(
            funcDef, 
            rt, 
            sp.stDepthSet, 
            sp.endDepth, 
            sp.parallelizable, 
            rwa.Readn, 
            rwa.Writen,
    )
    return sr.parallelFuncDefs, funcDef

def rewriteLoop(pklLst, Rewriter):
    pklLst = copy.deepcopy(pklLst)
    funcDef, rt, nseq, lp, N_loop, rwa = pklLst
    pe = ParentExtractor(funcDef)
    lr = Rewriter(
        funcDef, nseq, lp.sccStmtList, rt, lp.parallelizable, rwa.Readn, rwa.Writen)
    return lr.parallelFuncDefs, funcDef