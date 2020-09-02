from dsl import Session


sess = Session()
a = sess.input("a")
b = sess.input("b", private=True)
c = (a.detach() / 2).attach()
d = (a.detach() % 2).attach()
a.check_equals(c * 2 + d)
(d * (sess.constant(1) - d)).check_equals(0)
output = d + b + 2
circom = sess.gen(output)
print(circom)
