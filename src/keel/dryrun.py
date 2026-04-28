"""Op tracker for --dry-run output.

Commands record planned mutations into an OpLog; when --dry-run is set, the
log is printed instead of actually applying the operations.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Op:
    kind: str  # "create" | "modify" | "delete" | "git-worktree-create" | "git-worktree-remove" | "git-branch-rename"
    path: Path
    detail: str = ""
    diff: str | None = None


@dataclass
class OpLog:
    ops: list[Op] = field(default_factory=list)

    def create_file(self, path: Path, *, size: int = 0) -> None:
        self.ops.append(Op(kind="create", path=path, detail=f"({size} B)"))

    def modify_file(self, path: Path, *, diff: str = "") -> None:
        self.ops.append(Op(kind="modify", path=path, diff=diff))

    def delete_file(self, path: Path) -> None:
        self.ops.append(Op(kind="delete", path=path))

    def create_worktree(self, path: Path, *, source: Path, branch: str) -> None:
        self.ops.append(Op(
            kind="git-worktree-create",
            path=path,
            detail=f"from {source} on branch {branch}",
        ))

    def remove_worktree(self, path: Path) -> None:
        self.ops.append(Op(kind="git-worktree-remove", path=path))

    def rename_branch(self, repo: Path, *, old: str, new: str) -> None:
        self.ops.append(Op(
            kind="git-branch-rename",
            path=repo,
            detail=f"{old} → {new}",
        ))

    def format_summary(self) -> str:
        lines: list[str] = []
        groups: dict[str, list[Op]] = {}
        labels = {
            "create": "Would create:",
            "modify": "Would modify:",
            "delete": "Would delete:",
            "git-worktree-create": "Would create git worktree:",
            "git-worktree-remove": "Would remove git worktree:",
            "git-branch-rename": "Would rename branch:",
        }
        for op in self.ops:
            groups.setdefault(op.kind, []).append(op)
        for kind, label in labels.items():
            ops = groups.get(kind, [])
            if not ops:
                continue
            lines.append(f"[dry-run] {label}")
            for op in ops:
                suffix = f"  {op.detail}" if op.detail else ""
                lines.append(f"  {op.path}{suffix}")
                if op.diff:
                    for d in op.diff.splitlines():
                        lines.append(f"    {d}")
        return "\n".join(lines)
