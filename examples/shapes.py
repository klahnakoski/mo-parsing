# shapes.py
#
#   A sample program showing how parse actions can convert parsed
# strings into a data type or object.
#
# Copyright 2012, 2019 Paul T. McGuire
#

# define class hierarchy of Shape classes, with polymorphic area method
class Shape:
    def __init__(self, tokens):
        self.__dict__.update(tokens)

    def area(self):
        raise NotImplemented()

    def __str__(self):
        return "<{}>: {}".format(self.__class__.__name__, vars(self))


class Square(Shape):
    def area(self):
        return self.side ** 2


class Rectangle(Shape):
    def area(self):
        return self.width * self.height


class Circle(Shape):
    def area(self):
        return 3.14159 * self.radius ** 2


from mo_parsing import *

number = Regex(r"-?\d+(\.\d*)?").add_parse_action(lambda t: float(t[0]))

# Shape expressions:
#   square : S <centerx> <centery> <side>
#   rectangle: R <centerx> <centery> <width> <height>
#   circle : C <centerx> <centery> <diameter>

squareDefn = "S" + number("centerx") + number("centery") + number("side")
rectDefn = (
    "R" + number("centerx") + number("centery") + number("width") + number("height")
)
circleDefn = "C" + number("centerx") + number("centery") + number("diameter")

squareDefn.add_parse_action(Square)
rectDefn.add_parse_action(Rectangle)


def computeRadius(tokens):
    tokens["radius"] = tokens.diameter / 2.0


circleDefn.add_parse_action(computeRadius, Circle)

shape_expr = squareDefn | rectDefn | circleDefn

tests = """\
C 0 0 100
R 10 10 20 50
S -1 5 10""".splitlines()

for t in tests:
    shape = shape_expr.parse_string(t)[0]



