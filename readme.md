# KnowledgeFlow
## A succinct library for creating zero knowledge proofs, all from the comfort of Python

zkSNARKs, succinct, non-interactive arguments of knowledge, are a cool new gadget that let you prove certain things about certain objects without revealing what they are. For example, if you have a hash function, sha256, and you have an output of the hash function, say `77af778b51abd4a3c51c5ddd97204a9c3ae614ebccb75a606c3b6865aed6744e`, you can use a SNARK to prove that you know a pre-image of the hash function, in this case `cat` (because `sha256(cat) == 77af778b51abd4a3c51c5ddd97204a9c3ae614ebccb75a606c3b6865aed6744e`). The key thing is that you can prove this *without revealing the word `cat`*. And moreover, the size of the proof doesn't depend on the complexity of the function you want to prove something about. Basically SNARKs allow you to output a checksum for an arbitrary computation, proving that you know an input to a function that produces a certain output, *without revealing what the input is*.

Very recently, production-grade libraries for producing SNARKs have started to make their way into the world, first and foremost Circom, a SNARK library focusing on web applications. To build a zero knowledge proof in Circom, you first need to build an arithmetic circuit (like a logical circuit, but with + and * as gates) representing the function you want to compute. The syntax looks a little like this:
```
template Modulo(divisor_bits) {
    signal input dividend; // -8
    signal input divisor; // 5
    signal output remainder; // 2
    signal output quotient; // -2

    component is_neg = IsNegative();
    is_neg.in <== dividend;

    signal output is_dividend_negative;
    is_dividend_negative <== is_neg.out;

    signal output dividend_adjustment;
    dividend_adjustment <== 1 + is_dividend_negative * -2; // 1 or -1

    signal output abs_dividend;
    abs_dividend <== dividend * dividend_adjustment; // 8

    signal output raw_remainder;
    raw_remainder <-- abs_dividend % divisor;
    
    signal output neg_remainder;
    neg_remainder <-- divisor - raw_remainder;

    if (is_dividend_negative == 1 && raw_remainder != 0) {
        remainder <-- neg_remainder;
    } else {
        remainder <-- raw_remainder;
    }

    quotient <-- (dividend - remainder) / divisor; // (-8 - 2) / 5 = -2.

    dividend === divisor * quotient + remainder; // -8 = 5 * -2 + 2.

    component rp = MultiRangeProof(3, 128, SQRT_P);
    rp.in[0] <== divisor;
    rp.in[1] <== quotient;
    rp.in[2] <== dividend;

    // check that 0 <= remainder < divisor
    component remainderUpper = LessThan(divisor_bits);
    remainderUpper.in[0] <== remainder;
    remainderUpper.in[1] <== divisor;
    remainderUpper.out === 1;
}
```
And that's just to compute modulo (%)! As you can see, it's a little wordy. Circom takes inspiration from Verilog, the low-level language computer engineers use to describe electrical circuits, so I tend to think of it as the assembly language of SNARKs.

KnowledgeFlow is the first higher-level language that compiles down into Circom. The same modulo circuit in KnowledgeFlow looks like this:
```python
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
```
A little more readable! Now, let's learn a little more about how to build a circuit like this.

## Building circuits in KnowledgeFlow
The `Session` class is your starting point for all interactions with KnowledgeFlow:
```python
from knowledgeflow import Session

sess = Session()
```
Next, we need to get some inputs to use in our circuit. Inputs can either be public or private, which means what it sounds like: public inputs are known both to the prover and the verifier, while private inputs are known only to the prover (like the word `cat` in our example from before).
```python
a = sess.input("a")
b = sess.input("b", private=True)
```
Once you have some inputs, you can compute with them! Let's make a simple circuit that will multiply `a` and `b` together, and compile it to Circom:
```python
output = a * b
print(sess.gen(output))
```
This will print:
```
template Main() {
    signal input a;
    signal private input b;
    signal output a_times_b__;

    a_times_b__ <== a * b;
}

component main = Main();
```
As you would expect, you can also add inputs together and multiply them by constants:
```python
c = a + b * 3
```
(if you want to put the number on the left ot the multiplication, you have to cast it to a KnowledgeFlow class first:)
```python
c = a + sess.constant(3) * b
```
Now let's do something more complicated. Arithmetic circuits, the framework underlying SNARKs, only let you do addition and multiplication. What if we want to do a division, `a / b`? Well, there's a clever trick. Rather than doing the division in the circuit, we make the prover supply the answer of the division (the quotient, `q`), and then in the circuit verify that `q * b == a`.

The language that we're using to generate circuits actually has two purposes. First, as we've seen, you can use it to generate a proof that you know a pre-image to a certain function. However, it can also be used to *generate the output of the function in the first place*. In fact, this is typically how Circom would be used in production. First you would run your inputs through the Circom circuit to get the output, and then you would go back and use that output, along with the circuit, to generate a proof of correctness.

For our division circuit, in production we don't want to be manually filling in the output of the division every time we want to get the output of our circuit. Instead, we want to tell Circom how to generate this special input, the quotient `q`, that's ostensibly provided by the prover but really should be auto-generated by the circuit.

In KnowledgeFlow, there is a special syntax for cases like this, and it's called *detach*. Normally in KnowledgeFlow, your variables are *attached* to the constraint set. What this means is that every time you do an operation, say multiply `a * b`, a new operation is added to the computational graph that produces the output of your function, *and* a constraint is added to the constraint set that will be verified in the proof. When you detach from the constraint set, the second thing no longer happens, so you have to add your constraints manually, but in exchange you get to use a lot more operations. Including division. Then when you're done, you can re-attach to auto-add constraints going forward.

Here's what it looks like in a real circuit:
```python
q = (a.detach() / b).attach()
a.check_equals(q * b)
```
The rule is that if at least one of the variables in a binary operation is detached, then the operation as a whole is detached and doesn't get a constraint added.

Next, let's show the power of Python metaprogramming by abstracting this circuit into a function:
```python
def div(a, b):
    q = (a.detach() / b).attach()
    a.check_equals(q * b)
    return q
```
Now we can use this function anywhere in our code, without having to manually add division constraints ever again! Neat.
