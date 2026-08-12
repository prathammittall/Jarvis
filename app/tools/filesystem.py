"""Filesystem tools with safety checks."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from app.tools.registry import RiskLevel, ToolDefinition

SPECIAL_DIRS = {
    "desktop": Path.home() / "Desktop",
    "downloads": Path.home() / "Downloads",
    "documents": Path.home() / "Documents",
    "home": Path.home(),
}


def _resolve_path(path_str: str) -> Path:
    path_str = path_str.strip().replace("\\", "/")
    lower = path_str.lower()

    # Handle "Name on desktop/downloads" patterns
    for special, special_path in SPECIAL_DIRS.items():
        if lower.startswith(f"{special}/"):
            return (special_path / path_str.split("/", 1)[1]).resolve()
        if lower.endswith(f" on {special}") or lower.endswith(f" on my {special}"):
            name = lower.split(" on ")[0].strip()
            if name.startswith("called "):
                name = name[7:]
            return (special_path / name).resolve()

    if lower in SPECIAL_DIRS:
        return SPECIAL_DIRS[lower]

    p = Path(path_str)
    if not p.is_absolute():
        # Check if first segment is a special dir
        parts = path_str.split("/")
        if parts[0].lower() in SPECIAL_DIRS:
            return (SPECIAL_DIRS[parts[0].lower()] / "/".join(parts[1:])).resolve()
        p = Path.home() / p
    return p.expanduser().resolve()


def _create_folder(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(args["path"])
    path.mkdir(parents=True, exist_ok=True)
    return {"success": True, "message": f"Created folder {path.name}.", "path": str(path)}


def _create_file(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(args["path"])
    content = args.get("content", "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"success": True, "message": f"Created file {path.name}.", "path": str(path)}


def _read_file(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(args["path"])
    if not path.is_file():
        return {"success": False, "error": f"File not found: {path}"}
    content = path.read_text(encoding="utf-8", errors="replace")
    preview = content[:500] + ("..." if len(content) > 500 else "")
    return {"success": True, "content": preview, "path": str(path)}


def _list_directory(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(args.get("path", "home"))
    if not path.is_dir():
        return {"success": False, "error": f"Directory not found: {path}"}
    entries = []
    for item in sorted(path.iterdir()):
        kind = "dir" if item.is_dir() else "file"
        entries.append({"name": item.name, "type": kind})
    return {"success": True, "entries": entries[:50], "path": str(path), "count": len(entries)}


def _delete_path(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(args["path"])
    if not path.exists():
        return {"success": False, "error": f"Path not found: {path}"}
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return {"success": True, "message": f"Deleted {path.name}."}


def _rename_path(args: dict[str, Any]) -> dict[str, Any]:
    src = _resolve_path(args["path"])
    new_name = args["new_name"]
    dst = src.parent / new_name
    src.rename(dst)
    return {"success": True, "message": f"Renamed to {new_name}.", "path": str(dst)}


def _move_path(args: dict[str, Any]) -> dict[str, Any]:
    src = _resolve_path(args["path"])
    dst = _resolve_path(args["destination"])
    shutil.move(str(src), str(dst))
    return {"success": True, "message": f"Moved to {dst}."}


def _copy_path(args: dict[str, Any]) -> dict[str, Any]:
    src = _resolve_path(args["path"])
    dst = _resolve_path(args["destination"])
    if src.is_dir():
        shutil.copytree(str(src), str(dst))
    else:
        shutil.copy2(str(src), str(dst))
    return {"success": True, "message": f"Copied to {dst}."}


def _open_folder(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(args["path"])
    if not path.is_dir():
        return {"success": False, "error": f"Folder not found: {path}"}
    os.startfile(str(path))
    return {"success": True, "message": f"Opened {path.name}."}


def register(registry) -> None:
    registry.register(ToolDefinition(
        name="create_folder", description="Create a new folder",
        parameters={"path": {"type": "string", "description": "Folder path or name (e.g. 'Test on desktop')"}},
        required=["path"], risk_level=RiskLevel.SAFE, execute=_create_folder,
    ))
    registry.register(ToolDefinition(
        name="create_file", description="Create a text file",
        parameters={
            "path": {"type": "string"}, "content": {"type": "string", "description": "File content"},
        },
        required=["path"], risk_level=RiskLevel.SAFE, execute=_create_file,
    ))
    registry.register(ToolDefinition(
        name="read_file", description="Read a text file",
        parameters={"path": {"type": "string"}}, required=["path"],
        risk_level=RiskLevel.SAFE, execute=_read_file,
    ))
    registry.register(ToolDefinition(
        name="list_directory", description="List contents of a directory",
        parameters={"path": {"type": "string", "description": "Directory path (desktop, downloads, etc.)"}},
        required=[], risk_level=RiskLevel.SAFE, execute=_list_directory,
    ))
    registry.register(ToolDefinition(
        name="delete_path", description="Delete a file or folder (requires confirmation)",
        parameters={"path": {"type": "string"}}, required=["path"],
        risk_level=RiskLevel.CONFIRMATION_REQUIRED, execute=_delete_path,
    ))
    registry.register(ToolDefinition(
        name="rename_path", description="Rename a file or folder",
        parameters={"path": {"type": "string"}, "new_name": {"type": "string"}},
        required=["path", "new_name"], risk_level=RiskLevel.CONFIRMATION_REQUIRED, execute=_rename_path,
    ))
    registry.register(ToolDefinition(
        name="move_path", description="Move a file or folder",
        parameters={"path": {"type": "string"}, "destination": {"type": "string"}},
        required=["path", "destination"], risk_level=RiskLevel.CONFIRMATION_REQUIRED, execute=_move_path,
    ))
    registry.register(ToolDefinition(
        name="copy_path", description="Copy a file or folder",
        parameters={"path": {"type": "string"}, "destination": {"type": "string"}},
        required=["path", "destination"], risk_level=RiskLevel.SAFE, execute=_copy_path,
    ))
    registry.register(ToolDefinition(
        name="open_folder", description="Open a folder in File Explorer",
        parameters={"path": {"type": "string"}}, required=["path"],
        risk_level=RiskLevel.SAFE, execute=_open_folder,
    ))
