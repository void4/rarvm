# Byte size in bits
BYTESIZE = 8
# Size of a word in bits
WORDSIZE = 8*BYTESIZE
# 1 + maximum value of a word
WMAX = 2**WORDSIZE
# Maximum value of a word
WMASK = WMAX-1

# Process fields
HEAD, STACK, MAP, MEMORY = range(4)

# Header fields
STATUS, REC, GAS, MEM, IP = range(5)

# Offsets of fields in the serialized format
F_STATUS, F_REC, F_GAS, F_MEM, F_IP, F_LENSTACK, F_LENMAP, F_LENMEMORY, F_STACK, F_MAP, F_MEMORY = range(11)

NORMAL, FROZEN, VOLHALT, VOLRETURN, VOLYIELD, OOG, OOC, OOS, OOM, OOB, UOC, RECURSE, IIN = range(13)
#STATI = ["NORMAL", "FROZEN", "VOLHALT", "VOLRETURN", "VOLYIELD", "OUTOFGAS", "OUTOFCODE", "OUTOFSTACK", "OUTOFMEMORY", "OUTOFBOUNDS", "UNKNOWNCODE", "RUN"]
STATI = ["NOR", "FRZ", "HLT", "RET", "YLD", "OOG", "OOC", "OOS", "OOM", "OOB", "UOC", "REC"]

# Instruction IDs
HALT, RETURN, YIELD, RUN, JUMP, JUMPR, JZ, JZR, PUSH, POP, DUP, FLIP, KEYSET, KEYHAS, KEYGET, KEYDEL, STACKLEN, MEMORYLEN, AREALEN, READ, WRITE, AREA, DEAREA, ALLOC, DEALLOC, ADD, SUB, NOT, MUL, DIV, MOD, SHA256, ECVERIFY, ROT, ROT2, CMP, HEADER = range(37)

# Instruction names as usable in the assembler
INSTR = ["HALT", "RETURN", "YIELD", "RUN", "JUMP", "JUMPR", "JZ", "JZR", "PUSH", "POP", "DUP", "FLIP", "KEYSET", "KEYHAS", "KEYGET", "KEYDEL", "STACKLEN", "MEMORYLEN", "AREALEN", "READ", "WRITE", "AREA", "DEAREA", "ALLOC", "DEALLOC", "ADD", "SUB", "NOT", "MUL", "DIV", "MOD", "SHA256", "ECVERIFY", "ROT", "ROT2", "CMP", "HEADER"]

# Instruction properties and requirements
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
