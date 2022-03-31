import sys

from core.constants import INSTR, PUSH, WMASK, WORDSIZE
from core.numeric import tc

opcodes = [instr.lower() for instr in INSTR]
#print(opcodes)

def optimize(text):
	optimized = []
	last = None
	lastpushed = None
	skip = False
	i = 0
	while i < len(text):
		line = text[i]
		skip = None
		nextline = text[i+1] if i + 1 < len(text) else None
		if line[:4] == "PUSH":
			if line == "PUSH 0" and nextline in ["ADD", "SUB"]:
				#Can only do these if there is something one the stack. Otherwise different behavior (no failure)
				skip = 2
			elif line == "PUSH 1" and nextline in ["MUL", "DIV"]:
				skip = 2
			elif line == lastpushed:
				optimized.append("DUP")
			else:
				lastpushed = line
				optimized.append(line)
		elif nextline == "NOT" and line == "NOT":
			skip = 2
		else:
			lastpushed = None
			optimized.append(line)

		if skip is None:
			i += 1
		else:
			i += skip
	return optimized

def assemble(text):
	#print("Assembling...")
	if isinstance(text, str):
		text = text.split("\n")
	text_unopt = "\n".join(text)
	#XXX Don'T HAVE TO CHANGE JUMP LABELS HERE because that happens after optimization
	text_opt = text
	for i in range(5):
		text_opt = optimize(text_opt)
	text_opt = "\n".join(text_opt)
	#print(text_opt)
	asm = translate(text_opt, False)
	#print("Optimized:", len(asm), "Unoptimized:", len(translate(text_unopt)))
	return asm

def isint(s):
	try:
		int(s)
		return True
	except ValueError:
		return False

def translate(text, debug=False):
	lines = text.split("\n")

	labels = {}
	opcounter = 0

	def intorlabel(arg):
		try:
			return int(arg)
		except:
			return arg

	lines = [{"source":line} for line in lines]
	for line in lines:
		clean = line["source"].strip().lower()
		if ";" in clean:
			clean = clean[:clean.find(";")]

		line["clean"] = clean

		opline = clean.split(" ")
		line["opline"] = opline

		if len(opline) == 1 and opline[0].endswith(":"):
			label = opline[0][:-1]
			line["name"] = label
			labels[label] = {"opc":opcounter}
			ignore = True
			line["type"] = "label"
		elif opline[0] == "pushr":
			opcounter += 1
			ignore = False
			line["type"] = "code"
		elif opline[0] in opcodes:#meh
			opcounter += 1
			ignore = False
			line["type"] = "code"
		elif isint(opline[0]):
			opcounter += 1
			ignore = False
			line["type"] = "code"
		elif opline[0]:
			raise Exception("Invalid symbol:", opline[0])
		else:
			line["type"] = "whitespace"
			ignore = True
		line["ignore"] = ignore
		line["opcount"] = opcounter

		if line["ignore"]:
			continue

		op = line["opline"][0]
		if op in ["push", "pushr"]:
			line["code"] = [PUSH, intorlabel(line["opline"][1])]
		elif isint(op):
			line["code"] = [int(op)]
		elif op in opcodes:
			line["code"] = [opcodes.index(op)]
		else:
			raise Exception("Unknown opcode %s" % line)

	# Calculate label offsets from expanded code
	offset = 0
	for line in lines:
		line["offset"] = offset
		if line["type"] == "label":
			labels[line["name"]] = offset
		elif line["type"] == "code":
			offset += len(line["code"])

	# Extend jumps with offset pushes
	for line in lines:
		if debug:
			print(line["offset"], line["opline"])
		if line["type"] == "code" and line["opline"][0] in ["jz", "jump"]:
			if len(line["opline"]) == 2 and not isinstance(line["opline"][1], int):
				#labeloffset = labels[line["opline"][1]]
				#print("Relative offset %i" % (labeloffset))
				print("Deprecated")
				exit(1)
				line["code"] = [PUSH, labeloffset] + line["code"]

	# Lastly, replace all labels with offsets

	total = []
	for line in lines:
		if line["type"] == "code":
			#print(tc(labels[exp]-line["offset"]-2, WORDSIZE))
			#line["code"] = [tc(labels[exp]-line["offset"]-2, WORDSIZE) if exp in labels else exp for exp in line["code"]]
			#line["code"] = [labels[exp] if exp in labels else exp for exp in line["code"]]
			last = line["code"][-1]
			if last in labels:
				if line["opline"][0] == "pushr":
					#print(line["offset"]+2, labels[last], last, labels[last]-line["offset"]-2)
					line["code"][0] = opcodes.index("push")
					line["code"][-1] = tc(labels[last]-line["offset"]-2, WORDSIZE)
				else:
					line["code"][-1] = labels[last]
			total += line["code"]

	if debug:
		print(labels)

	"""
	for i, line in enumerate(lines):
		if line["type"] == "code":
			print("%i\t%i\t%s\t%s" % (line["opcount"], line["offset"], " ".join(map(str, line["code"])), "\t".join(line["opline"])))
		elif line["type"] == "label":
			print("%i\t%i\t%s" % (line["opcount"], line["offset"], line["name"]))

	#print("".join(map(lambda x:hex(x)[2:].zfill(16), total)))
	print(total)
	"""
	return total

def pack(code, stack=[], map=[], memory=[]):
	#code = assemble(code)
	memory = [code] + memory
	binary = [0,0,10000000,100000000,0,len(stack),len(map),len(memory)] + stack + map + sum([[len(area)]+area for area in memory], [])
	return Binary(binary)

class Binary:
	def __init__(self, data):
		self.data = data
	def write(self, path):
		#print("Writing to %s" % path)
		with open(path, "wb") as f:
			#print("%i words." % len(self.data))
			#print(self.data)
			f.write(struct.pack(">Q", len(self.data)))
			f.write(struct.pack(">%uQ" % len(self.data), *self.data))
#bfile = open("bytecode.js", "w+")
#bfile.write("var code = "+str(code))
#bfile.close()
import struct
if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("need input file")
		exit()

	inp = sys.argv[1]

	with open(inp, "r") as f:
		text = f.read()

	binary = pack(text)

	#print(binary.data)

	if len(sys.argv) > 2:
		binary.write(sys.argv[2])
	else:
		print("No output file given")
