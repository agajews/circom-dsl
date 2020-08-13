from dsl import Session

sess = Session()
a = sess.input("a")
b = sess.input("b")
c = sess.cond(a.detach(), a, b)
print(sess.gen(c))
