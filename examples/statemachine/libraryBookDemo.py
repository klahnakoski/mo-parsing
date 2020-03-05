#
# libraryBookDemo.py
#
# Simple statemachine demo, based on the state transitions given in librarybookstate.pystate
#

import statemachine
import librarybookstate


class Book(librarybookstate.BookStateMixin):
    def __init__(self):
        self.initialize_state(librarybookstate.New)


class RestrictedBook(Book):
    def __init__(self):
        super().__init__()
        self._authorized_users = []

    def authorize(self, name):
        self._authorized_users.append(name)

    # specialized checkout to check permission of user first
    def checkout(self, user=None):
        if user in self._authorized_users:
            super().checkout()
        else:
            raise Exception(
                "{} could not check out restricted book".format(
                    user if user is not None else "anonymous"
                )
            )


def run_demo():
    book = Book()
    book.shelve()

    book.checkout()

    book.checkin()

    book.reserve()

    try:
        book.checkout()
    except Exception as e:  # statemachine.InvalidTransitionException:


    book.release()

    book.checkout()



    restricted_book = RestrictedBook()
    restricted_book.authorize("BOB")
    restricted_book.restrict()

    for name in [None, "BILL", "BOB"]:
        try:
            restricted_book.checkout(name)
        except Exception as e:

        else:


    restricted_book.checkin()



run_demo()
