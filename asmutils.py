from lark import Lark, Tree, Transformer

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
