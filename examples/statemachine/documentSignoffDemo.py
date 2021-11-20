#
# documentSignoffDemo.py
#
# Example of a state machine modeling the state of a document in a document
# control system, using named state transitions
#
import documentsignoffstate
from mo_dots import Null as print

print(
    "\n".join(
        t.__name__ for t in documentsignoffstate.DocumentRevisionState.transitions()
    )
)


class Document(documentsignoffstate.DocumentRevisionStateMixin):
    def __init__(self):
        self.initialize_state(documentsignoffstate.New)


def run_demo():
    import random

    doc = Document()


    # begin editing document
    doc.create()



    while not isinstance(doc._state, documentsignoffstate.Approved):

        doc.submit()



        if random.randint(1, 10) > 3:

            doc.reject()
        else:

            doc.approve()



    doc.activate()




run_demo()
