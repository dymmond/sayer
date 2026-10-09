from tests.testdirectives.definitions import BaseDirective, success


class Directive(BaseDirective):
    @classmethod
    def run(cls):
        return success
