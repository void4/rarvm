from parser import compile
from vm import entry_point

path = "bin.b"
import sys
if len(sys.argv) < 2:
    print("Missing <source>")
    exit(1)

with open(sys.argv[1], "r") as f:
    source = f.read()

binary = compile(source)
print(binary)

binary.write(path)

if "debug" in sys.argv:
    debug = True
else:
    debug = False

entry_point(["main", path, 1000000000, 1000000000, debug])
