import textwrap


class Op:
    def __add__(self, other):
        return Add(self, other)

    @property
    def fullname(self):
        return "{}__".format(self.name)

    def gen(self):
        signals, statements = self._gen(set(), my_signals=False)
        output = "signal output {};".format(self.fullname)
        signals.append(output)

        main = "\n".join(signals) + "\n\n" + "\n".join(statements)
        circom = "template Main() {{\n{}\n}}\n\ncomponent main = Main();".format(
            textwrap.indent(main, "    ")
        )
        return circom

    def _gen(self, traversed, my_signals=True):
        if self in traversed:
            return [], []
        traversed.add(self)
        signals = []
        statements = []
        for child in self.children:
            curr_signals, curr_statements = child._gen(traversed)
            signals += curr_signals
            statements += curr_statements
        if my_signals:
            signals += self._gen_signals()
        statements += self._gen_statements()
        return signals, statements

    def _gen_signals(self):
        signal = "signal {};".format(self.fullname)
        return [signal]

    def _gen_statements(self):
        return []


class Add(Op):
    def __init__(self, left, right):
        self.children = [left, right]
        self.name = "{}_plus_{}".format(left.name, right.name)

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <== {} + {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class Input(Op):
    def __init__(self, name, private=False):
        self.name = name
        self.children = []
        self.private = private

    def _gen_signals(self):
        signal = "signal "
        if self.private:
            signal += "private "
        signal += "input {};".format(self.fullname)
        return [signal]

    @property
    def fullname(self):
        return self.name


if __name__ == "__main__":
    a = Input("a")
    b = Input("b", private=True)
    c = a + b
    d = a + c
    circom = d.gen()
    print(circom)
