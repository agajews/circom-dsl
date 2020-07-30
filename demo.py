from dsl import Input


a = Input("a")
b = Input("b", private=True)
c = (a.detach() / b).attach()
a.check_equals(a, c * b)
circom = c.gen()
print(circom)
