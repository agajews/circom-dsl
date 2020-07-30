import textwrap

_global_names = set()


class Op:
    def __init__(self, children, name):
        self.children = children
        self.constraints = []
        self.name = name
        if self.fullname in _global_names:
            suffix = 0
            while self.fullname in _global_names:
                self.name = "{}_{}".format(name, suffix)
                suffix += 1
        _global_names.add(self.fullname)

    def __add__(self, other):
        assert isinstance(other, Op)
        if isinstance(other, Var):
            return VarAdd(self, other)
        else:
            return Add(self, other)

    def __mul__(self, other):
        assert isinstance(other, Op)
        if isinstance(other, Var):
            return VarMul(self, other)
        else:
            return Mul(self, other)

    def __truediv__(self, other):
        assert isinstance(other, Var)
        return VarDiv(self, other)

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
        for child in self.children + self.constraints:
            curr_signals, curr_statements = child._gen(traversed)
            signals += curr_signals
            statements += curr_statements
        if my_signals:
            signals += self._gen_signals()
        statements += self._gen_statements()
        for constraint in self.constraints:
            statements.append("{} === {};".format(self.fullname, constraint.fullname))
        return signals, statements

    def _gen_signals(self):
        signal = "signal {};".format(self.fullname)
        return [signal]

    def _gen_statements(self):
        return []

    def detach(self):
        return VarInput(self)

    def check_equals(self, other):
        assert isinstance(other, Op)
        assert not all([isinstance(self, Var), isinstance(other, Var)])
        self.constraints.append(other)


class Var(Op):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __add__(self, other):
        assert isinstance(other, Op)
        return VarAdd(self, other)

    def __mul__(self, other):
        assert isinstance(other, Op)
        return VarMul(self, other)

    def __truediv__(self, other):
        assert isinstance(other, Op)
        return VarDiv(self, other)

    def _gen_statements(self):
        statements = self._gen_statements()
        for constraint in self.constraints:
            statements.append("{} === {};", self.fullname, constraint.fullname)
        return statements


class VarInput(Var):
    def __init__(self, signal):
        super().__init__(children=[signal], name="var_{}".format(signal.name))

    def _gen_statements(self):
        [signal] = self.children
        statement = "{} <-- {};".format(self.fullname, signal.fullname)
        return [statement]


class VarAdd(Var):
    def __init__(self, left, right):
        super().__init__(
            children=[left, right], name="{}_plus_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} + {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class VarMul(Var):
    def __init__(self, left, right):
        super().__init__(
            children=[left, right], name="{}_times_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} * {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class VarDiv(Var):
    def __init__(self, left, right):
        super().__init__(
            children=[left, right], name="{}_div_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} / {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class Add(Op):
    def __init__(self, left, right):
        super().__init__(
            children=[left, right], name="{}_plus_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <== {} + {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class Mul(Op):
    def __init__(self, left, right):
        super().__init__(
            children=[left, right], name="{}_times_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <== {} * {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class Input(Op):
    def __init__(self, name, private=False):
        super().__init__(children=[], name=name)
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
    c = a.detach() / b
    a.check_equals(c * b)
    circom = c.gen()
    print(circom)
