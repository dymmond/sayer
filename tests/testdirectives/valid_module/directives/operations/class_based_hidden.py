from tests.testdirectives.definitions import BaseDirective, success


class Directive(BaseDirective):
    def run():
        return success
