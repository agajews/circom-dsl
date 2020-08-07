from dsl import Session


sess = Session()
a = sess.input("a")
b = sess.input("b", private=True)
c = (a.detach() / b).attach()
a.check_equals(c * b)
circom = sess.gen(c)
print(circom)
