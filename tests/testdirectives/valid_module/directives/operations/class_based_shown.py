from tests.testdirectives.definitions import BaseDirective, success


class Directive(BaseDirective):
    __display_in_cli__ = True

    @classmethod
    def run(cls):
        return success
