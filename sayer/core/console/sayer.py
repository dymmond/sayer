import inspect
from typing import Dict, List, Optional, Tuple, Union

import click
from rich import box
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sayer.conf import monkay
from sayer.utils.console import console
from sayer.utils.signature import generate_signature


class RichHelpFormatter:
    """
    Renders a rich help screen for a click command.

    This class breaks the help rendering process into modular,
    overridable methods. To customize, create a subclass and
    override the specific 'render_*' or '_get_*' methods.
    """

    def __init__(self, ctx: click.Context):
        self.ctx: click.Context = ctx
        self.cmd: Union[click.Command, click.Group] = ctx.command

        # Load settings from config
        self.display_full_help: bool = monkay.settings.display_full_help
        self.display_help_length: int = monkay.settings.display_help_length

    def render_help(self) -> None:
        """
        The main orchestration method.

        It fetches all components, prints them in order,
        and then exits the context.
        """
        if getattr(self.cmd, "hidden", False):
            return

        # Get all renderable components
        usage = self.render_usage()
        description = self.render_description()
        options_panel = self.render_options()
        commands_panel = self.render_commands()
        custom_command_panels = self.render_custom_commands()

        # Print them in order with spacing
        console.print(usage)
        console.print()  # blank line

        console.print(description)
        console.print()

        if options_panel:
            console.print(options_panel)
            console.print()

        if commands_panel:
            console.print(commands_panel)
            console.print()

        for panel in custom_command_panels:
            console.print(panel)

        # Exit
        self.ctx.exit()


    def render_usage(self) -> Padding:
        """Renders the 'Usage:' line."""
        signature = generate_signature(self.cmd)
        if isinstance(self.cmd, click.Group):
            usage_line = f"{self.ctx.command_path} [OPTIONS] COMMAND [ARGS]..."
        else:
            usage_line = f"{self.ctx.command_path} {signature}".rstrip()

        usage_text = Text()
        usage_text.append("Usage: ", style="bold yellow")
        usage_text.append(usage_line, style="white")
        return Padding(usage_text, (1, 0, 0, 1))

    def render_description(self) -> Padding:
        """Renders the command's description as Markdown."""
        raw_help = (
            self.cmd.help
            or (self.cmd.callback.__doc__ or "").strip()
            or "No description provided."
        )
        description_renderable = Markdown(raw_help)
        return Padding(description_renderable, (0, 0, 0, 1))

    def render_options(self) -> Optional[Panel]:
        """Renders the 'Options' panel."""
        options_data, max_flag_len = self._get_options_data()

        if not options_data:
            return None

        opt_table = Table(
            show_header=True,
            header_style="gray50",
            box=None,
            pad_edge=False,
            padding=(0, 2),
            expand=False,
        )
        opt_table.add_column(
            "Flags", style="bold cyan", no_wrap=True, min_width=max_flag_len
        )
        opt_table.add_column("Required", style="red", no_wrap=True, justify="center")
        opt_table.add_column("Default", style="blue", no_wrap=True, justify="center")
        opt_table.add_column("Description", style="gray50", ratio=1)

        for flags_str, required_str, default_str, desc in options_data:
            flags_text = self._format_flags_text(flags_str)
            opt_table.add_row(
                flags_text,
                required_str,
                default_str,
                desc,
            )

        return Panel(
            opt_table,
            title="Options",
            title_align="left",
            border_style="gray50",
            box=box.ROUNDED,
            padding=(0, 1),
        )

    def render_commands(self) -> Optional[Panel]:
        """Renders the 'Commands' panel for standard subcommands."""
        sub_items, max_cmd_len = self._get_subcommand_data()

        if not sub_items:
            return None

        cmd_table = Table(
            show_header=True,
            header_style="gray50",
            box=None,
            pad_edge=False,
            padding=(0, 2),
            expand=False,
        )
        cmd_table.add_column(
            "Name", style="bold cyan", no_wrap=True, min_width=max_cmd_len
        )
        cmd_table.add_column("Description", style="gray50", ratio=1)

        for name, summary in sub_items:
            cmd_table.add_row(Text(name, style="bold cyan"), summary)

        return Panel(
            cmd_table,
            title="Commands",
            title_align="left",
            border_style="gray50",
            box=box.ROUNDED,
            padding=(0, 1),
        )

    def render_custom_commands(self) -> List[Panel]:
        """Renders a list of panels for 'custom_commands' groups."""
        if not (hasattr(self.cmd, "custom_commands") and self.cmd.custom_commands):
            return []

        items = (
            self.cmd.custom_commands.items()
            if isinstance(self.cmd.custom_commands, dict)
            else self.cmd.custom_commands
        )
        grouped: Dict[str, List[Tuple[str, str]]] = {}
        default_title = getattr(
            getattr(self.cmd, "custom_command_config", None),
            "title",
            "Custom Commands",
        )

        for name, sub in items:
            raw_sub_help = getattr(sub, "help", "") or ""
            lines = raw_sub_help.strip().splitlines()
            summary = lines[0] if lines else ""

            title = getattr(
                getattr(sub, "custom_command_config", None), "title", default_title
            )
            grouped.setdefault(title, []).append((name, summary))

        panels = []
        for title, sub_items in grouped.items():
            max_cmd_len = max((len(name) for name, _ in sub_items), default=0)

            custom_table = Table(
                show_header=True,
                header_style="gray50",
                box=None,
                pad_edge=False,
                padding=(0, 2),
                expand=False,
            )
            custom_table.add_column(
                "Name", style="bold cyan", no_wrap=True, min_width=max_cmd_len
            )
            custom_table.add_column("Description", style="gray50", ratio=1)

            for name, summary in sub_items:
                custom_table.add_row(Text(name, style="bold cyan"), summary)

            panels.append(
                Panel(
                    custom_table,
                    title=title,
                    title_align="left",
                    border_style="gray50",
                    box=box.ROUNDED,
                    padding=(0, 1),
                )
            )

        return panels

    def _get_options_data(
        self,
    ) -> Tuple[List[Tuple[str, str, str, str]], int]:
        """Extracts, formats, and returns option data and max flag length."""
        user_options = [
            p
            for p in self.cmd.params
            if not getattr(p, "hidden", False)
            and isinstance(p, (click.Option, click.Argument))
            and "--help" not in getattr(p, "opts", ())
        ]

        flags_req_def_desc: List[Tuple[str, str, str, str]] = []
        max_flag_len = 0

        for param in user_options:
            flags_str = "/".join(param.opts)  # No longer reversed
            if len(flags_str) > max_flag_len:
                max_flag_len = len(flags_str)

            required_str = "Yes" if getattr(param, "required", False) else "No"

            default_val = getattr(param, "default", inspect._empty)
            if default_val in (inspect._empty, None, ...):
                default_str = ""
            elif isinstance(default_val, bool):
                default_str = "true" if default_val else "false"
            else:
                default_str = str(default_val)

            desc = getattr(param, "help", "")
            flags_req_def_desc.append((flags_str, required_str, default_str, desc))

        return flags_req_def_desc, max_flag_len

    def _format_flags_text(self, flags_str: str) -> Text:
        """Helper to format flag strings with special colors."""
        flags_text = Text()
        parts = flags_str.split("/")
        for i, part in enumerate(parts):
            if i > 0:
                flags_text.append("/", style="bold cyan")  # Add separator back
            if part.startswith("--no-"):
                flags_text.append(part, style="magenta")
            else:
                flags_text.append(part, style="bold cyan")
        return flags_text

    def _get_subcommand_data(self) -> Tuple[List[Tuple[str, str]], int]:
        """Extracts, formats, and returns subcommand data and max name length."""
        if not isinstance(self.cmd, click.Group):
            return [], 0

        sub_items: List[Tuple[str, str]] = []
        max_cmd_len = 0

        for name, sub in self.cmd.commands.items():
            if getattr(sub, "hidden", False) is True:
                continue
            if (
                hasattr(self.cmd, "custom_commands")
                and self.cmd.custom_commands
                and name in self.cmd.custom_commands
            ):
                continue

            raw_sub_help = sub.help or ""
            sub_summary = self._format_subcommand_summary(raw_sub_help)

            if len(name) > max_cmd_len:
                max_cmd_len = len(name)
            sub_items.append((name, sub_summary))

        return sub_items, max_cmd_len

    def _format_subcommand_summary(self, raw_help: str) -> str:
        """Formats the help string for a subcommand in the list."""
        if not self.display_full_help:
            lines = raw_help.strip().splitlines()
            first_line = lines[0] if lines else ""
            remaining = " ".join(lines[1:]).strip()
            if len(remaining) > self.display_help_length:
                remaining = remaining[: self.display_help_length] + "..."
            return f"{first_line}\n{remaining}" if remaining else first_line
        else:
            return raw_help


def render_help_for_command(*args, **kwargs) -> None:
    """
    Renders help using the RichHelpFormatter class.

    This function is designed to be called in two ways,
    due to inconsistencies in the Sayer framework:

    1. As a direct function: render_help_for_command(ctx)
       (Likely used by SayerCommand.format_help)
    2. As a 'format_help' method replacement: cmd.format_help = render_help_for_command
       (Likely used by SayerGroup, which passes [self, ctx, formatter])

    To provide a custom formatter, create a subclass of RichHelpFormatter
    and attach it to the context, e.g.:
    ctx.formatter_class = MyCustomHelpFormatter
    """

    ctx: click.Context
    if args and isinstance(args[0], click.Context):
        # Case 1: render_help_for_command(ctx)
        ctx = args[0]
    elif len(args) > 1 and isinstance(args[1], click.Context):
        # Case 2: render_help_for_command(self, ctx, formatter)
        ctx = args[1]
    else:
        raise TypeError(
            "Could not find click.Context in args for render_help_for_command. "
            f"Received args: {args}"
        )

    # Look for a custom formatter class on the context,
    # default to our new base class.
    FormatterClass = getattr(ctx, "formatter_class", RichHelpFormatter)

    # If the formatter_class on the context is NOT one of our rich
    # formatters (e.g., it's a default click.HelpFormatter),
    # we MUST ignore it and use our RichHelpFormatter,
    # otherwise we'll crash trying to call methods that don't exist.
    try:
        if not issubclass(FormatterClass, RichHelpFormatter):
            FormatterClass = RichHelpFormatter
    except TypeError:
        # issubclass fails if FormatterClass is not a class
        FormatterClass = RichHelpFormatter

    formatter = FormatterClass(ctx)
    formatter.render_help()
