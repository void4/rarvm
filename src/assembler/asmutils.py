import time

from lark import Lark, Tree, Transformer

from core.constants import *

asmgrammar = r"""
%ignore /[\t \f]+/  // Whitespace
NAME: /[a-zA-Z_]\w*/
NUMBER: DEC_NUMBER
DEC_NUMBER: /0|[1-9]\d*/i

start: expr
expr: NAME ["(" expr [("," expr)*] ")"] | NUMBER
"""
asml = Lark(asmgrammar, debug=True)

class AsmTransformer(Transformer):
    def start(self, node):
        return node[0]
    def expr(self, node):
        if node[0].type == "NAME":
            code = []
            for arg in node[1:]:
                if isinstance(arg, list):
                    code += arg
                else:
                    raise Exception("ASM Parse Error")
            if node[0].value != "push":
                code += [node[0].value.upper()]
            return code
        elif node[0].type == "NUMBER":
            return ["PUSH %i" % int(node[0].value)]
        else:
            raise Exception("ASM Parse Error")

asmt = AsmTransformer()
def asm(text):
    transformed = asmt.transform(asml.parse(text))
    #print(transformed)
    return transformed

disasmgrammar = """
%ignore /[\t \f]+/  // Whitespace
NAME: /[a-zA-Z_]\w*/
NUMBER: DEC_NUMBER
DEC_NUMBER: /0|[1-9]\d*/i

start: (line "\n")*
line: label | instruction
label: NAME ":"
instruction: NAME [NAME | NUMBER]
"""

def disasm(text):
    lines = text.split("\n")
    lineno = 0
    result = []
    stack = []

    def app(v):
        nonlocal result
        result.append(v)

    while lineno < len(lines):
        cmd = lines[lineno]
        #print(lineno, cmd, stack, "\n", "\n".join(result))
        if cmd.strip() == "":
            pass
        elif cmd.endswith(":"):
            result.append(cmd)
        elif cmd.startswith("PUSH "):
            stack.append(cmd.split()[1])
        elif cmd == "ROT2":
            app("ROT2")
            if len(stack) < 3:
                for i in range(3-len(stack),-1,-1):
                    stack = ["ARG%i" % i] + stack
            stack = stack[:-3] + [stack[-2], stack[-1], stack[-3]]
        elif cmd == "YIELD":
            result.append(str(stack) + "yield(%s)" % ",".join(stack[-2:]))
            stack = stack[:-2]
        else:
            cmdname = cmd.split()[0] if " " in cmd else cmd
            reqs = REQS[INSTR.index(cmdname)]
            cmd = cmd.lower()
            stackeffect = reqs[2]
            stackreq = reqs[1]
            #print(stackreq, stackeffect)
            if stackreq > 0:
                cmd = cmd + "("
                for i in range(stackreq):
                    cmd += stack.pop(-stackreq+i) + ","
                # Remove last comma, prob. could use for else:
                if stackreq > 0:
                    cmd = cmd[:-1]
                cmd += ")"
                if stackreq+stackeffect > 0:
                    for i in range(stackreq+stackeffect):
                        if i > 0:
                            cmd += "[%i]" % i
                        stack.append(cmd)
                else:
                    app(cmd)
            else:
                #result += stack
                #stack = []
                if stackeffect+stackreq > 0:
                    for i in range(stackeffect):
                        stack.append(cmd)
                else:
                    app(cmd)

        lineno += 1
        #time.sleep(0.02)
    for element in stack:
        result.append(element)

    return "\n".join(result).lower()

if __name__ == "__main__":
    with open("source.asm") as f:
        print(disasm(f.read()))
