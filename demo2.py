from dsl import Input, Constant


a = Input("a")
b = Input("b", private=True)
c = (a.detach() / 2).attach()
d = (a.detach() % 2).attach()
a.check_equals(a, c * 2 + d)
d.check_equals(d * (Constant(1) - d), 0)
output = d + b + 2
circom = output.gen()
print(circom)
