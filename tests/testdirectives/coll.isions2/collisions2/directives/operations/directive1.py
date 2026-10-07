from tests.testdirectives.definitions import directive, success

app_name = "foo"

@directive(display_in_cli=True)
def testfunc():
    """With app name."""
    return success
