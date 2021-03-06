import textwrap


class Session:
    """The `Session` class is your starting point for interacting with KnowledgeFlow."""
    def __init__(self):
        self.names = set()
        self.component_names = set()
        self.constraints = []
        self.children = []
        self.includes = set()

    def input(self, name, private=False):
        if name in self.names:
            raise Exception("input named {} not unique in the session".format(name))
        return Input(self, name, private)

    def add_child(self, child):
        self.children.append(child)

    def constant(self, val):
        return Constant(self, val)

    def gen(self, output):
        if output.passthrough:
            output = IdentityOp(output)
        includes = ['include "{}"'.format(path) for path in self.includes]
        traversed = set()
        signals, statements = output._gen(traversed, my_signals=False)
        for child in self.children:
            curr_signals, curr_statements = child._gen(traversed)
            signals += curr_signals
            statements += curr_statements
        for left, right in self.constraints:
            curr_signals, curr_statements = left._gen(traversed)
            signals += curr_signals
            statements += curr_statements
            curr_signals, curr_statements = right._gen(traversed)
            signals += curr_signals
            statements += curr_statements
            statements.append("{} === {};".format(left.fullname, right.fullname))

        output_text = "signal output {};".format(output.fullname)
        signals.append(output_text)

        main = "\n".join(signals) + "\n\n" + "\n".join(statements)
        circom = "{}\n\ntemplate Main() {{\n{}\n}}\n\ncomponent main = Main();".format(
            "\n".join(includes), textwrap.indent(main, "    ")
        )
        return circom

    def include(self, path):
        self.includes.add(path)

    def extern(self, name, inputs, output=None, args=[]):
        return Extern(self, name, inputs, output, args)

    def cond(self, pred, left, right):
        return VarCond(pred, left, right)


class Extern:
    def __init__(self, sess, name, inputs, output, args):
        self.sess = sess
        self.name = name
        self.inputs = inputs
        for name, val in inputs.items():
            if isinstance(val, list):
                assert len(val) == 1
                assert isinstance(val[0], int)
            else:
                assert isinstance(val, int)
        self.output = output
        if isinstance(output, list):
            assert len(output) == 1
            assert isinstance(output[0], str)
        elif output is not None:
            assert isinstance(output, str)
        self.args = args

    def strip_underscores(self, kwargs):
        new_kwargs = {}
        for k, v in kwargs.items():
            if k.startswith("_"):
                k = k[1:]
            new_kwargs[k] = v
        return new_kwargs

    def __call__(self, **kwargs):
        kwargs = self.strip_underscores(kwargs)
        assignments = []
        children = []
        assert len(kwargs) == len(self.inputs)
        for name, typ in self.inputs.items():
            assert name in kwargs
            arg = kwargs[name]
            if isinstance(typ, list):
                if isinstance(arg, list):
                    assert len(arg) == typ[0]
                    for i, child in enumerate(arg):
                        if isinstance(child, int):
                            child = self.sess.constant(child)
                            arg[i] = child
                        assert isinstance(child, Op)
                        assert child.sess is self.sess
                        children.append(child)
                    assignments.append((name, arg))
                else:
                    assert isinstance(arg, ExternArray)
                    assignments.append(((name, typ[0]), arg))
                    children.append(arg)
            else:
                if isinstance(arg, int):
                    arg = self.sess.constant(arg)
                assert isinstance(arg, Op)
                assert arg.sess is self.sess
                children.append(arg)
                assignments.append((name, arg))
        extern_op = ExternOp(self.sess, self.name, children, assignments, self.args)
        self.sess.add_child(extern_op)

        if isinstance(self.output, list):
            return ExternArray(extern_op, self.output[0])
        elif isinstance(self.output, str):
            return ExternOutput(extern_op, self.output)
        else:
            return None


class Op:
    def __init__(self, sess, children, name, passthrough=False):
        self.sess = sess
        self.children = children
        self.constraints = []
        self.name = name
        if not passthrough and self.fullname in sess.names:
            suffix = 0
            while self.fullname in sess.names:
                self.name = "{}_{}".format(name, suffix)
                suffix += 1
        if not passthrough:
            sess.names.add(self.fullname)
        self.passthrough = passthrough

    def __add__(self, other):
        if isinstance(other, int):
            return Add(self, Constant(self.sess, other))
        assert isinstance(other, Op)
        if isinstance(other, Var):
            return VarAdd(self, other)
        else:
            return Add(self, other)

    def __sub__(self, other):
        if isinstance(other, int):
            return Sub(self, Constant(self.sess, other))
        assert isinstance(other, Op)
        if isinstance(other, Var):
            return VarSub(self, other)
        else:
            return Sub(self, other)

    def __mul__(self, other):
        if isinstance(other, int):
            return Mul(self, Constant(self.sess, other))
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

    def _gen(self, traversed, my_signals=True):
        self.generated = True
        if id(self) in traversed:
            return [], []
        traversed.add(id(self))
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

    def detach(self):
        return Detachment(self)

    def check_equals(self, other):
        if isinstance(other, int):
            other = Constant(self.sess, other)
        assert isinstance(other, Op)
        self.sess.constraints.append((self, other))


class ExternOp(Op):
    def __init__(self, sess, extern_name, children, assignments, args):
        super().__init__(
            sess=sess, children=children, name=extern_name, passthrough=True,
        )
        self.extern_name = extern_name
        self.assignments = assignments
        self.args = args
        suffix = 0
        self.component_name = "{}_{}".format(extern_name, suffix)
        while self.component_name in sess.component_names:
            suffix += 1
            self.component_name = "{}_{}".format(extern_name, suffix)
        sess.component_names.add(self.component_name)

    def _gen_statements(self):
        component = "component {} = {}({});".format(
            self.component_name, self.extern_name, ", ".join(str(x) for x in self.args),
        )
        statements = [component]
        for arg_name, args in self.assignments:
            if isinstance(args, list):
                for i, arg in enumerate(args):
                    if isinstance(arg, int):
                        print(arg)
                    statements.append(
                        "{}.{}[{}] <== {};".format(
                            self.component_name, arg_name, i, arg.fullname
                        )
                    )
            elif isinstance(args, ExternArray):
                statements.append(
                    "for (var i__ = 0; i__ < {size}; i__++) {{\n    {comp}.{arg_name}[i__] <== {extern_component}.{extern_prop}[i__]\n}}".format(
                        size=arg_name[1],
                        comp=self.component_name,
                        arg_name=arg_name[0],
                        extern_component=args.extern_op.component_name,
                        extern_prop=args.output_prop,
                    )
                )
            else:
                statements.append(
                    "{}.{} <== {};".format(self.component_name, arg_name, args.fullname)
                )
        return statements

    def _gen_signals(self):
        return []


class ExternOutput(Op):
    def __init__(self, extern_op, output_prop):
        super().__init__(
            sess=extern_op.sess,
            children=[extern_op],
            name=extern_op.component_name,
            passthrough=True,
        )
        self.extern_op = extern_op
        self.output_prop = output_prop

    @property
    def fullname(self):
        return "{}.{}".format(self.extern_op.component_name, self.output_prop)

    def _gen_statements(self):
        return []

    def _gen_signals(self):
        return []


class ExternArray(Op):
    def __init__(self, extern_op, output_prop):
        super().__init__(
            sess=extern_op.sess,
            name=extern_op.component_name,
            children=[extern_op],
            passthrough=True,
        )
        self.extern_op = extern_op
        self.output_prop = output_prop

    def _gen_statements(self):
        return []

    def _gen_signals(self):
        return []

    def __getitem__(self, index):
        assert isinstance(index, int)
        return ExternArrayElem(self.extern_op, self.output_prop, index)


class ExternArrayElem(Op):
    def __init__(self, extern_op, output_prop, index):
        super().__init__(
            sess=extern_op.sess,
            name=extern_op.component_name,
            children=[extern_op],
            passthrough=True,
        )
        self.extern_op = extern_op
        self.output_prop = output_prop
        self.index = index

    @property
    def fullname(self):
        return "{}.{}[{}]".format(
            self.extern_op.component_name, self.output_prop, self.index
        )

    def _gen_statements(self):
        return []

    def _gen_signals(self):
        return []


class Var(Op):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __add__(self, other):
        if isinstance(other, int):
            return VarAdd(self, Constant(self.sess, other))
        assert isinstance(other, Op)
        return VarAdd(self, other)

    def __sub__(self, other):
        if isinstance(other, int):
            return VarSub(self, Constant(self.sess, other))
        assert isinstance(other, Op)
        return VarSub(self, other)

    def __mul__(self, other):
        if isinstance(other, int):
            return VarMul(self, Constant(self.sess, other))
        assert isinstance(other, Op)
        return VarMul(self, other)

    def __truediv__(self, other):
        if isinstance(other, int):
            return VarDiv(self, Constant(self.sess, other))
        assert isinstance(other, Op)
        return VarDiv(self, other)

    def __mod__(self, other):
        if isinstance(other, int):
            return VarMod(self, Constant(self.sess, other))
        assert isinstance(other, Op)
        return VarMod(self, other)

    def __eq__(self, other):
        if isinstance(other, int):
            other = self.sess.constant(other)
        assert isinstance(other, Op)
        return VarEq(self, other)

    def __ne__(self, other):
        if isinstance(other, int):
            other = self.sess.constant(other)
        assert isinstance(other, Op)
        return VarNeq(self, other)

    def __and__(self, other):
        if isinstance(other, int):
            other = self.sess.constant(other)
        assert isinstance(other, Op)
        return VarAnd(self, other)

    def attach(self):
        return Attachment(self)


class Constant(Op):
    def __init__(self, sess, val):
        super().__init__(
            sess=sess, children=[], name="c{}".format(abs(val)), passthrough=True
        )
        self.val = val

    @property
    def fullname(self):
        return str(self.val)

    def _gen_signals(self):
        return []


class Detachment(Var):
    def __init__(self, signal):
        super().__init__(
            sess=signal.sess, children=[signal], name=signal.name, passthrough=True
        )

    @property
    def fullname(self):
        [signal] = self.children
        return signal.fullname

    def _gen(self, *args, **kwargs):
        [signal] = self.children
        return signal._gen(*args, **kwargs)


class Attachment(Op):
    def __init__(self, var):
        super().__init__(sess=var.sess, children=[var], name=var.name, passthrough=True)

    @property
    def fullname(self):
        [var] = self.children
        return var.fullname

    def _gen(self, *args, **kwargs):
        [var] = self.children
        return var._gen(*args, **kwargs)


class VarAdd(Var):
    def __init__(self, left, right):
        assert left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[left, right],
            name="{}_plus_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} + {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class VarSub(Var):
    def __init__(self, left, right):
        assert left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[left, right],
            name="{}_minus_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} - {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class VarMul(Var):
    def __init__(self, left, right):
        assert left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[left, right],
            name="{}_times_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} * {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class VarEq(Var):
    def __init__(self, left, right):
        assert left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[left, right],
            name="{}_eq_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} == {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class VarNeq(Var):
    def __init__(self, left, right):
        assert left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[left, right],
            name="{}_neq_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} != {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class VarAnd(Var):
    def __init__(self, left, right):
        assert left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[left, right],
            name="{}_and_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} && {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class VarCond(Var):
    def __init__(self, pred, left, right):
        assert pred.sess is left.sess and left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[pred, left, right],
            name="if_{}".format(pred.name),
        )

    def _gen_statements(self):
        [pred, left, right] = self.children
        statement = "if ({} == 1) {{ {} <-- {}; }} else {{ {} <-- {}; }}".format(
            pred.fullname, self.fullname, left.fullname, self.fullname, right.fullname
        )
        return [statement]


class VarDiv(Var):
    def __init__(self, left, right):
        assert left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[left, right],
            name="{}_div_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} / {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class VarMod(Var):
    def __init__(self, left, right):
        assert left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[left, right],
            name="{}_mod_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <-- {} % {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class Add(Op):
    def __init__(self, left, right):
        assert left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[left, right],
            name="{}_plus_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <== {} + {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class Sub(Op):
    def __init__(self, left, right):
        assert left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[left, right],
            name="{}_minus_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <== {} - {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class Mul(Op):
    def __init__(self, left, right):
        assert left.sess is right.sess
        super().__init__(
            sess=left.sess,
            children=[left, right],
            name="{}_times_{}".format(left.name, right.name),
        )

    def _gen_statements(self):
        [left, right] = self.children
        statement = "{} <== {} * {};".format(
            self.fullname, left.fullname, right.fullname
        )
        return [statement]


class IdentityOp(Op):
    def __init__(self, signal):
        super().__init__(sess=signal.sess, children=[signal], name=signal.name)

    def _gen_statements(self):
        [signal] = self.children
        statement = "{} <== {};".format(self.fullname, signal.fullname)
        return [statement]


class Input(Op):
    def __init__(self, sess, name, private=False):
        super().__init__(sess=sess, name=name, children=[])
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
