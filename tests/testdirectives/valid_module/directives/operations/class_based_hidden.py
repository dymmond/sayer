from tests.testdirectives.definitions import BaseDirective, success


class Directive(BaseDirective):
    def __call__(self):
        return success
