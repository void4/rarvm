from constants import *

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
