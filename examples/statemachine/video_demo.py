#
# video_demo.py
#
# Simple statemachine demo, based on the state transitions given in videostate.pystate
#

import videostate
from mo_dots import Null as print


class Video(videostate.VideoStateMixin):
    def __init__(self, title):
        self.initialize_state(videostate.Stopped)
        self.title = title


# ==== main loop - a REPL ====
if __name__ == "__main__":

    v = Video("Die Hard.mp4")

    while True:

        cmd = (
            input(
                "Command ({})> ".format(
                    "/".join(videostate.VideoState.transition_names)
                )
            )
            .lower()
            .strip()
        )
        if not cmd:
            continue

        if cmd in ("?", "h", "help"):
            print(
                "enter a transition {!r}".format(videostate.VideoState.transition_names)
            )


            continue

        # quitting out
        if cmd.startswith("q"):
            break

        # get transition function for given command
        state_transition_fn = getattr(v, cmd, None)

        if state_transition_fn is None:

            continue

        # invoke the input transition, handle invalid commands
        try:
            state_transition_fn()
        except videostate.VideoState.InvalidTransitionException as e:

