# escrito por Marco Alfonso, 2004 Noviembre

from mo_dots import Null as print

# importamos los símbolos requeridos desde el módulo
from mo_parsing import *
# usamos las letras en latin1, que incluye las como 'ñ', 'á', 'é', etc.
from mo_parsing.infix import one_of
from mo_parsing.utils import parsing_unicode, nums

alphas = parsing_unicode.Latin1.alphas

# Aqui decimos que la gramatica "saludo" DEBE contener
# una palabra compuesta de caracteres alfanumericos
# (Word(alphas)) mas una ',' mas otra palabra alfanumerica,
# mas '!' y esos seian nuestros tokens
saludo = Word(alphas) + "," + Word(alphas) + one_of("! . ?")
tokens = saludo.parse_string("Hola, Mundo !")

# Ahora parseamos una cadena, "Hola, Mundo!",
# el metodo parse_string, nos devuelve una lista con los tokens
# encontrados, en caso de no haber errores...
for i, token in enumerate(tokens):
    print("Token %d -> %s" % (i, token))

# imprimimos cada uno de los tokens Y listooo!!, he aquí a salida
# Token 0 -> Hola
# Token 1 -> ,
# Token 2-> Mundo
# Token 3 -> !

# ahora cambia el parseador, aceptando saludos con mas que una sola palabra antes que ','
saludo = Group(OneOrMore(Word(alphas))) + "," + Word(alphas) + one_of("! . ?")
tokens = saludo.parse_string("Hasta mañana, Mundo !")

for i, token in enumerate(tokens):
    print("Token %d -> %s" % (i, token))

# Ahora parseamos algunas cadenas, usando el metodo run_tests
saludo.run_tests(
    """\
    Hola, Mundo!
    Hasta mañana, Mundo !
""",
    fullDump=False,
)

# Por supuesto, se pueden "reutilizar" gramáticas, por ejemplo:
numimag = Word(nums) + "i"
numreal = Word(nums)
numcomplex = numreal + "+" + numimag
print(numcomplex.parse_string("3+5i"))

# Cambiar a complejo numero durante parsear:
numcomplex = numcomplex.add_parse_action(lambda t: complex("".join(t).replace("i", "j")))
print(numcomplex.parse_string("3+5i"))

# Excelente!!, bueno, los dejo, me voy a seguir tirando código...
