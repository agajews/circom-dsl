from dsl import Session

sess = Session()
a = sess.input("a")
b = sess.input("b")
c = a.detach() & b
print(sess.gen(c))
