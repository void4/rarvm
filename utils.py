

class L(list):
    def __new__(self, *args, **kwargs):
        return super(L, self).__new__(self, args, kwargs)

    def __init__(self, *args, **kwargs):
        if len(args) == 1 and hasattr(args[0], '__iter__'):
            #print("iter", args[0])
            list.__init__(self)
            for e in args[0]:
                self.append(e)
            if not isinstance(args, tuple):
                self.__dict__.update(args.__dict__)
                self.line = args.line
        else:
            list.__init__(self, args)
        self.__dict__.update(kwargs)

    def __call__(self, **kwargs):
        self.__dict__.update(kwargs)
        return self

def kahn(nodes, edges):
    indegree = [0]*len(nodes)
    for nodeindex, node in enumerate(nodes):
        for edge in edges[nodeindex]:
            indegree[nodes.index(edge)] += 1

    queue = []
    for nodeindex in range(len(nodes)):
        if indegree[nodeindex] == 0:
            queue.append(nodeindex)

    numvisited = 0
    top_order = []

    while queue:
        nodeindex = queue.pop(0)
        node = nodes[nodeindex]
        top_order.append(nodeindex)
        for edge in edges[nodeindex]:
            index = nodes.index(edge)
            indegree[index] -= 1
            if indegree[index] == 0:
                queue.append(index)

        numvisited += 1

    #print(top_order)

    if numvisited != len(nodes):
        print("nope, cycle!")
        exit(1)
    else:
        print("No type cycle detected.")


    indexorder = [None]*len(top_order)
    for i, ti in enumerate(top_order):
        indexorder[ti] = i
    indexorder = indexorder[::-1]
    return indexorder

def stringToWords(arr):

    i = 0
    new = []
    while i < len(arr):
        c = arr[i]
        if c == "\\" and i != len(arr)-1:
            nxt = arr[i+1]
            if nxt == "n":
                new.append(ord("\n"))
                i += 2
            elif nxt == "\\":
                new.append(ord("\\"))
                i += 2
            else:
                abort("Invalid string format \\%s" % nxt, node[0])
        else:
            new.append(ord(c))
            i += 1

    return new

def nametoint(name):
    b = name.encode("utf8")
    if len(b)>8:
        b = b[:8]
        print("WARNING, only using the first 8 bytes of %s" % name)
    return int.from_bytes(b, byteorder="big")
