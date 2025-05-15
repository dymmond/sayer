from typing import List, Union

import click
from click.testing import CliRunner


class SayerTestClient:
    def __init__(self, app: Union[click.BaseCommand, click.Group]):
        self.app = app
        self.runner = CliRunner()

    def invoke(self, *args: Union[str, List[str]], input: str = None, env: dict = None):
        flat_args = []
        for arg in args:
            if isinstance(arg, list):
                flat_args.extend(arg)
            else:
                flat_args.append(arg)
        return self.runner.invoke(self.app, flat_args, input=input, env=env)
