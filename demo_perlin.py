from dsl import Session

BIGNUM = 1649267441664000
SCALE_BITS = 16

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
lessthan = sess.extern("LessThan", args=[SCALE_BITS], inputs={"in": [2]}, output="out")

sess.include("range_proof/circuit.circom")
multirangeproof = sess.extern(
    "MultiRangeProof",
    args=[3, 128, 1000000000000000000000000000000000000],
    inputs={"in": [3]},
)

sess.include("QuinSelector.circom")
quinselector = sess.extern(
    "QuinSelector", args=[SCALE_BITS], inputs={"in": SCALE_BITS}, output="out"
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
    multirangeproof(_in=[a, b, c])


def modulo(dividend, divisor):
    raw_remainder = abs(dividend).detach() % divisor
    remainder = sess.cond(
        is_negative(dividend).detach() & raw_remainder != 0,
        divisor - raw_remainder,
        raw_remainder,
    ).attach()
    quotient = ((dividend.detach() - remainder) / divisor).attach()
    (divisor * quotient + remainder).check_equals(dividend)
    check_less_than(remainder, divisor)
    check_multi_range(divisor, quotient, dividend)
    return remainder


def random_gradient_at(x, y, scale):
    vecs = [
        (1000, 0),
        (923, 382),
        (707, 707),
        (382, 923),
        (0, 1000),
        (-383, 923),
        (-708, 707),
        (-924, 382),
        (-1000, 0),
        (-924, -383),
        (-708, -708),
        (-383, -924),
        (-1, -1000),
        (382, -924),
        (707, -708),
        (923, -383),
    ]

    denom = BIGNUM / 1000

    index = random(x, y, scale)
    x = quinselector(_in=[x for x, y in vecs], index=index)
    y = quinselector(_in=[y for x, y in vecs], index=index)
    return (x * denom, y * denom)


def get_corners_and_grad_vectors(x, y, scale):
    bottom_left = (x - modulo(x, scale), y - modulo(y, scale))
    bottom_right = (bottom_left[0] + scale, bottom_left[1])
    top_left = (bottom_left[0], bottom_left[1] + scale)
    top_right = (bottom_left[0] + scale, bottom_right[1] + scale)

    corners = [bottom_left, bottom_right, top_left, top_right]
    grads = []
    for curr_x, curr_y in corners:
        grads.append(random_gradient_at(curr_x, curr_y, scale))
    return corners, grads


def div(x, y):
    out = (x.detach() / y).attach()
    x.check_equals(out * y)
    return out


def get_weight(corner, p, is_bottom, is_left):
    diff = (
        p[0] - corner[0] if is_left else corner[0] - p[0],
        p[1] - corner[1] if is_bottom else corner[1] - p[1],
    )
    numer = (BIGNUM - diff[0]) * (BIGNUM - diff[1])
    return div(numer, BIGNUM)


def dot(a, b):
    sum = a[0] * b[0] + a[1] * b[1]
    return div(sum, BIGNUM)


def perlin_value(coords, grads, p, scale):
    is_bottoms = [True, True, False, False]
    is_lefts = [True, False, True, False]
    outputs = []

    for coord, grad, is_bottom, is_left in zip(coords, grads, is_bottoms, is_lefts):
        dist = (div(p[0] - coord[0], scale), div(p[1] - coord[1], scale))
        dot_prod = dot(grad, dist)
        corner = (div(coord[0], scale), div(coord[1], scale))
        weight = get_weight(corner, p, is_bottom, is_left)
        outputs.append(div(dot_prod * weight, BIGNUM))

    return sum(outputs)


def single_scale_perlin(p, scale):
    coords, grads = get_corners_and_grad_vectors(p[0], p[1], scale)
    p = (BIGNUM * p[0], BIGNUM * p[1])
    coords = [(BIGNUM * x, BIGNUM * y) for x, y in coords]
    return perlin_value(coords, grads, p, scale)


p = (sess.input("p0"), sess.input("p1"))
z = single_scale_perlin(p, 2048)
print(sess.gen(z))
