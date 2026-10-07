from tests.testdirectives.definitions import BaseDirective, success


class Directive(BaseDirective):
    __display_in_cli__ = True

    def __call__(self):
        return success
