#
# trafficLightDemo.py
#
# Example of a simple state machine modeling the state of a traffic light
#

import trafficlightstate


class TrafficLight(trafficlightstate.TrafficLightStateMixin):
    def __init__(self):
        self.initialize_state(trafficlightstate.Red)

    def change(self):
        self._state = self._state.next_state()


light = TrafficLight()
for i in range(10):

    light.crossing_signal()
    light.delay()


    light.change()
