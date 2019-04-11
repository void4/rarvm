

def tc(val, bits):
    """compute the 2's complement of int value val"""
    if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value
    return val & ((2 ** bits) - 1)                         # return positive value as is

def tcr(val, bits):
    """compute the 2's complement of int value val"""
    if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value
    return val                  # return positive value as is


"""
bits = 4
for i in range(-2**bits//2, 2**bits//2):
    v = tc(i,bits)
    print(v)
    print(tcr(v,bits))
"""
