from tests.testdirectives.definitions import directive, success


@directive(display_in_cli=True)
def testfunc():
    """Dummy."""
    return success
