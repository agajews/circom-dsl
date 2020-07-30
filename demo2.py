from dsl import Input


a = Input("a")
b = Input("b", private=True)
c = (a.detach() / 2).attach()
a.check_equals(c * 2)
circom = (c + b + 2).gen()
print(circom)
