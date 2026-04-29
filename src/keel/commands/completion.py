"""`keel completion` — print (or install) shell completion for keel."""
from __future__ import annotations

import typer

from keel.output import Output

_SUPPORTED = {"bash", "zsh", "fish"}

_INSTALL_PATHS = {
    "bash": "~/.bash_completion.d/keel",
    "zsh": "~/.zfunc/_keel",
    "fish": "~/.config/fish/completions/keel.fish",
}


def cmd_completion(
    ctx: typer.Context,
    shell: str = typer.Argument(..., help="Shell to generate completion for: bash, zsh, or fish."),
    install: bool = typer.Option(False, "--install", help="Write the completion script to the canonical location for the chosen shell."),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Print (or install) shell completion for `keel`."""
    out = Output.from_context(ctx, json_mode=json_mode)

    if shell not in _SUPPORTED:
        out.error(
            f"unsupported shell: {shell!r}. Supported: {', '.join(sorted(_SUPPORTED))}",
            code="bad_shell",
        )
        raise typer.Exit(code=2)

    # Use Click's completion machinery directly — works in-process under CliRunner.
    import click.shell_completion as cc
    import typer.main as _typer_main

    from keel.app import app as _app  # deferred to avoid circular import at module level

    click_app = _typer_main.get_command(_app)
    comp_cls = cc.get_completion_class(shell)
    script = comp_cls(click_app, {}, prog_name="keel", complete_var="_KEEL_COMPLETE").source()

    if install:
        from pathlib import Path

        target = Path(_INSTALL_PATHS[shell]).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(script)
        out.info(f"Installed completion for {shell} → {target}")
        out.result({"path": str(target), "shell": shell}, human_text=str(target))
    else:
        if json_mode:
            out.result({"shell": shell, "script": script})
        else:
            print(script)
