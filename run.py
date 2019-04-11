from compiler import compile
from vm import entry_point

path = "bin.b"
import sys
if len(sys.argv) < 2:
    print("Missing <source>")
    exit(1)

with open(sys.argv[1], "r") as f:
    source = f.read()

binary = compile(source)
#print(binary)

"""
LAST THING I DID
CANT JUST ALLOCATE STRINGS DYNAMICALLY AT END OF FRAME
change frame layout, put pointers at the start, dont use arealen as often

"""

binary.write(path)

if "debug" in sys.argv:
    debug = True
else:
    debug = False

#entry_point(["main", path, 1000000000, 1000000000, debug])
entry_point(["main", binary.data, 1000000000, 1000000000, debug])
