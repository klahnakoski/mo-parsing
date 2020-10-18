# SimpleCalc.py
#
# Demonstration of the parsing module,
# Sample usage
#
#     $ python SimpleCalc.py
#     Type in the string to be parse or 'quit' to exit the program
#     > g=67.89 + 7/5
#     69.29
#     > g
#     69.29
#     > h=(6*g+8.8)-g
#     355.25
#     > h + 1
#     356.25
#     > 87.89 + 7/5
#     89.29
#     > ans+10
#     99.29
#     > quit
#     Good bye!
#
#


# Uncomment the line below for readline support on interactive terminal
# import readline
from mo_parsing import ParseException, Word, alphas, alphanums

# Debugging flag can be set to either "debug_flag=True" or "debug_flag=False"
debug_flag = False

variables = {}

from examples.fourFn import BNF, exprStack, evaluate_stack

# from fourFn import BNF, exprStack, fn, opn
# def evaluateStack( s ):
#     op = s.pop()
#     if op == 'unary -':
#         return -evaluateStack( s )
#     if op in "+-*/^":
#         op2 = evaluateStack( s )
#         op1 = evaluateStack( s )
#         return opn[op]( op1, op2 )
#     elif op == "PI":
#         return math.pi # 3.1415926535
#     elif op == "E":
#         return math.e  # 2.718281828
#     elif op in fn:
#         return fn[op]( evaluateStack( s ) )
#     elif op[0].isalpha():
#         if op in variables:
#             return variables[op]
#         raise Exception("invalid identifier '%s'" % op)
#     else:
#         return float( op )

arithExpr = bnf
ident = Word(alphas, alphanums).set_parser_name("identifier")
assignment = ident("varname") + "=" + arithExpr
pattern = assignment | arithExpr

if __name__ == "__main__":

    # input_string
    input_string = ""

    # Display instructions on how to quit the program

    input_string = input("> ")

    while input_string.strip().lower() != "quit":
        if input_string.strip().lower() == "debug":
            debug_flag = True
            input_string = input("> ")
            continue

        # Reset to an empty exprStack
        del exprStack[:]

        if input_string != "":
            # try parsing the input string
            try:
                L = pattern.parseString(input_string, parseAll=True)
            except ParseException as err:
                L = ["Parse Failure", input_string, (str(err), err.line, err.column)]

            if len(L) == 0 or L[0] != "Parse Failure":
                for i, ob in enumerate(exprStack):
                    if isinstance(ob, str) and ob in variables:
                        exprStack[i] = str(variables[ob])

                # calculate result , store a copy in ans , display the result to user
                try:
                    result = evaluate_stack(exprStack)
                except Exception as e:
                    pass
                else:
                    variables["ans"] = result

                    # Assign result to a variable if required
                    if L.varname:
                        variables[L.varname] = result
            else:
                err_str, err_line, err_col = L[-1]

        # obtain new input string
        input_string = input("> ")
