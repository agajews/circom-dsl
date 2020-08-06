from dsl import Input

a = Input("a")
b = Input("b", private=True)
c = (a.detach() / b).attach()
a.check_equals(a, b * c)
print(c.gen())
