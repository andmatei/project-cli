"""`keel deliverable rm <name>`."""

from __future__ import annotations

import shutil

import typer

from keel import git_ops, workspace
from keel.api import (
    HINT_LIST_DELIVERABLES,
    ErrorCode,
    OpLog,
    Output,
    confirm_destructive,
    resolve_cli_scope,
)
from keel.markdown_edit import remove_bullet_under_heading


def cmd_rm(
    ctx: typer.Context,
    name: str = typer.Argument(...),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Parent project. Auto-detected from CWD if omitted."
    ),
    keep_code: bool = typer.Option(
        False, "--keep-code", help="Preserve the worktree dir even when removing the deliverable."
    ),
    keep_design: bool = typer.Option(
        False,
        "--keep-design",
        help="Preserve the design dir (rare; use to keep records of a removed deliverable).",
    ),
    force: bool = typer.Option(
        False, "--force", help="Allow removal even if the worktree has uncommitted changes."
    ),
    yes: bool = typer.Option(
        False, "-y", "--yes", help="Skip interactive prompts (description, etc.)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print intended operations and exit; write nothing."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Remove a deliverable, including its design dir, worktree, and parent references."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, None, allow_deliverable=False, out=out)
    project = scope.project
    if not workspace.deliverable_exists(project, name):
        out.fail(
            f"deliverable not found: {project}/{name}\n  {HINT_LIST_DELIVERABLES}",
            code=ErrorCode.NOT_FOUND,
        )

    deliv_scope = workspace.Scope(project=project, deliverable=name)
    deliv = deliv_scope.unit_dir

    if dry_run:
        log = OpLog()
        if not keep_design:
            log.delete_file(deliv)
        log.modify_file(
            scope.design_md_path,
            diff=f"- - **{name}**: ...",
        )
        out.info(log.format_summary())
        return

    confirm_destructive(
        f"Remove deliverable {project}/{name}? This deletes its unit dir.",
        yes=yes,
    )

    # Remove worktree if present (and not --keep-code)
    code_dir = deliv / "code"
    if code_dir.is_dir() and not keep_code:
        try:
            git_ops.remove_worktree(code_dir, force=force)
        except git_ops.GitError as e:
            out.fail(f"failed to remove worktree at {code_dir}: {e}", code=ErrorCode.GIT_FAILED)

    # Remove unit contents (unless --keep-design preserves design artifacts).
    # New layout has design files at the unit root rather than a design/ subdir, so we remove
    # everything except the worktree dir(s) we want to keep.
    if not keep_design and deliv.is_dir():
        for child in list(deliv.iterdir()):
            # Preserve any worktree dirs requested via --keep-code
            if keep_code and child.name == "code":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    # If the deliverable dir is now empty (no code/ kept), rmdir it.
    try:
        if deliv.is_dir() and not any(deliv.iterdir()):
            deliv.rmdir()
    except OSError:
        pass  # best-effort

    # Clean up parent design.md (the AST edit is idempotent).
    parent_design = scope.design_md_path
    if parent_design.is_file():
        parent_design.write_text(
            remove_bullet_under_heading(parent_design.read_text(), "Deliverables", f"- **{name}**:")
        )

    out.result(
        {"removed": name, "path": str(deliv)},
        human_text=f"Deliverable removed: {deliv}",
    )
