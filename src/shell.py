import os
import sys
import time
import argparse

from core.vm import *

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


def pack(d):
    b = b""
    b += len(d).to_bytes(8, byteorder="big", signed=False)
    for i in range(len(d)):
        assert d[i] >= 0
        v = d[i].to_bytes(8, byteorder="big", signed=False)
        b += v
    return b

def entry_point(filepath, gas, mem, debug, outpath):

    if isinstance(filepath, str):
        binary = os.open(filepath, os.O_RDONLY)
        data = os.read(binary, 2**32)#XXX
        os.close(binary)
        flat = unpack(data)
    else:
        flat = filepath

    gas = int(gas)
    mem = int(mem)

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

    if outpath is not None:# and sharp[HEAD][STATUS] != VOLHALT:
        data = pack(ret)
        binary = os.open(outpath, os.O_WRONLY | os.O_CREAT)
        os.write(binary, data)
        os.close(binary)
    #print(time.time()-t)
    #print(ret)
    #print(STATI[ret[STATUS]])
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser("rarVM", description="Executes a rarVM binary")
    parser.add_argument("filename", type=str)
    parser.add_argument("--gas", type=int, default=1000000)
    parser.add_argument("--mem", type=int, default=1000000)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--out", type=str, default=None)
    #TODO only write --out on OOG, OOM etc!
    args = parser.parse_args()
    #print(args)
    entry_point(args.filename, args.gas, args.mem, args.debug, args.out)
