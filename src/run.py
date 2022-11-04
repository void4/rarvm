import sys
sys.dont_write_bytecode = True
from argparse import ArgumentParser

from compiler.compiler import compile
from shell import entry_point

parser = ArgumentParser(
    prog="rarVM",
    description= "resource aware, recursively sandboxable virtual machine"
)

parser.add_argument("filename", default=None)
parser.add_argument("--debug", default=False, action="store_true")
parser.add_argument("--binpath", default="bin.b")

args = parser.parse_args()

if args.filename is None:
    print("Missing <source>.et")
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

if args.binpath:#TODO: default: none?
    binary.write(args.binpath)

#entry_point(["main", path, 1000000000, 1000000000, debug])
entry_point(binary.data, 1000000000, 1000000000, args.debug, None)
