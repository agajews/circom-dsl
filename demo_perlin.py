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

sess.include("circomlib/circuits/comparators.circom")
lessthan = sess.extern("LessThan", args=[254], inputs={"in": [2]}, output="out")

sess.include("range_proof/circuit.circom")
multirangeproof = sess.extern(
    "MultiRangeProof",
    args=[3, 128, 1000000000000000000000000000000000000],
    inputs={"in": [3]},
    output="out",
)


def random(x, y, scale):
    full_random = mimc_sponge(_in=[x, y, scale], k=0)
    bits = num2bits(_in=full_random[0])
    truncated = bits[3] * 8 + bits[2] * 4 + bits[1] * 2 + bits[0]
    return truncated


def is_negative(x):
    return sign(_in=num2bits(_in=x))


def abs(x):
    return x * (is_negative(x) * -2 + 1)


def check_less_than(a, b):
    lessthan(_in=[a, b]).check_equals(1)


def check_multi_range(a, b, c):
    multirangeproof(_in=[a, b, c]).check_equals(1)


def modulo(dividend, divisor):
    raw_remainder = abs(dividend).detach() % divisor
    remainder = sess.cond(
        is_negative(dividend).detach() & raw_remainder != 0,
        divisor - raw_remainder,
        raw_remainder,
    ).attach()
    # remainder = sess.cond(
    #     raw_remainder != 0, divisor - raw_remainder, raw_remainder,
    # ).attach()
    quotient = ((dividend.detach() - remainder) / divisor).attach()
    (divisor * quotient + remainder).check_equals(dividend)
    # check_less_than(remainder, divisor)
    # check_multi_range(divisor, quotient, dividend)
    return (quotient, remainder)


dividend = sess.input("dividend")
divisor = sess.input("divisor")
(quotient, remainder) = modulo(dividend, divisor)
print(sess.gen(remainder))
