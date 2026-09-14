"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { SkillCatalogTree } from "@/components/skills/SkillCatalogTree";
import {
  CATALOG_FILE_PATH,
  createSkill,
  createSkillFolder,
  deleteSkill,
  deleteSkillFolder,
  getSkill,
  getSkillCatalog,
  listSkillFolderPaths,
  skillBasename,
  skillBodyFromMarkdown,
  skillParentFolder,
  skillsApiErrorMessage,
  updateSkill,
  type SkillCatalog,
  type SkillRecord,
} from "@/lib/skills";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
};

function normalizeFilename(value: string): string {
  const cleaned = value.trim().replace(/^\/+/, "");
  if (!cleaned) return "";
  return cleaned.endsWith(".md") ? cleaned : `${cleaned}.md`;
}

export function SkillsPanel({ accessToken, tenantId }: Props) {
  const [catalog, setCatalog] = useState<SkillCatalog>({ children: [] });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState("");
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [skill, setSkill] = useState<SkillRecord | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [body, setBody] = useState("");
  const [folderName, setFolderName] = useState("");
  const [moveFolder, setMoveFolder] = useState("");
  const [fileName, setFileName] = useState("");
  const [folderDeleteMode, setFolderDeleteMode] = useState<"relocate" | "delete">(
    "relocate",
  );

  const folderOptions = useMemo(
    () => listSkillFolderPaths(catalog.children ?? []),
    [catalog.children],
  );

  const refresh = useCallback(async () => {
    if (!accessToken || !tenantId) return;
    setError(null);
    try {
      const next = await getSkillCatalog(accessToken, tenantId);
      setCatalog(next);
    } catch (err) {
      setError(skillsApiErrorMessage(err));
    }
  }, [accessToken, tenantId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function clearEditor(folder = "") {
    setSkill(null);
    setName("");
    setDescription("");
    setBody("");
    setFileName("");
    setMoveFolder(folder);
  }

  async function openSkill(path: string) {
    if (!accessToken || !tenantId) return;
    if (path === CATALOG_FILE_PATH) {
      openCatalog();
      return;
    }
    setSelectedPath(path);
    const parent = skillParentFolder(path);
    setSelectedFolder(parent);
    setMoveFolder(parent);
    setFileName(skillBasename(path));
    setError(null);
    try {
      const record = await getSkill(accessToken, tenantId, path);
      setSkill(record);
      setName(record.name);
      setDescription(record.description);
      setBody(skillBodyFromMarkdown(record.content));
      setFileName(skillBasename(record.path));
      setMoveFolder(skillParentFolder(record.path));
    } catch (err) {
      setError(skillsApiErrorMessage(err));
    }
  }

  function openCatalog() {
    setSelectedPath(CATALOG_FILE_PATH);
    setSelectedFolder("");
    clearEditor("");
    setError(null);
  }

  async function onCreateFolder() {
    if (!accessToken || !tenantId || !folderName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const next = await createSkillFolder(accessToken, tenantId, {
        name: folderName.trim(),
        parent_path: selectedFolder,
      });
      setCatalog(next);
      setFolderName("");
    } catch (err) {
      setError(skillsApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function onCreateSkill() {
    if (!accessToken || !tenantId || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const record = await createSkill(accessToken, tenantId, {
        name: name.trim(),
        description,
        body,
        folder_path: selectedFolder,
      });
      await refresh();
      setSelectedPath(record.path);
      setSkill(record);
      setMoveFolder(skillParentFolder(record.path));
      setFileName(skillBasename(record.path));
      setSelectedFolder(skillParentFolder(record.path));
    } catch (err) {
      setError(skillsApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function onSaveSkill() {
    if (!accessToken || !tenantId || !selectedPath || !skill) return;
    const nextFile = normalizeFilename(fileName) || skillBasename(selectedPath);
    const currentParent = skillParentFolder(selectedPath);
    const currentFile = skillBasename(selectedPath);
    const relocating =
      moveFolder !== currentParent || nextFile !== currentFile;

    setBusy(true);
    setError(null);
    try {
      const record = await updateSkill(accessToken, tenantId, selectedPath, {
        name: name.trim(),
        description,
        body,
        ...(relocating
          ? {
              dest_folder_path: moveFolder,
              new_filename: nextFile,
            }
          : {}),
      });
      setSkill(record);
      setSelectedPath(record.path);
      setSelectedFolder(skillParentFolder(record.path));
      setMoveFolder(skillParentFolder(record.path));
      setFileName(skillBasename(record.path));
      await refresh();
    } catch (err) {
      setError(skillsApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function onDeleteSkill() {
    if (!accessToken || !tenantId || !selectedPath) return;
    if (!window.confirm(`Delete skill ${selectedPath}?`)) return;
    setBusy(true);
    setError(null);
    try {
      const next = await deleteSkill(accessToken, tenantId, selectedPath);
      setCatalog(next);
      setSelectedPath(null);
      clearEditor(selectedFolder);
    } catch (err) {
      setError(skillsApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function onDeleteFolder() {
    if (!accessToken || !tenantId || !selectedFolder) return;
    const detail =
      folderDeleteMode === "relocate"
        ? `Move contents of "${selectedFolder}" up to the parent, then remove the folder?`
        : `Permanently delete folder "${selectedFolder}" and ALL skills inside it?`;
    if (!window.confirm(detail)) return;
    setBusy(true);
    setError(null);
    try {
      const next = await deleteSkillFolder(
        accessToken,
        tenantId,
        selectedFolder,
        folderDeleteMode,
      );
      setCatalog(next);
      setSelectedFolder("");
      setSelectedPath(null);
      clearEditor("");
    } catch (err) {
      setError(skillsApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (!accessToken || !tenantId) {
    return (
      <p className="text-sm text-muted-foreground">Sign in to manage skills.</p>
    );
  }

  function selectFolder(path: string) {
    setSelectedFolder(path);
    setSelectedPath(null);
    setSkill(null);
    setName("");
    setDescription("");
    setBody("");
    setFileName("");
    setMoveFolder(path);
  }

  const catalogOpen = selectedPath === CATALOG_FILE_PATH;
  const catalogJson = JSON.stringify(catalog, null, 2);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(260px,320px)_1fr]">
      <section className="space-y-4">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-foreground">
            Skill files
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Tenant catalog tree — folders and `.md` skills for this organisation.
          </p>
          <p className="mt-1 font-mono text-[11px] text-muted-foreground">
            Target: {selectedFolder ? `${selectedFolder}/` : "skills/"}
          </p>
        </div>
        <SkillCatalogTree
          nodes={catalog.children ?? []}
          selectedFolder={selectedFolder}
          selectedPath={selectedPath}
          onSelectSkill={(path) => void openSkill(path)}
          onSelectFolder={selectFolder}
          onSelectCatalog={openCatalog}
        />
        <div className="space-y-2 border-t border-border pt-4">
          <label className="block text-xs font-medium">New folder</label>
          <input
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
            value={folderName}
            onChange={(e) => setFolderName(e.target.value)}
            placeholder="Folder name"
          />
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              disabled={busy || !folderName.trim()}
              onClick={() => void onCreateFolder()}
            >
              Add folder
              {selectedFolder ? ` in ${selectedFolder}` : ""}
            </Button>
            {selectedFolder ? (
              <>
                <label className="block space-y-1 text-xs">
                  <span className="font-medium">When deleting folder</span>
                  <select
                    className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                    value={folderDeleteMode}
                    onChange={(e) =>
                      setFolderDeleteMode(
                        e.target.value === "delete" ? "delete" : "relocate",
                      )
                    }
                  >
                    <option value="relocate">
                      Move contents to parent, then remove folder
                    </option>
                    <option value="delete">
                      Delete folder and all skills inside
                    </option>
                  </select>
                </label>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => void onDeleteFolder()}
                >
                  Delete folder
                </Button>
              </>
            ) : null}
          </div>
        </div>
      </section>

      <section className="space-y-4">
        {catalogOpen ? (
          <>
            <div>
              <h2 className="text-sm font-semibold tracking-wide text-foreground">
                {CATALOG_FILE_PATH}
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Read-only index of this organisation’s skill tree. Create, move,
                rename, and delete update it automatically.
              </p>
            </div>
            {error ? (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}
            <pre className="max-h-[min(32rem,60vh)] overflow-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-[12px] leading-5 text-foreground">
              {catalogJson}
            </pre>
          </>
        ) : (
          <>
            <div>
              <h2 className="text-sm font-semibold tracking-wide text-foreground">
                {skill ? "Edit skill" : "Create skill"}
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Skills are markdown files. Agents load the full file only after
                selecting from the catalog.
              </p>
            </div>
            {error ? (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}
            <label className="block space-y-1 text-sm">
              <span className="text-xs font-medium">Name</span>
              <input
                className="w-full rounded-md border border-border bg-background px-2 py-1.5"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-xs font-medium">Description</span>
              <input
                className="w-full rounded-md border border-border bg-background px-2 py-1.5"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </label>
            {skill ? (
              <>
                <label className="block space-y-1 text-sm">
                  <span className="text-xs font-medium">File name</span>
                  <input
                    className="w-full rounded-md border border-border bg-background px-2 py-1.5 font-mono text-sm"
                    value={fileName}
                    onChange={(e) => setFileName(e.target.value)}
                    placeholder="skill-name.md"
                  />
                </label>
                <label className="block space-y-1 text-sm">
                  <span className="text-xs font-medium">Folder</span>
                  <select
                    className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                    value={moveFolder}
                    onChange={(e) => setMoveFolder(e.target.value)}
                  >
                    {folderOptions.map((folder) => (
                      <option key={folder || "root"} value={folder}>
                        {folder ? `skills/${folder}/` : "skills/"}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="font-mono text-[11px] text-muted-foreground">
                  Path: {selectedPath}
                </p>
              </>
            ) : null}
            <label className="block space-y-1 text-sm">
              <span className="text-xs font-medium">Markdown body</span>
              <textarea
                className="min-h-48 w-full rounded-md border border-border bg-background px-2 py-1.5 font-mono text-sm"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="# Steps&#10;&#10;1. …"
              />
            </label>
            <div className="flex flex-wrap gap-2">
              {skill ? (
                <>
                  <Button
                    type="button"
                    disabled={busy || !name.trim()}
                    onClick={() => void onSaveSkill()}
                  >
                    Save skill
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={busy}
                    onClick={() => void onDeleteSkill()}
                  >
                    Delete skill
                  </Button>
                </>
              ) : (
                <Button
                  type="button"
                  disabled={busy || !name.trim()}
                  onClick={() => void onCreateSkill()}
                >
                  Create skill
                  {selectedFolder ? ` in ${selectedFolder}` : ""}
                </Button>
              )}
              {skill ? (
                <Button
                  type="button"
                  variant="ghost"
                  disabled={busy}
                  onClick={() => {
                    setSelectedPath(null);
                    clearEditor(selectedFolder);
                  }}
                >
                  New skill
                </Button>
              ) : null}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
