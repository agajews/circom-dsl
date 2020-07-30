import textwrap

_global_names = set()


class Op:
    def __init__(self, children, name, passthrough=False):
        self.generated = False
        self.children = children
        self.constraints = []
        self.name = name
        if not passthrough and self.fullname in _global_names:
            suffix = 0
            while self.fullname in _global_names:
                self.name = "{}_{}".format(name, suffix)
                suffix += 1
        if not passthrough:
            _global_names.add(self.fullname)

    def __add__(self, other):
        if isinstance(other, int):
            return Add(self, Constant(other))
        assert isinstance(other, Op)
        if isinstance(other, Var):
            return VarAdd(self, other)
        else:
            return Add(self, other)

    def __sub__(self, other):
        if isinstance(other, int):
            return Sub(self, Constant(other))
        assert isinstance(other, Op)
        if isinstance(other, Var):
            return VarSub(self, other)
        else:
            return Sub(self, other)

    def __mul__(self, other):
        if isinstance(other, int):
            return Mul(self, Constant(other))
        assert isinstance(other, Op)
        if isinstance(other, Var):
            return VarMul(self, other)
        else:
            return Mul(self, other)

    def __truediv__(self, other):
        assert isinstance(other, Var)
        return VarDiv(self, other)

    def __mod__(self, other):
        assert isinstance(other, Var)
        return VarMod(self, other)

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
        self.generated = True
        if self in traversed:
            return [], []
        traversed.add(self)
        signals = []
        statements = []
        constraint_children = [child for tup in self.constraints for child in tup]
        for child in self.children + constraint_children:
            curr_signals, curr_statements = child._gen(traversed)
            signals += curr_signals
            statements += curr_statements
        if my_signals:
            signals += self._gen_signals()
        statements += self._gen_statements()
        for left, right in self.constraints:
            statements.append("{} === {};".format(left.fullname, right.fullname))
        return signals, statements

    def _gen_signals(self):
        signal = "signal {};".format(self.fullname)
        return [signal]

    def _gen_statements(self):
        return []

    def detach(self):
        return Detachment(self)

    def check_equals(self, left, right):
        if isinstance(left, int):
            left = Constant(left)
        if isinstance(right, int):
            right = Constant(right)
        assert all([isinstance(left, Op), isinstance(right, Op)])
        assert not any([isinstance(left, Var), isinstance(right, Var)])
        self.constraints.append((left, right))

    def __del__(self):
        if not self.generated:
            raise Exception(
                "node {} created but not used, you might have added a constraint to an isolated variable".format(
                    self.fullname
                )
            )


class Var(Op):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __add__(self, other):
        if isinstance(other, int):
            return VarAdd(self, Constant(other))
        assert isinstance(other, Op)
        return VarAdd(self, other)

    def __sub__(self, other):
        if isinstance(other, int):
            return VarSub(self, Constant(other))
        assert isinstance(other, Op)
        return VarSub(self, other)

    def __mul__(self, other):
        if isinstance(other, int):
            return VarMul(self, Constant(other))
        assert isinstance(other, Op)
        return VarMul(self, other)

    def __truediv__(self, other):
        if isinstance(other, int):
            return VarDiv(self, Constant(other))
        assert isinstance(other, Op)
        return VarDiv(self, other)

    def __mod__(self, other):
        if isinstance(other, int):
            return VarMod(self, Constant(other))
        assert isinstance(other, Op)
        return VarMod(self, other)

    def attach(self):
        return Attachment(self)


class Constant(Op):
    def __init__(self, val):
        super().__init__(children=[], name="c{}".format(val), passthrough=True)
        self.val = val

    @property
    def fullname(self):
        return str(self.val)

    def _gen_signals(self):
        return []


class Detachment(Var):
    def __init__(self, signal):
        super().__init__(children=[signal], name=signal.name, passthrough=True)

    @property
    def fullname(self):
        [signal] = self.children
        return signal.fullname

    def _gen_signals(self):
        return []


class Attachment(Op):
    def __init__(self, var):
        super().__init__(children=[var], name=var.name, passthrough=True)

    @property
    def fullname(self):
        [var] = self.children
        return var.fullname

    def _gen_signals(self):
        return []

    def gen(self):
        [var] = self.children
        return var.gen()


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


class VarSub(Var):
    def __init__(self, left, right):
        super().__init__(
            children=[left, right], name="{}_minus_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} - {};".format(
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


class VarMod(Var):
    def __init__(self, left, right):
        super().__init__(
            children=[left, right], name="{}_mod_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} % {};".format(
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


class Sub(Op):
    def __init__(self, left, right):
        super().__init__(
            children=[left, right], name="{}_minus_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <== {} - {};".format(
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
