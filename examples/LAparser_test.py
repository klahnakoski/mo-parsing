from mo_future import first

from examples import LAparser
from examples.LAparser import (
    exprStack,
    _evaluateStack,
    _assignfunc,
    equation,
)

testcases = [
    ("Scalar addition", "a = b+c", "a=(b+c)"),
    ("Vector addition", "V3_a = V3_b + V3_c", "vCopy(a,vAdd(b,c))"),
    ("Vector addition", "V3_a=V3_b+V3_c", "vCopy(a,vAdd(b,c))"),
    ("Matrix addition", "M3_a = M3_b + M3_c", "mCopy(a,mAdd(b,c))"),
    ("Matrix addition", "M3_a=M3_b+M3_c", "mCopy(a,mAdd(b,c))"),
    ("Scalar subtraction", "a = b-c", "a=(b-c)"),
    ("Vector subtraction", "V3_a = V3_b - V3_c", "vCopy(a,vSubtract(b,c))"),
    ("Matrix subtraction", "M3_a = M3_b - M3_c", "mCopy(a,mSubtract(b,c))"),
    ("Scalar multiplication", "a = b*c", "a=b*c"),
    ("Scalar division", "a = b/c", "a=b/c"),
    ("Vector multiplication (dot product)", "a = V3_b * V3_c", "a=vDot(b,c)"),
    (
        "Vector multiplication (outer product)",
        "M3_a = V3_b @ V3_c",
        "mCopy(a,vOuterProduct(b,c))",
    ),
    ("Matrix multiplication", "M3_a = M3_b * M3_c", "mCopy(a,mMultiply(b,c))"),
    ("Vector scaling", "V3_a = V3_b * c", "vCopy(a,vScale(b,c))"),
    ("Matrix scaling", "M3_a = M3_b * c", "mCopy(a,mScale(b,c))"),
    (
        "Matrix by vector multiplication",
        "V3_a = M3_b * V3_c",
        "vCopy(a,mvMultiply(b,c))",
    ),
    ("Scalar exponentiation", "a = b^c", "a=pow(b,c)"),
    ("Matrix inversion", "M3_a = M3_b^-1", "mCopy(a,mInverse(b))"),
    ("Matrix transpose", "M3_a = M3_b^T", "mCopy(a,mTranspose(b))"),
    ("Matrix determinant", "a = M3_b^Det", "a=mDeterminant(b)"),
    ("Vector magnitude squared", "a = V3_b^Mag2", "a=vMagnitude2(b)"),
    ("Vector magnitude", "a = V3_b^Mag", "a=sqrt(vMagnitude2(b))"),
    (
        "Complicated expression",
        "myscalar = (M3_amatrix * V3_bvector)^Mag + 5*(-xyz[i] + 2.03^2)",
        "myscalar=(sqrt(vMagnitude2(mvMultiply(amatrix,bvector)))+5*(-xyz[i]+pow(2.03,2)))",
    ),
    (
        "Complicated Multiline",
        "myscalar = \n(M3_amatrix * V3_bvector)^Mag +\n 5*(xyz + 2.03^2)",
        "myscalar=(sqrt(vMagnitude2(mvMultiply(amatrix,bvector)))+5*(xyz+pow(2.03,2)))",
    ),
]

all_passed = True


def post_test(test, parsed):
    global all_passed

    # copy exprStack to evaluate and clear before running next test
    parsed_stack = exprStack[:]
    exprStack.clear()

    name, testcase, expected = first(tc for tc in testcases if tc[1] == test)
    this_test_passed = False
    try:
        result = _evaluateStack(parsed_stack)

        # Create final assignment
        if LAparser.targetvar:
            result = _assignfunc(LAparser.targetvar, result)
        else:
            raise TypeError

        parsed["result"] = result
        parsed["passed"] = this_test_passed = result == expected
    finally:
        all_passed = all_passed and this_test_passed


equation.runTests([t[1] for t in testcases], postParse=post_test)

assert all_passed
