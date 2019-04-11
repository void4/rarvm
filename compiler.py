from lark import Lark, Tree, Transformer
from lark.tree import Visitor
from lark.lexer import Token

from assembler import pack, assemble
from asmutils import asm

from utils import L, kahn, stringToWords, nametoint

import os

grammar = r"""
NAME: /\*?[a-zA-Z_]\w*/
COMMENT: /#[^\n]*/
_NEWLINE: ( /\r?\n[\t ]*/ | COMMENT)+

_DEDENT: "<DEDENT>"
_INDENT: "<INDENT>"

%import common.ESCAPED_STRING
string: ESCAPED_STRING

number: DEC_NUMBER
DEC_NUMBER: /0|[1-9]\d*/i

%ignore /[\t \f]+/  // Whitespace

start: (_NEWLINE | typedef | funcdef | importdef)*



tnpair: NAME NAME
funcdef: "def" funname "(" [funparams] ")" ["->" "(" [funrets] ")"] ":" funcbody
funcbody: suite
funparams: tnpair ("," tnpair)*
funrets: NAME ("," NAME)*

importdef: "import" NAME _NEWLINE

typedef: "typ" NAME "{" funparams "}" _NEWLINE

?stmt: (simple_stmt | compound_stmt)
suite: _NEWLINE _INDENT _NEWLINE? stmt+ _DEDENT _NEWLINE?

compound_stmt: (if_stmt | while_stmt)
if_stmt: "if" test ":" suite ["else" ":" suite]
while_stmt: "while" [test] ":" suite


?test: or_test
?or_test: and_test ("or" and_test)*
?and_test: not_test ("and" not_test)*
?not_test: "not" not_test -> not
| comparison
?comparison: expr _comp_op expr
!_comp_op: "==" | "!=" | "<" | "<=" | ">" | ">="

simple_stmt: (assign | run | doreturn | doyield | write_stmt | area_stmt | alloc_stmt | dealloc_stmt | funcall) _NEWLINE

write_stmt: "$write" "(" expr "," expr ["," expr] ")"
assign: NAME "=" expr
run: "$run" "(" expr ")"
doreturn: "return" expr
doyield: "yield" //expr
area_stmt: "$area"
alloc_stmt: "$alloc" "(" expr ["," expr] ")"
dealloc_stmt: "$dealloc" "(" expr ["," expr] ")"

?expr: arith_expr
?arith_expr: term (_add_op term)*
?term: factor (_mul_op factor)*
?factor: _factor_op factor | molecule
?molecule: read | funcall | atom | arealen_expr | memorylen_expr | keyget_expr | funcname_expr |  molecule "[" [expr] "]" -> getitem

read: "$read" "(" expr ["," expr] ")"

?atom: "[" listmaker "]" | tuple | attr | NAME | number | string
listmaker: test ("," test)* [","]

arealen_expr: "$arealen" "(" expr ")"
memorylen_expr: "$memorylen"
keyget_expr: "$keyget" "(" expr ")"
funcname_expr: "$funcname" "(" NAME ")"

!_factor_op: "+"|"-"|"~"
!_add_op: "+"|"-"
!_mul_op: "*"|"/"|"%"

funcall: funname "(" [funargs] ")"
funname: NAME
funargs: expr ("," expr)*
tuple: [NAME] "{" [expr ("," expr)*] "}"
attr: NAME "." NAME
"""

DEBUG = False

l = Lark(grammar, debug=True)

def indent(line):
    return (len(line) - len(line.lstrip(' '))) // 4

def prep(code):
    code = code.split('\n')
    code.append('\n')
    current = 0
    lines = ''
    for line in code:
        ind = indent(line)
        if ind > current:
            prefix = '<INDENT>' * (ind - current)
        else:
            if ind < current:
                prefix = '<DEDENT>' * (current - ind)
            else:
                prefix = ''
        current = ind
        lines += prefix + line.lstrip() + '\n'

    # Remove indent-dedent pairs
    for i in range(5):
        lines = lines.replace("<DEDENT>\n\n<INDENT>", "").replace("<DEDENT>\n<INDENT>", "").replace("<DEDENT><INDENT>", "")

    return lines



def getChildByName(node, name):
    for child in node.children:
        if child._pretty_label() == name:
            return child

class Generator:

    def __init__(self):
        self.counter = 0

    def next(self):
        self.counter += 1
        return self.counter

    def label(self):
        return 'label:%i' % self.next()

    def name(self):
        return 'name:%i' % self.next()

MEM_CODE = 0
MEM_STACK = 1
MEM_HEAP = 2
MEM_IO = 3

def compile_function(abort, warn, generator, types, funcs, funcname):
    if DEBUG:
        print("Compiling function %s" % funcname)
    func = funcs[funcname]
    tree = func["body"]
    intypes = {name: typ for typ, name in func["in"]}
    var = {}

    def hasType(name):
        if name in var or name in intypes:
            return True
        else:
            return False

    def isint(s):
        try:
            int(s)
            return True
        except:
            return False

    def getTypeSignature(expr):
        if DEBUG:
            print(expr)
        if isinstance(expr, Token):
            #print(expr.type, expr.type == "DEC_NUMBER")
            if expr.type == "DEC_NUMBER":
                return "u"

            expr = expr.value

        if isinstance(expr, str):
            if isint(expr):
                return "u"

            name = expr
            if name in var:
                return var[name]["type"]
            elif name in intypes:
                return intypes[name]
            else:
                abort("Unknown variable %s" % name)
        elif isinstance(expr, Tree):
            #print(expr)
            try:
                expr.type
            except AttributeError:
                print("attrerr:", expr)
            return expr.type
        elif isinstance(expr, L):
            if isinstance(expr.type, str):
                return expr.type
            elif isinstance(expr.type, list):
                if len(expr.type) == 1:
                    return expr.type[0]
                return expr.type
            else:
                #return list(expr.type)[0]
                raise Exception("huh?")
        else:
            print("expr:",expr)
            abort("Unknown expression type")

    def pushVar(name):
        typ = types[getTypeSignature(name)]

    def codeOrAbort(expr):
        if isinstance(expr, Tree) or isinstance(expr, L):
            try:
                return expr.code
            except Exception as e:
                print(e, expr)
        else:
            print("expr:",expr)
            abort("Unknown addr push")

    def pushExpr(expr):
        if isinstance(expr, Token):
            expr = expr.value

        if isinstance(expr, str):

            if isint(expr):
                return ["PUSH %i" % int(expr)]

            code = []

            typ = types[getTypeSignature(expr)]

            for index in range(typ["len"]):
                code += getAbsoluteOffset(expr, index)
                code += ["READ"]
            return code
        else:
            return codeOrAbort(expr)

    def readAddr(expr, offset=None):
        code = pushAddr(expr, offset=offset)
        code += ["READ"]
        return code

    def flatten(l):
        return sum(l,[])

    def getSubtype(name, key):
        for subtype in types[name]["def"]:
            if subtype["name"] == key:
                return subtype

    def varLen():
        return sum(types[var[v]["type"]]["len"] for v in var)

    def typLen(typelist):
        return sum(types[typ]["len"] for typ in typelist)

    def inTypLen(typenamelist):
        return sum(types[typ[0]]["len"] for typ in typenamelist)

    arglen = inTypLen(func["in"])
    retlen = typLen(func["out"])

    if DEBUG:
        print(func["in"], arglen)
        print(func["out"], retlen)

    # Get offset relative to stack frame
    def getRelativeOffset(name):
        offset = 0
        #retlen
        for v in var:
            if v == name:
                return offset
            offset += types[var[v]["type"]]["len"]

        offset = -arglen
        for i in func["in"]:
            if i[1] == name:
                return offset
            offset += types[i[0]]["len"]
        raise Exception("%s not found" % name)

    def add(i):
        if i < 0:
            return ["PUSH %i" % -i, "SUB"]
        elif i > 0:
            return ["PUSH %i" % i, "ADD"]
        else:
            return []

    def read(offset, page=0):
        return push(offset, page) + ["READ"]

    # Get absolute offset in page
    def getAbsoluteOffset(name, index=None):
        offset = getRelativeOffset(name)
        code = ["PUSH %i" % MEM_STACK, "PUSH %i" % MEM_STACK, "PUSH 0", "READ"]
        code += add(offset)
        if index is not None:
            code += add(index)
        return code

    def listOrFirstElement(l):
        if isinstance(l, list) and len(l) == 1:
            return l[0]
        return l

    # Returns true if t1 != t2
    def compareTypes(t1, t2):
        return listOrFirstElement(t1) != listOrFirstElement(t2)

    def ensurePrimitive(op, n1, n2):
        leftType = getTypeSignature(n1)
        rightType = getTypeSignature(n2)
        if leftType != "u" or rightType != "u":
            abort("Can only %s variables of type 'u', got %s and %s" % (op, leftType, rightType), node[0])
        if leftType != rightType:
            abort("Cannot %s two different types" % op, node[0])
        return leftType, rightType

    # Default function cleanup, after return values have been pushed to the stack
    def coda():

        code = []

        # Write return values from stack to memory
        #for i in range(retlen):
        #    # Current stack frame
        #    code += asm("write(%i, add(read(%i,0),%i), rot2)" % (MEM_STACK, MEM_STACK, i))

        # Push old return address to stack
        code += asm("read(%i,sub(arealen(%i),1))" % (MEM_STACK, MEM_STACK))

        # Push old stack frame address to stack
        code += asm("read(%i,sub(arealen(%i),2))" % (MEM_STACK, MEM_STACK))

        # Truncate area to current stack frame address
        code += asm("dealloc(%i, sub(arealen(%i), read(%i,0)))" % (MEM_STACK, MEM_STACK, MEM_STACK))#sub , retlen

        # Set old stack frame address again
        code += asm("write(%i,0,rot2)" % (MEM_STACK))

        if funcname == "main":
            #code += asm("pop")
            #code += asm("dearea(0)")
            code += ["HALT"]
        else:
            # Jump to return address
            code += ["JUMP"]

        return code

    # Puts default return values on stack + coda
    def ecoda():
        code = []
        for i in range(retlen):
            code += asm("push(0)")
        code += coda()
        return code

    """
    MEM_STACK layout
    0:0 - current stack frame address

    expect: arg* |
    create: arg* | ret* static* last_stack return_addr
    destroy: arg* ret*
    """

    # Generate code here?
    class TypeAnnotator(Transformer):
        def funcbody(self, node):
            node = L(node)
            node.code = []
            # Allocate stack frame
            #print("RET", func["out"])

            # Calculate stack frame size # + return address + stack frame
            framesize = varLen() + 2#XXX retlen +

            # Allocate stack frame
            node.code += asm("alloc(%i,%i)" % (MEM_STACK, framesize))

            # Write current stack frame address to second last item of stack frame
            node.code += asm("write(%i,sub(arealen(%i),2),read(%i,0))" % (MEM_STACK, MEM_STACK, MEM_STACK))

            # Write return address from stack to end of stack frame
            node.code += asm("write(%i,sub(arealen(%i),1),rot2)" % (MEM_STACK, MEM_STACK))

            # Write stack frame address to 0:0
            node.code += asm("write(%i,0,sub(arealen(%i), %i))" % (MEM_STACK, MEM_STACK, framesize))

            # Put last index of area on stack
            #node.code += ["PUSH 0"]
            #node.code += ["PUSH 0", "arealen", "PUSH 1", "SUB"]
            # Save return address in frame
            #node.code += ["ROT2", "WRITE"]
            if DEBUG:
                print(funcname, node[0])

            node.code += node[0].code
            node.code += ecoda()

            code = "\n".join(node.code)

            #XXX check for jump at end of function!
            return code

        def suite(self, node):
            node = L(node)
            node.code = []
            for child in node:
                if DEBUG:
                    print(child)
                node.code += pushExpr(child)
            return node

        def doreturn(self, node):
            node = L(node)
            node.code = []
            retType = getTypeSignature(node[0])
            if compareTypes(retType, func["out"]):
                abort("Return type doesn't match function signature\nExpected %s, got %s" % (func["out"], retType))
            node.type = retType
            node.code += pushExpr(node[0])

            node.code += coda()

            return node

        def doyield(self,node):
            node = L(node)
            node.code = []
            #node.code += pushExpr(node[0])
            node.code += ["YIELD"]
            return node

        def area_stmt(self, node):
            node = L(node)
            node.code = ["AREA"]
            return node

        """
        Frame structure
                      fp here
        lastframe|args|local vars|location of last frame|return addr|

        """
        def funcall(self, node):
            if DEBUG:
                print("()", node)
            node = L(node)
            otherfuncname = node[0].children[0].value
            otherfunc = funcs[otherfuncname]
            node.type = otherfunc["out"]
            node.code = []
            # CANNOT CHANGE STACK FRAME BOUNDARY; THEN pushExpr, because they depend on unmodified AREALEN!
            # Allocate parameter space

            if len(node) > 1:
                intypes = otherfunc["in"]
                for i, param in enumerate(node[1].children):
                    paramsig = getTypeSignature(param)
                    if compareTypes(intypes[i][0], paramsig):
                        abort("Wrong types on function call, expected %s, got %s" % (intypes[i], paramsig))

                    node.code += pushExpr(param)

                node.code += asm("alloc(%i,%i)" % (MEM_STACK, inTypLen(otherfunc["in"])))
                for i, param in enumerate(node[1].children[::-1]):
                    paramsig = getTypeSignature(param)
                    for index in range(types[paramsig]["len"]):
                        # Write args to end of current stack frame
                        node.code += asm("push(%i,sub(arealen(%i),%i))" % (MEM_STACK, MEM_STACK, index+i+1))
                        node.code += ["ROT2"]
                        node.code += ["WRITE"]

            # Push return address
            # TODO do this dynamically with IP
            # XXX this doesn't work anymore anyway

            #label = generator.label()
            #node.code += ["PUSH %s" % label]
            node.code += ["PUSH 4", "HEADER"]
            node.code += ["PUSH 8", "ADD"]
            #XXX must add a few for this to work
            # XXX PUSH FUNC___!"§"otherfuncname (collisions)
            #node.code += ["PUSH %s" % otherfuncname, "JUMP"]
            node.code += asm("keyget(%i)" % nametoint(otherfuncname))
            node.code += ["JUMP"]
            #node.code += [label+":"]
            # TODO now handle returned values!
            # Deallocate return values
            #XXX node.code += asm("dealloc(%i,%i)" % (MEM_STACK, typLen(otherfunc["out"])))
            # Deallocate parameters
            node.code += asm("dealloc(%i,%i)" % (MEM_STACK, inTypLen(otherfunc["in"])))
            return node

        # TODO implement elif
        def if_stmt(self, node):
            node = L(node)
            node.code = []
            node.code += pushExpr(node[0])
            end_label = generator.label()
            if len(node) == 3:
                else_label = generator.label()
                node.code += ['PUSHR %s' % else_label]
            else:
                node.code += ['PUSHR %s' % end_label]
            node.code += ['JZR']
            node.code += node[1].code
            if len(node) == 3:
                node.code += ['PUSHR %s' % end_label]
                node.code += ['JUMPR']
                node.code += [else_label + ':']
                node += node[2].code
            node.code += [end_label + ':']
            return node

        def while_stmt(self, node):
            node = L(node)
            start_label = generator.label()
            end_label = generator.label()
            node.code = [start_label + ':']
            if len(node) == 2:
                node.code += pushExpr(node[0])
                node.code += ['PUSHR %s' % end_label]
                node.code += ['JZR']
                node.code += node[1].code
            else:
                node.code += node[0].code
            node.code += ['PUSHR %s' % start_label]
            node.code += ['JUMPR']
            node.code += [end_label + ':']
            return node

        def getitem(self, node):
            node = L(node)
            leftType = getTypeSignature(node[0])
            rightType = getTypeSignature(node[1])
            if not leftType.startswith("*"):
                abort("Cannot index into non-pointer type %s of '%s'" % (leftType, node[0]), node)
            if rightType != "u":
                abort("Cannot index into pointer using non-u type %s of %s" % (rightType, node[1]), node)

            if DEBUG:
                print("[]", leftType, rightType)
            node.code = []
            node.code += ["PUSH 0"] + pushExpr(node[0]) + pushExpr(node[1]) + ["ADD", "READ"]
            node.type = leftType[1:]
            return node

        def read(self, node):
            node = L(node)
            node.code = []
            leftType = getTypeSignature(node[0])

            if leftType != "u":
                abort("Cannot use non 'u' %s as index" % leftType, node[0])

            if len(node) == 1:
                node.code += ["PUSH 0"]
                node.code += pushExpr(node[0])
            else:
                rightType = getTypeSignature(node[1])
                if rightType != "u":
                    abort("Cannot use non 'u' %s as index" % rightType, node[1])
                node.code += pushExpr(node[0])
                node.code += pushExpr(node[1])
            node.code += ["READ"]
            node.type = "u"
            return node

        def write_stmt(self, node):
            node = L(node)
            node.code = []
            leftType = getTypeSignature(node[0])

            if leftType != "u":
                abort("Cannot use non 'u' %s as index" % leftType, node[0])

            if len(node) == 2:
                abort("disabled write", node)
                node.code += ["PUSH 0"]
                node.code += pushExpr(node[0])
            else:
                middleType = getTypeSignature(node[1])
                if middleType != "u":
                    abort("Cannot use non 'u' %s as index" % middleType, node[1])
                node.code += pushExpr(node[0])
                node.code += pushExpr(node[1])
            node.code += pushExpr(node[-1])
            node.code += ["WRITE"]
            return node

        def alloc_stmt(self, node):
            node = L(node)
            node.code = []
            leftType = getTypeSignature(node[0])

            if leftType != "u":
                abort("Cannot use non 'u' %s as index to alloc" % leftType, node[0])

            if len(node) == 1:
                node.code += ["PUSH 0"]
                node.code += pushExpr(node[0])
            else:
                rightType = getTypeSignature(node[1])
                if rightType != "u":
                    abort("Cannot use non 'u' %s as size to alloc" % rightType, node[1])
                node.code += pushExpr(node[0])
                node.code += pushExpr(node[1])
            node.code += ["ALLOC"]
            return node

        def dealloc_stmt(self, node):
            node = L(node)
            node.code = []
            leftType = getTypeSignature(node[0])

            if leftType != "u":
                abort("Cannot use non 'u' %s as index to dealloc" % leftType, node[0])

            if len(node) == 1:
                node.code += ["PUSH 0"]
                node.code += pushExpr(node[0])
            else:
                rightType = getTypeSignature(node[1])
                if rightType != "u":
                    abort("Cannot use non 'u' %s as size to dealloc" % rightType, node[1])
                node.code += pushExpr(node[0])
                node.code += pushExpr(node[1])
            node.code += ["DEALLOC"]
            return node

        def arealen_expr(self, node):
            node = L(node)
            node.type ="u"
            leftType = getTypeSignature(node[0])
            if leftType != "u":
                abort("Cannot use non 'u' %s as index to arealen" % leftType, node[0])
            node.code = pushExpr(node[0])
            node.code += ["AREALEN"]
            return node

        def keyget_expr(self, node):
            node = L(node)
            node.type = "u"
            leftType = getTypeSignature(node[0])
            if leftType != "u":
                abort("Cannot use non 'u' %s as index to keyget" % leftType, node[0])
            node.code = pushExpr(node[0])
            node.code += ["KEYGET"]
            return node

        def memorylen_expr(self, node):
            node = L(node)
            node.type = "u"
            node.code = ["MEMORYLEN"]
            return node

        def funcname_expr(self, node):
            node = L(node)
            node.type = "u"
            node.code = ["PUSH %i" % nametoint(node[0].value)]
            return node

        def comparison(self, node):
            node = L(node)
            if DEBUG:
                print("cmp", node)
            leftType, rightType = ensurePrimitive("cmp", node[0], node[2])
            node.code = []

            cmp = node[1].value

            if cmp in ["!=", "=="]:
                node.code += pushExpr(node[0])
                node.code += pushExpr(node[2])
                node.code += ["SUB"]
                if cmp == "==":
                    node.code += ["NOT"]
            elif cmp == "<":
                node.code += pushExpr(node[0])
                node.code += pushExpr(node[2])
                node.code += ["CMP"]
                node.code += ["NOT"]
            elif cmp == ">=":
                node.code += pushExpr(node[2])
                node.code += pushExpr(node[0])
                node.code += ["CMP"]
            elif cmp == ">":
                node.code += pushExpr(node[0])
                node.code += pushExpr(node[2])
                node.code += ["CMP"]
                node.code += ["NOT"]
            elif cmp == "<=":
                node.code += pushExpr(node[2])
                node.code += pushExpr(node[0])
                node.code += ["CMP"]
            else:
                abort("Unknown comparison operator %s" % node[1].value, node[1])
            #print("COMPARISON", cmp, node.code)
            node.type = "u"
            return node

        def compound_stmt(self, node):
            node = L(node)
            node.code = pushExpr(node[0])
            return node

        def simple_stmt(self, node):
            node = L(node)
            node.code = pushExpr(node[0])
            return node

        def arith_expr(self, node):
            node = L(node)
            node.type = getTypeSignature(node[0])
            node.code = pushExpr(node[0])
            return node

        def assign(self, node):
            if DEBUG:
                print("=", node)
            rightType = getTypeSignature(node[1])
            if DEBUG:
                print("=", rightType)

            if hasType(node[0].value):
                leftType = getTypeSignature(node[0].value)
                if compareTypes(leftType, rightType):
                    abort("Assignment type mismatch %s = %s" % (leftType, rightType), node)
            else:
                #print("New var", node[0].value)
                if isinstance(rightType, list) and len(rightType) > 1:
                    raise NotImplemented("nope")
                elif len(rightType) == 0:
                    abort("Cannot assign from () to something", node[0])

                var[node[0].value] = {"type":rightType}
                #node.code += [["_RESERVE", node[0].value]]
            #print(types,var[node[0].value])

            node = L(node)
            node.code = []
            """
            node.code += getAbsoluteOffset(node[0].value)
            node.code += getAbsoluteOffset(node[1].value)
            node.code += rightType["len"]
            node.code += "MEMCOPY"
            """
            node.code += pushExpr(node[1])
            for index in range(types[rightType]["len"]-1, -1, -1):
                # composite assignment somewhere else!
                node.code += getAbsoluteOffset(node[0].value, index)
                node.code += ["ROT2"]
                node.code += ["WRITE"]

            return node

        def number(self, node):
            node = L(node)
            node.type = "u"
            #TODO make sure u is in range
            node.code = ["PUSH %s" % node[0].value]
            return node

        def listmaker(self, node):
            node = L(node)
            node.type = ["u"] * len(node)
            return node

        def run(self, node):
            node = L(node)
            #node.code = asm("push(99999999999,99999999999)")
            node.code = pushExpr(node[0])
            node.code += ["RUN"]
            return node

        def attr(self, node):
            if not hasType(node[0].value):
                abort("Name %s has no type" % node[0].value, node[0])
            typ = getTypeSignature(node[0])#XXX
            if not typ in types:
                abort("%s's type is not a struct" % node[0].value, node[0])
            subtype = getSubtype(typ, node[1].value)
            if subtype is None:
                abort("%s.'%s' is not a valid attribute" % (node[0].value, node[1].value), node[1])
            node = L(node)
            node.code = []
            for index in range(subtype["len"]):
                node.code += getAbsoluteOffset(node[0].value, subtype["offset"]+index)
            node.code += ["READ"]
            node.type = subtype["type"]
            return node

        def tuple(self, node):
            node = L(node)
            node.code = []
            if DEBUG:
                print("TUPLE", node, node.code)
            if isinstance(node, list):
                data = node
                tup = list(getTypeSignature(n) for n in data)
                node.type = tup#flatten(tup)
            else:
                data = node[1]
                tup = list(getTypeSignature(n) for n in data)
                #TODO compare name with actual type
                nametyp = types[node[0].value]
                if nametyp != tup:
                    abort("Invalid type arguments: %s %s" % (nametyp, tup), node[0])
                node.type = nametyp

            for n in data:
                node.code += pushExpr(n)

            return node

        def term(self, node):
            node = L(node)
            node.code = pushExpr(node[0])
            for i in range((len(node) - 1) // 2):
                nextop = node[1 + i * 2 + 1]
                leftType, rightType = ensurePrimitive(node[1].value, node[0], nextop)
                node.code += pushExpr(nextop)
                node.code += ['%s' % {'*':'MUL',  '/':'DIV',  '%':'MOD'}[node[1 + i * 2].value]]

            node.type = leftType
            return node

        def arith_expr(self, node):
            node = L(node)
            node.code = pushExpr(node[0])
            for i in range((len(node) - 1) // 2):
                nextop = node[1 + i * 2 + 1]
                leftType, rightType = ensurePrimitive(node[1].value, node[0], nextop)
                node.code += pushExpr(nextop)
                node.code += ['%s' % {'+':'ADD',  '-':'SUB',  '~':'NOT'}[node[1 + i * 2].value]]

            node.type = leftType
            return node

        def expr(self, node):
            node = L(node)
            node.code = []
            node.type = getTypeSignature(node[0])
            node.code = pushExpr(node[0])
            return node

        def string(self, node):
            # TODO allocate on heap
            node = L(node)
            node.type = "vector"
            arr = node[0].value[1:-1]
            new = stringToWords(arr)
            if DEBUG:
                print("String", new)
            node.code = []
            node.code += asm("alloc(%i,%i)" % (MEM_HEAP, len(new)))
            for i, c in enumerate(new):
                node.code += asm("write(%i,sub(arealen(%i),%i),%i)" % (MEM_HEAP, MEM_HEAP, len(new)-i, c))

            node.code += asm("push(sub(arealen(%i),%i),%i)" % (MEM_HEAP, len(new), len(new)))
            return node
    # todo add casting

    annotator = TypeAnnotator()
    if DEBUG:
        print(tree)
    tree = annotator.transform(tree)

    return tree

def compile(text, path=None):



    def errortext(error, msg, node=None):
        out = error + ":\n"
        if node is not None:
            try:
                out += "Line %i: " % node.line + "\n"
                out += clean.split("\n")[node.line-1] + "\n"
                out += " "*node.column+"^\n"
            except AttributeError as e:
                print("AttributeError", e)
        out += msg
        return out

    def warn(msg, node=None):
        print(errortext("Warning",msg, node))

    def abort(msg, node=None):
        raise Exception(errortext("Error",msg, node))

    def pairs(tree):
        return [[n.children[0].value,n.children[1].value] for n in tree.children]

    class TypeGetter(Visitor):
        def start(self, node):
            #print(node)
            if DEBUG:
                print("Collected type definitions and function signatures.")

        def importdef(self, node):
            imports[node.children[0].value] = {}

        def typedef(self, node):
            node = node.children
            types[node[0].value] = pairs(node[1])

        def funcdef(self, node):
            indef = getChildByName(node, "funparams")
            if indef is None:
                indef = []
            else:
                indef = [[t,n] for t,n in pairs(indef)]

            outdef = getChildByName(node, "funrets")
            if outdef is None:
                outdef = []
            else:
                outdef = [n.value for n in outdef.children]


            funcs[getChildByName(node, "funname").children[0].value] = {
                "in":indef,
                "out":outdef,
                "body": getChildByName(node, "funcbody")}

    tg = TypeGetter()

    types = {}
    funcs = {}
    imports = {}

    def prepare(text=None, path=None):
        if text is None and path:
            with open(path, "r") as f:
                text = f.read()
        elif path is None and text:
            text = text
        else:
            print("wat")
            exit(1)
        clean = text.strip()

        prepped = prep(clean)
        if DEBUG:
            print(prepped)
        parsed = l.parse(prepped)

        tg.visit(parsed)

    prepare(text)
    if path is None:
        path = ""

    if len(imports) > 0 and path == None:
        abort("Have imports but don't know where to look for them. Set the path.")

    for name in imports:
        fullpath = path+name+".et"
        if not os.path.exists(fullpath):
            abort("Tried to import %s but could not find it in the path" % (importname))
        prepare(path=fullpath)
        if DEBUG:
            print("Imported %s" % (name))

    # Kahn's algorithm (DAG)

    for k,v in types.items():
        types[k] = {"def":v,"len":0}

    basetypes = {"u":{"def":[],"len":1}}
    types = {**basetypes, **types}

    # Add pointer types
    for typename in list(types):
        types["*"+typename] = {"def":[], "len":1}

    indexorder = kahn(list(types.keys()), [[tnpair[0] for tnpair in value["def"]] for value in types.values()])
    for index in indexorder:
        key = list(types.keys())[index]
        for tnpairindex, tnpair in enumerate(types[key]["def"]):
            # Add subtype length and cumulated offset
            types[key]["def"][tnpairindex] = {
                "type":types[key]["def"][tnpairindex][0],
                "name":types[key]["def"][tnpairindex][1],
                "len":types[tnpair[0]]["len"],
                "offset":types[key]["len"]
            }
            types[key]["len"] += types[tnpair[0]]["len"]

    for typename in types:
        types[typename]["name"] = typename

    generator = Generator()

    hasmain = False
    for funcname in funcs:
        if funcname == "main":
            hasmain = True
        funcs[funcname]["name"] = funcname
        funcs[funcname]["code"] = compile_function(abort, warn, generator, types, funcs, funcname)

    if not hasmain:
        abort("No main function specified")

    # Create stack, heap and io areas
    intro = ["AREA", "AREA", "AREA"]
    # Push return address
    intro += asm("push(0)")
    # Allocate 0 stack frame
    #XXX code += asm("area")
    intro += asm("alloc(%i,1)" % MEM_STACK)

    intro += ["PUSH main", "JUMP"]
    intro = "\n".join(intro) + "\n"

    code = assemble(intro)

    offset = len(code)
    for funcname, func in funcs.items():
        func["offset"] = offset + 1
        # Can't do cross-func optimization this way
        func["code"] = funcname+":"+"\n" + func["code"]
        func["compiled"] = assemble(func["code"])
        code += [len(func["compiled"])] + func["compiled"]
        if DEBUG:
            print(funcname, func["offset"], len(func["compiled"]))
        #code += str(len(func["code"])) + "\n"#XXX not len of CODE STRING, BUT COMPILED!
        #
        #code += func["code"] + "\n"
        offset = len(code)

    code = [funcs["main"]["offset"] if c=="main" else c for c in code]
    #print(code)
    map = []
    for funcname in funcs:
        #intro += ["PUSH %i" % nametoint(funcname), "PUSH %s" % funcname, "KEYSET"]
        map += [nametoint(funcname), funcs[funcname]["offset"]]
    #print(code)
    binary = pack(code,[],map)#See ^XXX^
    #print(binary.data)
    return binary
