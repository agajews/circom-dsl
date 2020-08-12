from dsl import Session

sess = Session()

sess.include("circomlib/circuits/mimcsponge.circom")
mimc_sponge = sess.extern(
    "MiMCSponge", args=[3, 4, 1], inputs={"in": [3], "k": 1}, output=["outs"]
)

sess.include("circomlib/circuits/bitify.circom")
num2bits = sess.extern("Num2Bits", args=[254], inputs={"in": 1}, output=["out"])

sess.include("circomlib/circuits/sign.circom")
sign = sess.extern("Sign", inputs={"in": [254]}, output="sign")


def random(x, y, scale):
    full_random = mimc_sponge(_in=[x, y, scale], k=0)
    bits = num2bits(_in=full_random[0])
    truncated = bits[3] * 8 + bits[2] * 4 + bits[1] * 2 + bits[0]
    return truncated


def is_negative(x):
    bits = num2bits(_in=x)
    return sign(_in=[bits[i] for i in range(254)])


a = sess.input("a")
b = sess.input("b")
scale = sess.input("scale")
print(sess.gen(random(a, b, scale)))
