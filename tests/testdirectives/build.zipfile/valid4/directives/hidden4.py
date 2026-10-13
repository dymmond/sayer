from tests.testdirectives.definitions import directive, success


@directive
def testfunc():
    return success
