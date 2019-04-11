#pypy2-v6.0.0-linux64/bin/pypy pypy2-v6.0.0-src/rpython/translator/goal/translate.py --opt=jit v/vm.py

try:
    from rpython.rlib.jit import JitDriver
    from rpython.rlib.jit import elidable, unroll_safe
    from rpython.rlib.jit import assert_green
    from rpython.rlib.jit import set_param
except ImportError:
    """Python compatibility."""
    class JitDriver(object):
        def __init__(self, **kw): pass
        def jit_merge_point(self, **kw): pass
        def can_enter_jit(self, **kw): pass
    def elidable(f): return f
    def dont_look_inside(f): return f
    def unroll_safe(f): return f
    def hint(v, **kw): return v
    def assert_green(x): pass
    def set_param(driver, name, value): pass

from time import sleep
from numeric import tcr
#from copy import deepcopy

BYTESIZE = 8
WORDSIZE = 8*BYTESIZE
WMAX = 2**WORDSIZE
WMASK = WMAX-1

STATUS, REC, GAS, MEM, IP = range(5)
HEAD, STACK, MAP, MEMORY = range(4)
F_STATUS, F_REC, F_GAS, F_MEM, F_IP, F_LENSTACK, F_LENMAP, F_LENMEMORY, F_STACK, F_MAP, F_MEMORY = range(11)

NORMAL, FROZEN, VOLHALT, VOLRETURN, VOLYIELD, OOG, OOC, OOS, OOM, OOB, UOC, RECURSE = range(12)
#STATI = ["NORMAL", "FROZEN", "VOLHALT", "VOLRETURN", "VOLYIELD", "OUTOFGAS", "OUTOFCODE", "OUTOFSTACK", "OUTOFMEMORY", "OUTOFBOUNDS", "UNKNOWNCODE", "RUN"]
STATI = ["NOR", "FRZ", "HLT", "RET", "YLD", "OOG", "OOC", "OOS", "OOM", "OOB", "UOC", "REC"]

HALT, RETURN, YIELD, RUN, JUMP, JUMPR, JZ, JZR, PUSH, POP, DUP, FLIP, KEYSET, KEYHAS, KEYGET, KEYDEL, STACKLEN, MEMORYLEN, AREALEN, READ, WRITE, AREA, DEAREA, ALLOC, DEALLOC, ADD, SUB, NOT, MUL, DIV, MOD, SHA256, ECVERIFY, ROT, ROT2, CMP, HEADER = range(37)

INSTR = ["HALT", "RETURN", "YIELD", "RUN", "JUMP", "JUMPR", "JZ", "JZR", "PUSH", "POP", "DUP", "FLIP", "KEYSET", "KEYHAS", "KEYGET", "KEYDEL", "STACKLEN", "MEMORYLEN", "AREALEN", "READ", "WRITE", "AREA", "DEAREA", "ALLOC", "DEALLOC", "ADD", "SUB", "NOT", "MUL", "DIV", "MOD", "SHA256", "ECVERIFY", "ROT", "ROT2", "CMP", "HEADER"]

REQS = [
    # Name, Instruction length, Required Stack Size, Stack effect, Gas cost
    [1,0,0,1],
    [1,0,0,1],
    [1,0,0,1],

    [1,1,-1,0],

    [1,1,-1,1],#jumps
    [1,1,-1,1],
    [1,2,-2,1],
    [1,2,-2,1],

    [2,0,1,2],
    [1,0,-1,2],#XXX changed stack effect

    [1,0,1,4],
    [1,2,0,4],

    [1,2,-2,10],#keys
    [1,1,0,4],
    [1,1,0,6],
    [1,1,-1,4],

    [1,0,1,2],#lens
    [1,0,1,2],
    [1,1,0,2],

    [1,2,-1,2],#r/w
    [1,3,-3,2],

    [1,0,1,10],#a/d
    [1,1,-1,10],#!use after free!
    [1,2,-2,10],#alloc/dealloc
    [1,2,-2,10],

    [1,2,-1,6],
    [1,2,-1,6],
    [1,1,0,4],
    [1,2,-1,8],
    [1,2,-1,10],
    [1,2,-1,10],

    [1,1,0,100],
    [1,1,0,100],

    [1,3,0,10],
    [1,3,0,10],

    [1,2,-1,10],

    [1,1,0,10],
]

#@elidable
def s(sharp):
    """Flattens and serializes the nested state structure"""
    flat = [] #!!! new list
    flat += sharp[HEAD]
    flat += [len(sharp[STACK])]
    flat += [len(sharp[MAP])]
    flat += [len(sharp)-MEMORY]
    flat += sharp[STACK]
    for i in range(0, len(sharp[MAP]), 2):
        k = sharp[MAP][i]
        v = sharp[MAP][i+1]
        flat += [k, v]
    for i in range(MEMORY, len(sharp)):
        flat += [len(sharp[i])]
        flat += sharp[i]
    return flat

#@elidable
def d(flat):
    """Deserializes and restores the runtime state structure from the flat version"""

    sharp = []
    sharp.append(flat[:F_LENSTACK])
    lenstack = flat[F_LENSTACK]
    lenmap = flat[F_LENMAP]
    lenmemory = flat[F_LENMEMORY]
    offset = F_LENMEMORY+1
    assert offset >= 0
    assert lenstack >= 0
    assert lenmap >= 0
    assert lenmemory >= 0
    sharp.append(flat[offset:offset+lenstack])
    offset += lenstack
    sharp.append(flat[offset:offset+lenmap])
    offset += lenmap
    #print(lenstack, lenmap, lenmemory)
    index = offset
    #print(flat, len(flat))
    for area in range(lenmemory):
        #print(index, lenmemory)
        lenarea = flat[index]
        assert index >= 0
        assert lenarea >= 0
        sharp.append(flat[index+1:index+1+lenarea])
        index = index + 1 + lenarea
    return sharp

#@unroll_safe
def next(state, jump=-1, relative=False):
    """Pops arguments. Sets the instruction pointer"""
    instr = state[MEMORY][state[HEAD][IP]]
    reqs = REQS[instr]
    if reqs[2] < 0:
        for i in range(-reqs[2]):
            state[STACK].pop(-1)
        #XXX state[HEAD][MEM] += abs(reqs[2])

    if jump == -1:
        state[HEAD][IP] += reqs[0]
    else:
        if relative:
            #print("J=", tcr(jump, WORDSIZE))
            jump = (state[HEAD][IP] + tcr(jump, WORDSIZE)) % WMAX
        #print(state[HEAD][IP], jump)

        state[HEAD][IP] = jump

# The following functions should have no or one side effect. If one, either
# 1. Set a STATE flag and return False, True otherwise
# 2. Have a side effect and be called _last_
# This is to ensure failing instructions can be continued normally

@elidable
def top(state):
    """Returns the top of the stack"""
    if len(state[STACK]) <= 0:
        return -1
    else:
        return state[STACK][-1]

def push(state, value):
    """Pushes a value onto the stack"""
    if state[HEAD][MEM] == 0:
        state[HEAD][STATUS] = OOM
        return False
    else:
        state[STACK].append(value)
        state[HEAD][MEM] -= 1#XXX
        return True

def validarea(state, area):
    """Checks if this memory area index exists"""
    if area > len(state) - MEMORY:
        state[HEAD][STATUS] = OOB
        return False
    else:
        return True

def validmemory(state, area, addr):
    """Checks if the memory address and area exist"""
    if not validarea(state, area) or addr >= len(state[MEMORY+area]):
        state[HEAD][STATUS] = OOB
        return False
    else:
        return True

@elidable
def hasmem(state, mem):
    """Checks if state has enough mem, sets flag otherwise"""
    if mem <= state[HEAD][MEM]:
        return True
    else:
        state[HEAD][STATUS] = OOM
        return False

trace = []

def run(binary, gas=100, mem=100, debug=False):

    binary[STATUS] = NORMAL
    binary[GAS] = gas
    binary[MEM] = mem

    states = [d(binary)]
    edges = [0]
    sizes = [len(binary)]
    while True:
        #XXX debug = len(states) > 1
        #TODO jitdriver.jit_merge_point(ip=states[-1][HEAD][IP], code=states[-1][CODE], state=states, edges=edges, sizes=sizes)
        state = states[-1]
        #print(state)
        #print("\n"*5)
        #print(state)
        jump_back = -2

        ip = -1
        instr = -1
        reqs = [0,0,0,0]
        #print(state[HEAD])
        if state[HEAD][STATUS] != NORMAL and state[HEAD][REC] == 0:
            jump_back = len(states)-2


        # Check if state has enough gas
        elif state[HEAD][GAS] <= 0:
            state[HEAD][STATUS] = OOG
            jump_back = len(states)-2
        elif state[HEAD][MEM] <= 0:
            state[HEAD][STATUS] = OOM
            jump_back = len(states)-2
        else:
            # Check if current instruction pointer is within code bounds
            ip = state[HEAD][IP]
            trace.append(ip)
            if len(state) < MEMORY + 1 or ip >= len(state[MEMORY]):
                state[HEAD][STATUS] = OOC
                jump_back = len(states)-2
            else:

                instr = state[MEMORY][ip]
                #if debug:
                #    print(instr)
                #    print(INSTR[instr])
                #if debug:
                    #print("STACK", state[STACK])
                    #if len(state) > MEMORY:
                    #    print("MEMORY", state[MEMORY:])
                #    print(ip, INSTR[instr])
                reqs = REQS[instr]

                # Check if extended instructions are within code bounds
                if ip + reqs[0] - 1 >= len(state[MEMORY]):
                    state[HEAD][STATUS] = OOC
                    jump_back = len(states)-2

                # Check whether stack has sufficient items for current instruction
                elif len(state[STACK]) < reqs[1]:
                    state[HEAD][STATUS] = OOS
                    jump_back = len(states)-2

        if jump_back == -2:
            # Check parent chain resources recursively
            # This should really be a vector of maximum possible costs
            base_gas = 1#reqs[2]
            base_mem = 1
            for i in range(len(states)):
                layer_cost = (sizes[i]+base_mem)*base_gas
                if layer_cost > states[i][HEAD][GAS]:
                    states[i][HEAD][STATUS] = OOG
                    jump_back = i-1
                    break

        #for st in states:
        #    print(st[HEAD])
        #if len(states)>1:
        #    print(jump_back,len(states), INSTR[instr], state[HEAD])
        if jump_back > -2:
            if debug:
                print("<<<", jump_back)
                #print(states[0][HEAD])
                pass
            serialized = None
            for i in range(len(states)-1, jump_back, -1):
                serialized = s(states[i])
                if i!=0:
                    #print(i, edges)
                    states[i-1][MEMORY+edges[len(edges)-i]] = serialized
                    states[i-1][HEAD][REC] = 0
                    states[i-1][HEAD][IP] += 0
                    states = states[:-1]
                    edges = edges[:-1]
                    sizes = sizes[:-1]
                #if i==jump_back-1:
                #    #states[i].status = OOG
                #print("First\n", i, states[0][HEAD])
                #if len(states) > 1:
                #    print(states[1][HEAD])
                if i==0:
                    #if debug:
                    #    print("STACK:",states[0][STACK])
                    #    print("MEMORY:",states[0][MEMORY])
                    return serialized

                if i==jump_back-1:
                    break

        if debug:
            print("".join(["<-|%s¦%s¦%s|%s|%s¦%s" % (STATI[states[i][HEAD][STATUS]], str(states[i][HEAD][GAS]//10**6), str(states[i][HEAD][MEM]//10**6), states[i][HEAD][IP], states[i][STACK], INSTR[states[i][MEMORY][states[i][HEAD][IP]]]) for i in range(len(states))]))
            if len(states[0]) > MEMORY+1:
                print(states[0][MEMORY+1])

        if jump_back > -2:
            pass
        elif instr == RUN:
            #area = state[STACK][-3]
            #gas = state[STACK][-2]
            #mem = state[STACK][-1]
            area = state[STACK][-1]
            #print(state[STACK])
            if validarea(state, area) and len(state[MEMORY+area]) > 4:#HEADERLEN
                child = state[MEMORY+area]
                #for mi, m in enumerate(state[MEMORY:]):
                #    print(mi, m)
                if state[HEAD][REC] == 0:
                    #XXX child[STATUS] = NORMAL
                    #child[GAS] = gas
                    #child[MEM] = mem
                    states.append(d(state[MEMORY+area]))

                    edges.append(area)
                    sizes.append(len(state[MEMORY+area]))
                    state[MEMORY+area] = None
                    state[HEAD][REC] = area + 1

                    if debug:
                        print(">>>", child[STATUS])


                # XXX do i need this?
                if state[HEAD][REC] > 0 and child[STATUS] != NORMAL:
                    #child[STATUS] = FROZEN
                    #XXX may not be required
                    state[HEAD][REC] = 0
                    next(state)
            else:
                #checkresources here?
                next(state)
        else:
                #print("\n".join(str(m) for m in states[0][MEMORY:]))
            if debug and len(states) > 1:
                print(state[STACK])
                print(state[MEMORY+1:])
                #sleep(0.1)
                #print(state[MEMORY])
            #print("".join(["%i;%i" % (states[i][0][GAS], states[i][0][MEM]) for i in range(len(states))]))
            stacklen = len(state[STACK])
            if instr == HALT:
                state[HEAD][STATUS] = VOLHALT
                next(state)
            elif instr == RETURN:
                state[HEAD][STATUS] = VOLRETURN
                state[HEAD][IP] = 0
            elif instr == YIELD:
                state[HEAD][STATUS] = VOLYIELD
                next(state)
            elif instr == JUMP:
                next(state, top(state))
            elif instr == JZ:
                if state[STACK][-2] == 0:
                    jitdriver.can_enter_jit(ip=state[HEAD][IP], code=state[MEMORY], state=states, edges=edges, sizes=sizes)
                    next(state, top(state))
                else:
                    next(state)
            elif instr == JUMPR:
                next(state, top(state), relative=True)
            elif instr == JZR:
                if state[STACK][-2] == 0:
                    jitdriver.can_enter_jit(ip=state[HEAD][IP], code=state[MEMORY], state=states, edges=edges, sizes=sizes)
                    next(state, top(state), relative=True)
                else:
                    next(state)
            elif instr == PUSH:
                state[STACK].append(state[MEMORY][ip+1])
                next(state)
            elif instr == POP:
                if len(state[STACK]) > 0:
                    state[STACK] = state[STACK][:-1]
                    state[HEAD][MEM] += 1
                    next(state)
            elif instr == DUP:
                state[STACK].append(top(state))
                next(state)
            elif instr == FLIP:
                last = state[STACK][-1]
                state[STACK][stacklen-1] = state[STACK][-2]
                state[STACK][stacklen-2] = last
                next(state)
            elif instr == KEYSET:

                if hasmem(state, 2):#or only exit if memory is actually needed?
                    kv = [state[STACK][-2], state[STACK][-1]]
                    for i in range(0, len(state[MAP]), 2):
                        if state[MAP][i] == kv[0]:
                            state[MAP][i+1] = kv[1]
                    else:
                        state[MAP] += kv
                        state[HEAD][MEM] -= 2
                    next(state)
            elif instr == KEYHAS:
                for i in range(0, len(state[MAP]), 2):
                    if state[MAP][i] == state[STACK][-1]:
                        state[STACK][-1] = 1
                else:
                    state[STACK][-1] = 0
                next(state)
            elif instr == KEYGET:
                for i in range(0, len(state[MAP]), 2):
                    if state[MAP][i] == state[STACK][-1]:
                        state[STACK][-1] = state[MAP][i+1]
                        break
                else:
                    state[STACK].pop(-1)
                    state[HEAD][MEM] += 1
                next(state)
            elif instr == KEYDEL:
                for i in range(0, len(state[MAP]), 2):
                    if state[MAP][i] == state[STACK][-1]:
                        state[MAP].pop(i)
                        state[MAP].pop(i)
                        state[HEAD][MEM] += 2
                next(state)
            elif instr == STACKLEN:
                if push(state, len(state[STACK])):
                    next(state)
            elif instr == MEMORYLEN:
                if push(state, len(state) - MEMORY):
                    next(state)
            elif instr == AREALEN:
                area = state[STACK][-1]
                if validarea(state, area):
                    state[STACK][-1] = len(state[MEMORY+area])
                    next(state)
            elif instr == READ:
                area, addr = state[STACK][stacklen-2], state[STACK][stacklen-1]
                if validmemory(state, area, addr):
                    #XXX area*AREALEN!!!!
                    state[STACK][-2] = state[MEMORY+area][addr]
                    next(state)
                else:
                    print(area, addr)
                    print("INVALIDA")

            elif instr == WRITE:
                area, addr = state[STACK][stacklen-3], state[STACK][stacklen-2]
                value = state[STACK][stacklen-1]
                if validmemory(state, area, addr):
                    state[MEMORY+area][addr] = value
                    next(state)
            elif instr == AREA:
                #sleep(1)
                # This should cost 1 mem
                if hasmem(state, 1):
                    state.append([])
                    state[HEAD][MEM] -= 1
                    next(state)
            elif instr == DEAREA:
                state[HEAD][MEM] += len(state[MEMORY+top(state)])
                state.pop(top(state))#XXX!
                next(state)
            elif instr == ALLOC:
                area, size = state[STACK][stacklen-2], state[STACK][stacklen-1]
                # Technically, -2

                #print("ALLOC", len(state), area, MEMORY)
                if len(state) > MEMORY+area:
                    if hasmem(state, size):
                        if validarea(state, area):
                            state[HEAD][MEM] -= size
                            state[MEMORY+area] += [0] * size
                            next(state)
                else:
                    #error?
                    state[HEAD][STATUS] = OOB
                    pass
            elif instr == DEALLOC:
                area, size = state[STACK][stacklen-2], state[STACK][stacklen-1]
                if validarea(state, area):
                    if len(state[MEMORY+area]) >= size:
                        state[HEAD][MEM] += size
                        stop = len(state[MEMORY+area])-size
                        if stop < 0:
                            stop = 0
                        state[MEMORY+area] = state[MEMORY+area][:stop]
                        next(state)
                    else:
                        state[HEAD][STATUS] = OOB
            elif instr == ADD:
                op1, op2 = state[STACK][stacklen-2], state[STACK][stacklen-1]
                state[STACK][stacklen-2] = (op1 + op2) % WMAX
                next(state)
            elif instr == SUB:
                op1, op2 = state[STACK][stacklen-2], state[STACK][stacklen-1]
                state[STACK][stacklen-2] = (op1 - op2) % WMAX
                next(state)
            elif instr == NOT:
                state[STACK][stacklen-1] = 1 if state[STACK][-1] == 0 else 0
                next(state)
            elif instr == MUL:
                op1, op2 = state[STACK][stacklen-2], state[STACK][stacklen-1]
                state[STACK][stacklen-2] = (op1 * op2) % WMAX
                next(state)
            elif instr == DIV:
                op1, op2 = state[STACK][stacklen-2], state[STACK][stacklen-1]
                state[STACK][stacklen-2] = op1 // op2
                next(state)
            elif instr == MOD:
                op1, op2 = state[STACK][stacklen-2], state[STACK][stacklen-1]
                state[STACK][stacklen-2] = op1 % op2
                next(state)
            elif instr == SHA256:
                #state[STACK][-1] = wrapint(state[STACK][-1], hashit)
                next(state)
            elif instr == ECVERIFY:
                #if verify(state[STACK][-1], ):
                pass
            elif instr == ROT:
                first = state[STACK][stacklen-1]
                second = state[STACK][stacklen-2]
                third = state[STACK][stacklen-3]
                state[STACK][stacklen-1] = second
                state[STACK][stacklen-2] = third
                state[STACK][stacklen-3] = first
                next(state)
            elif instr == ROT2:
                first = state[STACK][stacklen-1]
                second = state[STACK][stacklen-2]
                third = state[STACK][stacklen-3]
                state[STACK][stacklen-1] = third
                state[STACK][stacklen-2] = first
                state[STACK][stacklen-3] = second
                next(state)
            elif instr == CMP:
                first = state[STACK][stacklen-1]
                second = state[STACK][stacklen-2]
                if first < second:
                    state[STACK][stacklen-2] = 0
                else:
                    state[STACK][stacklen-2] = 1
                next(state)
            elif instr == HEADER:
                first = state[STACK][stacklen-1]
                if first < len(state[HEAD]):
                    state[STACK][stacklen-1] = state[HEAD][first]
                next(state)
            else:
                state[HEAD][STATUS] = UOC

        #if state[HEAD][GAS] % 1000000 == 0:
        #    print(state[HEAD][GAS])
        #Finalize
        memdelta = 4 - sizes[-1]
        for i in range(len(state)):
            memdelta += 1#XXX#sizes[i]#len(state[i])
        #print(memdelta)
        for i in range(len(states)):
            sizes[i] += memdelta
            states[i][HEAD][GAS] -= 1
            states[i][HEAD][MEM] -= sizes[i] * 1



import os

def b64(b):
    v = 0
    for i in range(8):
        #v |= ord(b[8-1-i])<<(i*8)
        v |= b[8-1-i]<<(i*8)

    return v

def unpack(b):
    l = b64(b)
    d = []
    offset = 8
    for i in range(l):
        v = b64(b[offset:offset+8])
        assert v >= 0
        d.append(v)
        offset += 8
    return d

import sys
import time

def entry_point(argv):
    if len(argv) < 4:
        print("<file> <gas> <mem>")
        return 1

    debug = False
    if len(argv) > 4:
        debug = bool(argv[4])
    #binary = os.open(argv[1], os.O_RDONLY, 0777)
    binary = os.open(argv[1], os.O_RDONLY)
    data = os.read(binary, 2**32)#XXX
    os.close(binary)

    gas = int(argv[2])
    mem = int(argv[3])

    flat = unpack(data)
    t = time.time()
    while True:
        ret = run(flat, gas, mem, debug=debug)
        #time.sleep(0.1)
        sharp = d(ret)
        #print(trace)
        if sharp[HEAD][STATUS] == VOLHALT:
            break
        elif sharp[HEAD][STATUS] == VOLYIELD:
            #print(len(sharp))
            sharp[HEAD][STATUS] = NORMAL
            if len(sharp)-MEMORY>0:
                #print(sharp[MEMORY:])
                if sharp[MEMORY+3][0] == 42:
                    #print(sharp[STACK][-1])
                    sys.stdout.write(chr(sharp[MEMORY+3][1]))
                    sys.stdout.flush()
                    sharp[MEMORY+3] = []
                #sharp = sharp[:-1]

            #XXX sharp[STACK] = sharp[STACK][:-2]
        else:
            print(sharp[HEAD])
            break
        flat = s(sharp)

    #print(time.time()-t)
    #print(ret)
    #print(STATI[ret[STATUS]])
    return 0

def target(*args):
    return entry_point, None

def get_location(ip, code):
    return "%s %s" % (str(ip), code)

jitdriver = JitDriver(greens=["ip", "code"],
        reds=["state", "edges", "sizes"],
        get_printable_location=get_location)


def jitpolicy(driver):
    from rpython.jit.codewriter.policy import JitPolicy
    return JitPolicy()

if __name__ == "__main__":
    entry_point(sys.argv)
