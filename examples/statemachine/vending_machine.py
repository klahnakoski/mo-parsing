#
# vending_machine.py
#
# Example of using the statemachine parser without importing a .pystate module.
#
# A vending machine that dispenses candy and chips in a 4x4 grid, A1 thru D4.
# To dispense a product, you must press an alpha button, then a digit button.
#

from examples import statemachine
from examples.statemachine.statemachine import InvalidTransitionException

# Vending machine buttons:
#    A, B, C, D
#    1, 2, 3, 4
#

vending_machine_state_description = """\
statemachine VendingMachineState:
    Idle-(press_alpha_button)->WaitingOnDigit
    WaitingOnDigit-(press_alpha_button)->WaitingOnDigit
    WaitingOnDigit-(press_digit_button)->DispenseProduct
    DispenseProduct-(dispense)->Idle
"""

# convert state machine text to state classes
generated = statemachine.namedStateMachine.transformString(
    vending_machine_state_description
)
# print(generated)
# exec generated code to define state classes and state mixin
exec(generated)


class VendingMachine(VendingMachineStateMixin):
    def __init__(self):
        self.initialize_state(Idle)
        self._pressed = None
        self._alpha_pressed = None
        self._digit_pressed = None

    def press_button(self, button):
        if button in "ABCD":
            self._pressed = button
            self.press_alpha_button()
        elif button in "1234":
            self._pressed = button
            self.press_digit_button()


    def press_alpha_button(self):
        try:
            super().press_alpha_button()
        except InvalidTransitionException as ite:
            pass
        else:
            self._alpha_pressed = self._pressed

    def press_digit_button(self):
        try:
            super().press_digit_button()
        except InvalidTransitionException as ite:
            pass
        else:
            self._digit_pressed = self._pressed
            self.dispense()

    def dispense(self):
        try:
            super().dispense()
        except InvalidTransitionException as ite:
            pass
        else:

            self._alpha_pressed = self._digit_pressed = None


vm = VendingMachine()
for button in "1 A B 1".split():

    vm.press_button(button)

