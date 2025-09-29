import os
from typing import Any, Optional

import click
from click import Group
from click.testing import CliRunner

from sayer.core.client import app as _app


class SayerTestResult:
    def __init__(self, result: Any) -> None:
        self.exit_code: int = result.exit_code
        self.output: str = result.output
        self.stdout: str = getattr(result, "stdout", result.output)
        self.stderr: str = getattr(result, "stderr", "")
        self.exception: BaseException | None = result.exception
        self.return_value: Any = getattr(result, "return_value", None)

    def __repr__(self) -> str:
        return (
            f"<SayerTestResult exit_code={self.exit_code} "
            f"exception={self.exception!r} return_value={self.return_value!r}>"
        )


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
        self.app = app or _app

    def invoke(
        self,
        args: list[str],
        input: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str] = None,
        with_return_value: bool = False,
        **kwargs: Any,
    ) -> SayerTestResult:
        """
        Invoke the CLI with the given arguments.

        Supports an optional `cwd` to temporarily change the working directory
        for the invocation (Click itself does not accept a cwd parameter).

        Args:
            args: list of command-line args, e.g. ["docs", "generate"].
            input: Text to pipe to stdin.
            env: Extra environment variables to set.
            cwd: Working directory to run in (temporarily chdirs).
            with_return_value: If True, return a SayerTestResult `return_value`.
            **kwargs: Other options forwarded to CliRunner.invoke().

        Returns:
            SayerTestResult: wrapping exit code, output, etc.
        """
        env_vars = os.environ.copy()
        if env:
            env_vars.update(env)

        prev_dir = os.getcwd()
        try:
            if cwd:
                os.chdir(cwd)

            # ✅ Leaf resolution only when explicitly requested
            if with_return_value and isinstance(self.app.cli, Group) and args:
                group = self.app.cli
                remaining = args
                cmd: click.Command | None = None

                while isinstance(group, Group) and remaining:
                    ctx = click.Context(group)
                    cmd_name, cmd, remaining = group.resolve_command(ctx, remaining)
                    if cmd is None:
                        break
                    if isinstance(cmd, Group):
                        group = cmd
                        continue
                    break  # leaf found

                if cmd is not None:
                    result = self.runner.invoke(
                        cmd,
                        remaining,
                        input=input,
                        env=env_vars,
                        color=False,
                        standalone_mode=False if with_return_value else True,
                        **kwargs,
                    )
                    return SayerTestResult(result)

            # ✅ Default: invoke root group (Click handles help/errors properly)
            result = self.runner.invoke(
                self.app.cli,
                args,
                input=input,
                env=env_vars,
                color=False,
                standalone_mode=False if with_return_value else True,
                **kwargs,
            )
            return SayerTestResult(result)

        finally:
            if cwd:
                os.chdir(prev_dir)

    def isolated_filesystem(self, **kwargs: Any) -> Any:
        """
        Proxy to CliRunner.isolated_filesystem(), for filesystem isolation.
        """
        return self.runner.isolated_filesystem(**kwargs)
