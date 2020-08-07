from dsl import Session

sess = Session()
a = sess.input("a")
b = sess.input("b", private=True)
c = (a.detach() / b).attach()
a.check_equals(b * c)
print(sess.gen(c))
