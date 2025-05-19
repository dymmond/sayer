import os
from typing import Any

from click.testing import CliRunner

from sayer.client import app as _app


class SayerTestResult:
    """
    Encapsulates the result of a CLI invocation.

    Attributes:
        exit_code (int): The process exit code.
        output (str): Combined stdout+stderr output text.
        stdout (str): Captured stdout.
        stderr (str): Captured stderr.
        exception (BaseException | None): Any exception raised by Click.
    """

    def __init__(self, result: Any) -> None:
        self.exit_code: int = result.exit_code
        self.output: str = result.output

        self.stdout: str = getattr(result, "stdout", result.output)
        self.stderr: str = getattr(result, "stderr", "")
        self.exception: BaseException | None = result.exception

    def __repr__(self) -> str:
        return f"<SayerTestResult exit_code={self.exit_code} exception={self.exception!r}>"


class SayerTestClient:
    """
    Provides a simple interface to invoke the Sayer CLI and inspect results.
    Wraps click.testing.CliRunner.
    """

    def __init__(self, app: Any = None) -> None:
        """
        Args:
            app: Optional Sayer app instance; defaults to the `app` from sayer.client.
        """
        self.runner = CliRunner()
        self.app = app or _app  # this is your Sayer() instance

    def invoke(
        self,
        args: list[str],
        input: str | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        **kwargs: Any,
    ) -> SayerTestResult:
        """
        Invoke the CLI with the given arguments.

        Args:
            args: List of command-line args, e.g. ["docs", "generate"].
            input: Text to pipe to stdin.
            env: Extra environment variables to set.
            cwd: Working directory to run in.
            **kwargs: Other options forwarded to CliRunner.invoke().

        Returns:
            SayerTestResult: wrapping exit code, output, etc.
        """
        # Merge env into a copy of os.environ
        env_vars = os.environ.copy()
        if env:
            env_vars.update(env)

        # Invoke the underlying Click group
        result = self.runner.invoke(
            self.app.cli,
            args,
            input=input,
            env=env_vars,
            cwd=cwd,
            **kwargs,
        )
        return SayerTestResult(result)

    def isolated_filesystem(self, **kwargs: Any):
        """
        Proxy to CliRunner.isolated_filesystem(), for filesystem isolation.

        Usage:
            with client.isolated_filesystem(temp_dir=...):
                ...
        """
        return self.runner.isolated_filesystem(**kwargs)
