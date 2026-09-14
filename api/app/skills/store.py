"""Skills store — one write path for .md skills + catalog.json over BlobStore."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from api.app.blob_store import BlobStore, resolve_blob_store
from api.app.settings import Settings, get_settings
from api.app.skills.catalog import (
    CATALOG_REL_PATH,
    add_folder,
    add_skill,
    catalog_index,
    dissolve_folder,
    dump_catalog,
    empty_catalog,
    move_skill_in_tree,
    parse_catalog,
    remove_folder,
    remove_skill,
    slugify_filename,
    slugify_folder,
    update_skill_node,
)

_FRONT_MATTER = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z",
    re.DOTALL,
)


class SkillsStoreError(Exception):
    def __init__(self, message: str, *, code: str = "invalid") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class SkillRecord:
    name: str
    description: str
    path: str
    content: str


def _require_client_id(client_id: str | None) -> str:
    cid = str(client_id or "").strip()
    if not cid:
        raise SkillsStoreError("client_id is required", code="invalid")
    return cid


def _skills_prefix(client_id: str) -> str:
    return f"{client_id}/skills"


def _blob_key(client_id: str, rel: str) -> str:
    rel_clean = str(rel or "").strip().lstrip("/")
    if not rel_clean or ".." in PurePosixPath(rel_clean).parts:
        raise SkillsStoreError("invalid skill path", code="invalid")
    return f"{_skills_prefix(client_id)}/{rel_clean}"


def render_skill_markdown(*, name: str, description: str, body: str) -> str:
    desc = (description or "").strip()
    title = (name or "").strip() or "Skill"
    body_text = (body or "").strip()
    if not body_text:
        body_text = f"# {title}\n"
    return (
        f"---\nname: {title}\ndescription: {desc}\n---\n\n{body_text.rstrip()}\n"
    )


def parse_skill_markdown(content: str) -> tuple[str, str, str]:
    """Return (name, description, body) from skill markdown."""
    text = content or ""
    match = _FRONT_MATTER.match(text)
    name = ""
    description = ""
    body = text
    if match:
        fm, body = match.group(1), match.group(2)
        for line in fm.splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip()
            if key == "name":
                name = val
            elif key == "description":
                description = val
    if not name:
        for line in body.splitlines():
            if line.startswith("# "):
                name = line[2:].strip()
                break
    return name or "Skill", description, body


class SkillsStore:
    """Tenant-scoped skills over a BlobStore (pluggable adapter)."""

    def __init__(
        self,
        *,
        client_id: str,
        blob_store: BlobStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.client_id = _require_client_id(client_id)
        self.settings = settings or get_settings()
        self.blob = blob_store or resolve_blob_store(settings=self.settings)

    def _load_catalog(self) -> dict[str, Any]:
        key = _blob_key(self.client_id, CATALOG_REL_PATH)
        try:
            raw = self.blob.get(client_id=self.client_id, key=key)
        except FileNotFoundError:
            return empty_catalog()
        try:
            return parse_catalog(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            raise SkillsStoreError(f"invalid catalog: {exc}", code="invalid") from exc

    def _save_catalog(self, catalog: dict[str, Any]) -> None:
        key = _blob_key(self.client_id, CATALOG_REL_PATH)
        self.blob.put(
            client_id=self.client_id,
            key=key,
            data=dump_catalog(catalog),
        )

    def get_catalog(self) -> dict[str, Any]:
        return self._load_catalog()

    def list_index(self) -> list[dict[str, str]]:
        return catalog_index(self._load_catalog())

    def read_skill(self, path: str) -> SkillRecord:
        rel = path.strip().lstrip("/")
        key = _blob_key(self.client_id, rel)
        try:
            raw = self.blob.get(client_id=self.client_id, key=key)
        except FileNotFoundError as exc:
            raise SkillsStoreError(f"skill not found: {rel}", code="not_found") from exc
        content = raw.decode("utf-8")
        name, description, _body = parse_skill_markdown(content)
        # Prefer catalog metadata when present
        for item in self.list_index():
            if item["path"] == rel:
                name = item["name"] or name
                description = item["description"] or description
                break
        return SkillRecord(name=name, description=description, path=rel, content=content)

    def create_folder(self, *, name: str, parent_path: str = "") -> dict[str, Any]:
        clean = (name or "").strip()
        if not clean:
            raise SkillsStoreError("folder name is required", code="invalid")
        # optional: ensure path segment is filesystem-safe for future file layout
        _ = slugify_folder(clean)
        catalog = self._load_catalog()
        try:
            catalog = add_folder(catalog, parent_path=parent_path, name=clean)
        except KeyError as exc:
            raise SkillsStoreError(str(exc), code="not_found") from exc
        except ValueError as exc:
            raise SkillsStoreError(str(exc), code="conflict") from exc
        self._save_catalog(catalog)
        return catalog

    def create_skill(
        self,
        *,
        name: str,
        description: str = "",
        body: str = "",
        folder_path: str = "",
        filename: str | None = None,
    ) -> SkillRecord:
        clean_name = (name or "").strip()
        if not clean_name:
            raise SkillsStoreError("skill name is required", code="invalid")
        folder = (folder_path or "").strip().strip("/")
        file_name = (filename or "").strip() or slugify_filename(clean_name)
        if not file_name.endswith(".md"):
            file_name = f"{file_name}.md"
        rel = f"{folder}/{file_name}".strip("/") if folder else file_name
        content = render_skill_markdown(
            name=clean_name,
            description=description,
            body=body,
        )
        catalog = self._load_catalog()
        try:
            catalog = add_skill(
                catalog,
                folder_path=folder,
                name=clean_name,
                description=description,
                path=rel,
            )
        except KeyError as exc:
            raise SkillsStoreError(str(exc), code="not_found") from exc
        except ValueError as exc:
            raise SkillsStoreError(str(exc), code="conflict") from exc

        skill_key = _blob_key(self.client_id, rel)
        self.blob.put(
            client_id=self.client_id,
            key=skill_key,
            data=content.encode("utf-8"),
        )
        try:
            self._save_catalog(catalog)
        except Exception:
            try:
                self.blob.delete(client_id=self.client_id, key=skill_key)
            except Exception:
                pass
            raise
        return SkillRecord(
            name=clean_name,
            description=(description or "").strip(),
            path=rel,
            content=content,
        )

    def update_skill(
        self,
        *,
        path: str,
        name: str | None = None,
        description: str | None = None,
        body: str | None = None,
        dest_folder_path: str | None = None,
        new_filename: str | None = None,
    ) -> SkillRecord:
        rel = path.strip().lstrip("/")
        current = self.read_skill(rel)
        next_name = name if name is not None else current.name
        next_desc = description if description is not None else current.description
        if body is not None:
            content = render_skill_markdown(
                name=next_name,
                description=next_desc,
                body=body,
            )
        else:
            _n, _d, old_body = parse_skill_markdown(current.content)
            content = render_skill_markdown(
                name=next_name,
                description=next_desc,
                body=old_body,
            )

        catalog = self._load_catalog()
        moving = dest_folder_path is not None or new_filename is not None
        new_rel = rel
        if moving:
            folder = (
                (dest_folder_path if dest_folder_path is not None else "")
                .strip()
                .strip("/")
            )
            # Keep current folder if only renaming file and dest omitted
            if dest_folder_path is None:
                folder = str(PurePosixPath(rel).parent)
                if folder == ".":
                    folder = ""
            file_name = (new_filename or PurePosixPath(rel).name).strip()
            if not file_name.endswith(".md"):
                file_name = f"{file_name}.md"
            new_rel = f"{folder}/{file_name}".strip("/") if folder else file_name
            try:
                if new_rel != rel:
                    catalog = move_skill_in_tree(
                        catalog,
                        path=rel,
                        dest_folder_path=folder,
                        new_path=new_rel,
                    )
                catalog = update_skill_node(
                    catalog,
                    path=new_rel,
                    name=next_name,
                    description=next_desc,
                )
            except KeyError as exc:
                raise SkillsStoreError(str(exc), code="not_found") from exc
            except ValueError as exc:
                raise SkillsStoreError(str(exc), code="conflict") from exc
        else:
            try:
                catalog = update_skill_node(
                    catalog,
                    path=rel,
                    name=next_name,
                    description=next_desc,
                )
            except KeyError as exc:
                raise SkillsStoreError(str(exc), code="not_found") from exc

        old_key = _blob_key(self.client_id, rel)
        new_key = _blob_key(self.client_id, new_rel)
        self.blob.put(
            client_id=self.client_id,
            key=new_key,
            data=content.encode("utf-8"),
        )
        if new_key != old_key:
            try:
                self.blob.delete(client_id=self.client_id, key=old_key)
            except Exception:
                pass
        try:
            self._save_catalog(catalog)
        except Exception:
            # best-effort: keep new file; catalog save failure surfaces to caller
            raise
        return SkillRecord(
            name=next_name,
            description=next_desc,
            path=new_rel,
            content=content,
        )

    def delete_skill(self, path: str) -> dict[str, Any]:
        rel = path.strip().lstrip("/")
        catalog = self._load_catalog()
        try:
            catalog = remove_skill(catalog, path=rel)
        except KeyError as exc:
            raise SkillsStoreError(str(exc), code="not_found") from exc
        self._save_catalog(catalog)
        try:
            self.blob.delete(client_id=self.client_id, key=_blob_key(self.client_id, rel))
        except Exception:
            pass
        return catalog

    def delete_folder(
        self,
        folder_path: str,
        *,
        mode: str = "delete",
    ) -> dict[str, Any]:
        action = (mode or "delete").strip().lower()
        if action not in {"delete", "relocate"}:
            raise SkillsStoreError(
                "folder delete mode must be 'delete' or 'relocate'",
                code="invalid",
            )
        catalog = self._load_catalog()
        try:
            if action == "relocate":
                catalog, moves = dissolve_folder(catalog, folder_path=folder_path)
                removed: list[str] = []
            else:
                catalog, removed = remove_folder(catalog, folder_path=folder_path)
                moves = []
        except KeyError as exc:
            raise SkillsStoreError(str(exc), code="not_found") from exc
        except ValueError as exc:
            raise SkillsStoreError(str(exc), code="invalid") from exc

        # Apply blob moves before catalog save so a move failure leaves catalog unchanged.
        moved_keys: list[tuple[str, str]] = []
        try:
            for old_rel, new_rel in moves:
                old_key = _blob_key(self.client_id, old_rel)
                new_key = _blob_key(self.client_id, new_rel)
                raw = self.blob.get(client_id=self.client_id, key=old_key)
                self.blob.put(
                    client_id=self.client_id,
                    key=new_key,
                    data=raw,
                )
                moved_keys.append((old_key, new_key))
            self._save_catalog(catalog)
        except Exception:
            for old_key, new_key in reversed(moved_keys):
                try:
                    raw = self.blob.get(client_id=self.client_id, key=new_key)
                    self.blob.put(client_id=self.client_id, key=old_key, data=raw)
                    self.blob.delete(client_id=self.client_id, key=new_key)
                except Exception:
                    pass
            raise

        for old_key, _new_key in moved_keys:
            try:
                self.blob.delete(client_id=self.client_id, key=old_key)
            except Exception:
                pass
        for rel in removed:
            try:
                self.blob.delete(
                    client_id=self.client_id,
                    key=_blob_key(self.client_id, rel),
                )
            except Exception:
                pass
        return catalog


def get_skills_store(
    *,
    client_id: str,
    blob_store: BlobStore | None = None,
    settings: Settings | None = None,
) -> SkillsStore:
    return SkillsStore(client_id=client_id, blob_store=blob_store, settings=settings)
