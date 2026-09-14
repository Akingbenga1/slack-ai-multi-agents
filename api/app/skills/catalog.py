"""Tenant skill catalog.json — navigable JSON tree (folders + skill links)."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any
from uuid import uuid4

CATALOG_VERSION = 1
CATALOG_REL_PATH = "catalog.json"

_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9._-]+")


def empty_catalog() -> dict[str, Any]:
    return {"version": CATALOG_VERSION, "children": []}


def parse_catalog(raw: bytes | str | None) -> dict[str, Any]:
    if raw is None or raw == b"" or raw == "":
        return empty_catalog()
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("catalog must be a JSON object")
    children = data.get("children")
    if children is None:
        children = []
    if not isinstance(children, list):
        raise ValueError("catalog.children must be a list")
    return {"version": int(data.get("version") or CATALOG_VERSION), "children": children}


def dump_catalog(catalog: dict[str, Any]) -> bytes:
    payload = {
        "version": int(catalog.get("version") or CATALOG_VERSION),
        "children": list(catalog.get("children") or []),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def slugify_filename(name: str) -> str:
    base = (name or "").strip().lower().replace(" ", "-")
    base = _SAFE_SEGMENT.sub("-", base).strip("-._") or "skill"
    if not base.endswith(".md"):
        base = f"{base}.md"
    return base


def slugify_folder(name: str) -> str:
    base = (name or "").strip().lower().replace(" ", "-")
    base = _SAFE_SEGMENT.sub("-", base).strip("-._") or "folder"
    return base


def iter_skill_nodes(children: list[dict[str, Any]], *, prefix: str = ""):
    """Yield (folder_prefix, skill_node) for every skill in the tree."""
    for node in children:
        if not isinstance(node, dict):
            continue
        ntype = str(node.get("type") or "")
        if ntype == "skill":
            yield prefix, node
        elif ntype == "folder":
            name = str(node.get("name") or "")
            nested = list(node.get("children") or [])
            next_prefix = f"{prefix}/{name}".strip("/") if name else prefix
            yield from iter_skill_nodes(nested, prefix=next_prefix)


def catalog_index(catalog: dict[str, Any]) -> list[dict[str, str]]:
    """Short index for progressive disclosure: name, description, path."""
    out: list[dict[str, str]] = []
    for _prefix, node in iter_skill_nodes(list(catalog.get("children") or [])):
        path = str(node.get("path") or "").strip()
        if not path:
            continue
        out.append(
            {
                "name": str(node.get("name") or path),
                "description": str(node.get("description") or ""),
                "path": path,
            }
        )
    return out


def _find_folder_children(
    children: list[dict[str, Any]],
    folder_path: str,
) -> list[dict[str, Any]]:
    """Return the children list for ``folder_path`` ('' = root). Mutates in place."""
    target = (folder_path or "").strip().strip("/")
    if not target:
        return children
    parts = [p for p in target.split("/") if p]
    current = children
    walked: list[str] = []
    for part in parts:
        match = None
        for node in current:
            if (
                isinstance(node, dict)
                and node.get("type") == "folder"
                and str(node.get("name") or "") == part
            ):
                match = node
                break
        if match is None:
            raise KeyError(f"folder not found: {'/'.join(walked + [part])}")
        if "children" not in match or not isinstance(match["children"], list):
            match["children"] = []
        current = match["children"]
        walked.append(part)
    return current


def add_folder(catalog: dict[str, Any], *, parent_path: str, name: str) -> dict[str, Any]:
    catalog = deepcopy(catalog)
    children = _find_folder_children(catalog["children"], parent_path)
    clean = (name or "").strip()
    if not clean:
        raise ValueError("folder name is required")
    for node in children:
        if node.get("type") == "folder" and str(node.get("name") or "") == clean:
            raise ValueError(f"folder already exists: {clean}")
    children.append(
        {
            "type": "folder",
            "id": str(uuid4()),
            "name": clean,
            "children": [],
        }
    )
    return catalog


def add_skill(
    catalog: dict[str, Any],
    *,
    folder_path: str,
    name: str,
    description: str,
    path: str,
) -> dict[str, Any]:
    catalog = deepcopy(catalog)
    children = _find_folder_children(catalog["children"], folder_path)
    clean_name = (name or "").strip()
    rel = (path or "").strip().lstrip("/")
    if not clean_name:
        raise ValueError("skill name is required")
    if not rel.endswith(".md"):
        raise ValueError("skill path must end with .md")
    for _prefix, node in iter_skill_nodes(catalog["children"]):
        if str(node.get("path") or "") == rel:
            raise ValueError(f"skill path already exists: {rel}")
    for node in children:
        if node.get("type") == "skill" and str(node.get("name") or "") == clean_name:
            raise ValueError(f"skill already exists: {clean_name}")
    children.append(
        {
            "type": "skill",
            "id": str(uuid4()),
            "name": clean_name,
            "description": (description or "").strip(),
            "path": rel,
        }
    )
    return catalog


def update_skill_node(
    catalog: dict[str, Any],
    *,
    path: str,
    name: str | None = None,
    description: str | None = None,
    new_path: str | None = None,
) -> dict[str, Any]:
    catalog = deepcopy(catalog)
    rel = (path or "").strip().lstrip("/")
    found = None
    for _prefix, node in iter_skill_nodes(catalog["children"]):
        if str(node.get("path") or "") == rel:
            found = node
            break
    if found is None:
        raise KeyError(f"skill not found: {rel}")
    if name is not None:
        found["name"] = name.strip()
    if description is not None:
        found["description"] = description.strip()
    if new_path is not None:
        dest = new_path.strip().lstrip("/")
        if not dest.endswith(".md"):
            raise ValueError("skill path must end with .md")
        for _prefix, node in iter_skill_nodes(catalog["children"]):
            if node is not found and str(node.get("path") or "") == dest:
                raise ValueError(f"skill path already exists: {dest}")
        found["path"] = dest
    return catalog


def remove_skill(catalog: dict[str, Any], *, path: str) -> dict[str, Any]:
    catalog = deepcopy(catalog)
    rel = (path or "").strip().lstrip("/")

    def _walk(nodes: list[dict[str, Any]]) -> bool:
        for i, node in enumerate(list(nodes)):
            if node.get("type") == "skill" and str(node.get("path") or "") == rel:
                nodes.pop(i)
                return True
            if node.get("type") == "folder":
                nested = node.get("children")
                if isinstance(nested, list) and _walk(nested):
                    return True
        return False

    if not _walk(catalog["children"]):
        raise KeyError(f"skill not found: {rel}")
    return catalog


def remove_folder(
    catalog: dict[str, Any],
    *,
    folder_path: str,
) -> tuple[dict[str, Any], list[str]]:
    """Remove folder and return (new_catalog, skill_paths_removed)."""
    catalog = deepcopy(catalog)
    target = (folder_path or "").strip().strip("/")
    if not target:
        raise ValueError("cannot delete the root folder")
    parts = target.split("/")
    parent_path = "/".join(parts[:-1])
    leaf = parts[-1]
    parent_children = _find_folder_children(catalog["children"], parent_path)
    removed_paths: list[str] = []
    idx = None
    folder_node = None
    for i, node in enumerate(parent_children):
        if node.get("type") == "folder" and str(node.get("name") or "") == leaf:
            idx = i
            folder_node = node
            break
    if idx is None or folder_node is None:
        raise KeyError(f"folder not found: {target}")
    for _prefix, skill in iter_skill_nodes(
        list(folder_node.get("children") or []),
        prefix=target,
    ):
        path = str(skill.get("path") or "").strip()
        if path:
            removed_paths.append(path)
    parent_children.pop(idx)
    return catalog, removed_paths


def dissolve_folder(
    catalog: dict[str, Any],
    *,
    folder_path: str,
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """Move folder children to its parent, rewrite skill paths, drop the folder.

    Returns (new_catalog, [(old_skill_path, new_skill_path), ...]).
    """
    catalog = deepcopy(catalog)
    target = (folder_path or "").strip().strip("/")
    if not target:
        raise ValueError("cannot dissolve the root folder")
    parts = target.split("/")
    parent_path = "/".join(parts[:-1])
    leaf = parts[-1]
    parent_children = _find_folder_children(catalog["children"], parent_path)
    idx = None
    folder_node = None
    for i, node in enumerate(parent_children):
        if node.get("type") == "folder" and str(node.get("name") or "") == leaf:
            idx = i
            folder_node = node
            break
    if idx is None or folder_node is None:
        raise KeyError(f"folder not found: {target}")

    moving_children = list(folder_node.get("children") or [])
    for child in moving_children:
        if child.get("type") == "folder":
            name = str(child.get("name") or "")
            for existing in parent_children:
                if (
                    existing.get("type") == "folder"
                    and str(existing.get("name") or "") == name
                ):
                    raise ValueError(
                        f"cannot relocate: folder already exists in parent: {name}"
                    )
        elif child.get("type") == "skill":
            path = str(child.get("path") or "").strip().lstrip("/")
            base = path.split("/")[-1] if path else ""
            dest = f"{parent_path}/{base}".strip("/") if parent_path else base
            for existing in parent_children:
                if (
                    existing.get("type") == "skill"
                    and str(existing.get("path") or "").strip().lstrip("/") == dest
                ):
                    raise ValueError(f"cannot relocate: skill already exists: {dest}")

    prefix = f"{target}/"
    moves: list[tuple[str, str]] = []

    def _rewrite(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            if node.get("type") == "skill":
                old = str(node.get("path") or "").strip().lstrip("/")
                if old.startswith(prefix):
                    rest = old[len(prefix) :]
                    new = f"{parent_path}/{rest}".strip("/") if parent_path else rest
                else:
                    base = old.split("/")[-1] if old else ""
                    if not base:
                        continue
                    new = f"{parent_path}/{base}".strip("/") if parent_path else base
                if new != old:
                    moves.append((old, new))
                    node["path"] = new
            elif node.get("type") == "folder":
                nested = node.get("children")
                if isinstance(nested, list):
                    _rewrite(nested)

    _rewrite(moving_children)
    parent_children.pop(idx)
    parent_children.extend(moving_children)
    return catalog, moves


def move_skill_in_tree(
    catalog: dict[str, Any],
    *,
    path: str,
    dest_folder_path: str,
    new_path: str,
) -> dict[str, Any]:
    """Remove skill from current folder and add under dest with new_path."""
    catalog = deepcopy(catalog)
    rel = (path or "").strip().lstrip("/")
    node_copy = None

    def _detach(nodes: list[dict[str, Any]]) -> bool:
        nonlocal node_copy
        for i, node in enumerate(list(nodes)):
            if node.get("type") == "skill" and str(node.get("path") or "") == rel:
                node_copy = dict(nodes.pop(i))
                return True
            if node.get("type") == "folder":
                nested = node.get("children")
                if isinstance(nested, list) and _detach(nested):
                    return True
        return False

    if not _detach(catalog["children"]) or node_copy is None:
        raise KeyError(f"skill not found: {rel}")
    dest = (new_path or "").strip().lstrip("/")
    if not dest.endswith(".md"):
        raise ValueError("skill path must end with .md")
    for _prefix, node in iter_skill_nodes(catalog["children"]):
        if str(node.get("path") or "") == dest:
            raise ValueError(f"skill path already exists: {dest}")
    node_copy["path"] = dest
    children = _find_folder_children(catalog["children"], dest_folder_path)
    children.append(node_copy)
    return catalog
