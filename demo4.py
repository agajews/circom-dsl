from dsl import Session

bits = 8


sess = Session()
dividend = sess.input("dividend")
divisor = sess.input("divisor", private=True)

remainder = (dividend.detach() % divisor).attach()
quotient = ((dividend.detach() - remainder) / divisor).attach()

dividend.check_equals(divisor * quotient + remainder)

sess.include("circomlib/circuits/comparators.circom")
lessthan = sess.extern("LessThan", args=[bits], inputs={"in": [2]}, output="out")

lessthan(_in=[remainder, divisor]).check_equals(1)

print(sess.gen(remainder))
