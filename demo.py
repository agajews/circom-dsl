from knowledgeflow import Session

sess = Session()
a = sess.input("a")
b = sess.input("b", private=True)
output = a * b
print(sess.gen(output))
