from time import sleep
#from copy import deepcopy

from core.numeric import tcr
from core.constants import *
from core.formats import *

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

def hasmem(state, mem):
    """Checks if state has enough mem, sets flag otherwise"""
    if mem <= state[HEAD][MEM]:
        return True
    else:
        state[HEAD][STATUS] = OOM
        return False



def run(binary, gas, mem, debug):

    blob = d(binary)

    blob[HEAD][STATUS] = NORMAL
    blob[HEAD][GAS] = gas
    blob[HEAD][MEM] = mem


    states = [blob]
    edges = [0]
    sizes = [len(binary)]
    while True:
        #XXX debug = len(states) > 1
        state = states[-1]

        jump_back = -2

        ip = -1
        instr = -1
        reqs = [0,0,0,0]

        if state[HEAD][STATUS] != NORMAL and state[HEAD][REC] == 0:
            jump_back = len(states)-2

        def jb(status=None, back=1, relative=True):
            nonlocal state, jump_back

            if relative:
                jump_back = len(states) - 1 - back
            else:
                jump_back = back

            if status is not None:
                state[HEAD][STATUS] = status

        # Check if state has enough gas
        if state[HEAD][GAS] <= 0:
            jb(OOG)
        elif state[HEAD][MEM] <= 0:
            jb(OOM)
        else:
            # Check if current instruction pointer is within code bounds
            ip = state[HEAD][IP]

            if len(state) < MEMORY + 1 or ip >= len(state[MEMORY]):
                jb(OOC)
            else:

                instr = state[MEMORY][ip]

                try:
                    reqs = REQS[instr]
                except IndexError:
                    # invalid instruction
                    jb(IIN)
                else:
                    # Check if extended instructions are within code bounds
                    if ip + reqs[0] - 1 >= len(state[MEMORY]):
                        jb(OOC)

                    # Check whether stack has sufficient items for current instruction
                    elif len(state[STACK]) < reqs[1]:
                        jb(OOS)

        if jump_back == -2:
            # Check parent chain resources recursively
            # This should really be a vector of maximum possible costs
            base_gas = 1#reqs[2]
            base_mem = 1
            for i in range(len(states)):
                layer_cost = base_gas#(sizes[i]+base_mem)*base_gas
                if layer_cost > states[i][HEAD][GAS]:
                    states[i][HEAD][STATUS] = OOG
                    jump_back = i-1
                    break

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
                    return serialized

                if i==jump_back-1:
                    break

        if debug:
            print("".join(["<-|%s¦GAS:%s¦MEM:%s|IP:%s|%s¦%s" % (STATI[states[i][HEAD][STATUS]], str(states[i][HEAD][GAS]), str(states[i][HEAD][MEM]), states[i][HEAD][IP], states[i][STACK], INSTR[states[i][MEMORY][states[i][HEAD][IP]]]) for i in range(len(states))]))
            #if len(states[0]) > MEMORY+1:
            #    print(states[0][MEMORY+1])

        if jump_back > -2:
            pass
        elif instr == RUN:
            #area = state[STACK][-3]
            #gas = state[STACK][-2]
            #mem = state[STACK][-1]
            area = state[STACK][-1]
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
                next(state, jump=0, relative=True)
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
                    next(state, top(state))
                else:
                    next(state)
            elif instr == JUMPR:
                next(state, top(state), relative=True)
            elif instr == JZR:
                if state[STACK][-2] == 0:
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
