"""`keel deliverable rm <name>`."""

from __future__ import annotations

import shutil

import typer

from keel import git_ops, workspace
from keel.api import HINT_LIST_DELIVERABLES, ErrorCode, OpLog, Output, confirm_destructive
from keel.markdown_edit import remove_bullet_under_heading
from keel.workspace import resolve_cli_scope


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

    deliv = workspace.deliverable_dir(project, name)

    if dry_run:
        log = OpLog()
        if not keep_design:
            log.delete_file(deliv)
        log.modify_file(
            workspace.design_dir(project) / "CLAUDE.md",
            diff=f"- - **{name}**: ...",
        )
        log.modify_file(
            workspace.design_dir(project) / "design.md",
            diff=f"- - **{name}**: ...",
        )
        out.info(log.format_summary())
        return

    confirm_destructive(
        f"Remove deliverable {project}/{name}? This deletes its design dir.",
        yes=yes,
    )

    # Remove worktree if present (and not --keep-code)
    code_dir = deliv / "code"
    if code_dir.is_dir() and not keep_code:
        try:
            git_ops.remove_worktree(code_dir, force=force)
        except git_ops.GitError as e:
            out.fail(f"failed to remove worktree at {code_dir}: {e}", code=ErrorCode.GIT_FAILED)

    # Remove design dir (unless --keep-design)
    if not keep_design:
        design_dir = deliv / "design"
        if design_dir.is_dir():
            shutil.rmtree(design_dir)

    # If the deliverable dir is now empty (no code/ kept, no design/ kept), rmdir it.
    # If --keep-code preserved code/, leave the dir in place containing just the worktree.
    try:
        if deliv.is_dir() and not any(deliv.iterdir()):
            deliv.rmdir()
    except OSError:
        pass  # best-effort

    # Clean up parent CLAUDE.md
    parent_claude = workspace.design_dir(project) / "CLAUDE.md"
    if parent_claude.is_file():
        parent_claude.write_text(
            remove_bullet_under_heading(parent_claude.read_text(), "Deliverables", f"- **{name}**:")
        )

    # Clean up parent design.md
    parent_design = workspace.design_dir(project) / "design.md"
    if parent_design.is_file():
        parent_design.write_text(
            remove_bullet_under_heading(parent_design.read_text(), "Deliverables", f"- **{name}**:")
        )

    # Clean up sibling deliverable CLAUDE.md files
    siblings_dir = workspace.project_dir(project) / "deliverables"
    if siblings_dir.is_dir():
        for sibling in siblings_dir.iterdir():
            if not sibling.is_dir():
                continue
            sibling_claude = sibling / "design" / "CLAUDE.md"
            if sibling_claude.is_file():
                sibling_claude.write_text(
                    remove_bullet_under_heading(
                        sibling_claude.read_text(), "Sibling deliverables", f"- {name}:"
                    )
                )

    out.info(f"Removed deliverable: {deliv}")
    out.result({"removed": str(deliv)}, human_text=f"Deliverable removed: {deliv}")
