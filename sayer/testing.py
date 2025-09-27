import os
from typing import Any, Dict, List, Optional

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
        args: List[str],
        input: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        **kwargs: Any,
    ) -> SayerTestResult:
        """
        Invoke the CLI with the given arguments.

        Supports an optional `cwd` to temporarily change the working directory
        for the invocation (Click itself does not accept a cwd parameter).

        Args:
            args: List of command-line args, e.g. ["docs", "generate"].
            input: Text to pipe to stdin.
            env: Extra environment variables to set.
            cwd: Working directory to run in (temporarily chdirs).
            **kwargs: Other options forwarded to CliRunner.invoke().

        Returns:
            SayerTestResult: wrapping exit code, output, etc.
        """
        env_vars = os.environ.copy()
        if env:
            env_vars.update(env)

        # Temporarily switch cwd if requested
        prev_dir = os.getcwd()
        try:
            if cwd:
                os.chdir(cwd)

            result = self.runner.invoke(
                self.app.cli,
                args,
                input=input,
                env=env_vars,
                color=False,  # disable ANSI for simplicity
                **kwargs,  # note: cwd and mix_stderr are not passed
            )
            # Patch in return_value if command supports it
            if result.exit_code == 0 and result.exception is None:
                if args:
                    cmd_name = args[0]
                    if cmd_name in self.app.cli.commands:
                        cmd = self.app.cli.commands[cmd_name]
                        if getattr(cmd, "_return_result", False):
                            ctx = cmd.make_context(cmd_name, args[1:], obj={}, resilient_parsing=False)
                            with ctx:
                                rv = cmd.invoke(ctx)
                            result.return_value = rv
        finally:
            if cwd:
                os.chdir(prev_dir)

        return SayerTestResult(result)

    def isolated_filesystem(self, **kwargs: Any) -> Any:
        """
        Proxy to CliRunner.isolated_filesystem(), for filesystem isolation.
        """
        return self.runner.isolated_filesystem(**kwargs)
