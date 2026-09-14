"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Folder,
  FolderOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { CATALOG_FILE_PATH, type SkillCatalogNode } from "@/lib/skills";

type Props = {
  nodes: SkillCatalogNode[];
  selectedFolder: string;
  selectedPath: string | null;
  onSelectFolder: (folderPath: string) => void;
  onSelectSkill: (path: string) => void;
  onSelectCatalog: () => void;
};

const ROW =
  "flex w-full items-center gap-1 rounded-md py-[3px] pr-2 text-left font-mono text-[13px] leading-5 outline-none focus-visible:ring-2 focus-visible:ring-primary/30";

function collectFolderPaths(
  nodes: SkillCatalogNode[],
  parent = "",
  out: string[] = [],
): string[] {
  for (const node of nodes) {
    if (node.type !== "folder") continue;
    const path = parent ? `${parent}/${node.name}` : node.name;
    out.push(path);
    collectFolderPaths(node.children ?? [], path, out);
  }
  return out;
}

function ancestorsOfPath(path: string): string[] {
  const parts = path.split("/").filter(Boolean);
  if (parts.length <= 1) return [];
  const folders = parts.slice(0, -1);
  return folders.map((_, i) => folders.slice(0, i + 1).join("/"));
}

function skillFileLabel(node: Extract<SkillCatalogNode, { type: "skill" }>) {
  const base = node.path.split("/").pop() || node.path;
  return base.endsWith(".md") ? base : `${base}.md`;
}

function TreeBranch({
  nodes,
  depth,
  folderPath,
  expanded,
  selectedFolder,
  selectedPath,
  onToggle,
  onSelectFolder,
  onSelectSkill,
}: {
  nodes: SkillCatalogNode[];
  depth: number;
  folderPath: string;
  expanded: Set<string>;
  selectedFolder: string;
  selectedPath: string | null;
  onToggle: (path: string) => void;
  onSelectFolder: (path: string) => void;
  onSelectSkill: (path: string) => void;
}) {
  if (!nodes.length) return null;

  return (
    <ul className="m-0 list-none p-0" role="group">
      {nodes.map((node, index) => {
        const isLast = index === nodes.length - 1;
        const guidePad = 10 + depth * 16;

        if (node.type === "folder") {
          const path = folderPath ? `${folderPath}/${node.name}` : node.name;
          const isOpen = expanded.has(path);
          const isSelected = selectedFolder === path && !selectedPath;

          return (
            <li key={`folder:${path}`} className="relative" role="treeitem" aria-expanded={isOpen}>
              {depth > 0 ? (
                <span
                  aria-hidden
                  className={cn(
                    "pointer-events-none absolute top-0 w-px bg-border",
                    isLast && !isOpen ? "h-[14px]" : "bottom-0",
                  )}
                  style={{ left: guidePad - 8 }}
                />
              ) : null}
              <div
                className={cn(
                  ROW,
                  isSelected
                    ? "bg-primary/15 text-foreground"
                    : "text-foreground/90 hover:bg-muted/70",
                )}
                style={{ paddingLeft: guidePad }}
              >
                <button
                  type="button"
                  className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-muted-foreground hover:text-foreground"
                  aria-label={isOpen ? `Collapse ${node.name}` : `Expand ${node.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggle(path);
                  }}
                >
                  {isOpen ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                </button>
                <button
                  type="button"
                  className="flex min-w-0 flex-1 items-center gap-1.5"
                  onClick={() => onSelectFolder(path)}
                >
                  {isOpen ? (
                    <FolderOpen className="h-4 w-4 shrink-0 text-amber-600" />
                  ) : (
                    <Folder className="h-4 w-4 shrink-0 text-amber-600" />
                  )}
                  <span className="truncate">{node.name}</span>
                </button>
              </div>
              {isOpen ? (
                <TreeBranch
                  nodes={node.children ?? []}
                  depth={depth + 1}
                  folderPath={path}
                  expanded={expanded}
                  selectedFolder={selectedFolder}
                  selectedPath={selectedPath}
                  onToggle={onToggle}
                  onSelectFolder={onSelectFolder}
                  onSelectSkill={onSelectSkill}
                />
              ) : null}
            </li>
          );
        }

        const active = selectedPath === node.path;
        const label = skillFileLabel(node);
        return (
          <li key={`skill:${node.path}`} className="relative" role="treeitem">
            {depth > 0 ? (
              <span
                aria-hidden
                className={cn(
                  "pointer-events-none absolute top-0 w-px bg-border",
                  isLast ? "h-[14px]" : "bottom-0",
                )}
                style={{ left: guidePad - 8 }}
              />
            ) : null}
            <button
              type="button"
              title={node.description ? `${node.name} — ${node.description}` : node.name}
              className={cn(
                ROW,
                "gap-1.5",
                active
                  ? "bg-primary/15 font-medium text-foreground"
                  : "text-foreground/85 hover:bg-muted/70",
              )}
              style={{ paddingLeft: guidePad + 20 }}
              onClick={() => onSelectSkill(node.path)}
            >
              <FileText className="h-4 w-4 shrink-0 text-sky-700" />
              <span className="truncate">{label}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function SkillCatalogTree({
  nodes,
  selectedFolder,
  selectedPath,
  onSelectFolder,
  onSelectSkill,
  onSelectCatalog,
}: Props) {
  const allFolders = useMemo(() => collectFolderPaths(nodes), [nodes]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const knownFolders = useRef<Set<string>>(new Set());

  useEffect(() => {
    setExpanded((prev) => {
      const next = new Set(prev);
      for (const path of allFolders) {
        if (!knownFolders.current.has(path)) next.add(path);
      }
      knownFolders.current = new Set(allFolders);
      if (selectedPath) {
        for (const a of ancestorsOfPath(selectedPath)) next.add(a);
      }
      if (selectedFolder) {
        next.add(selectedFolder);
        for (const a of ancestorsOfPath(selectedFolder)) next.add(a);
      }
      return next;
    });
  }, [allFolders, selectedFolder, selectedPath]);

  function toggle(path: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  const rootSelected = selectedFolder === "" && !selectedPath;
  const catalogSelected = selectedPath === CATALOG_FILE_PATH;
  const catalogPad = 10 + 16;

  return (
    <nav
      aria-label="Organisation skill files"
      className="overflow-hidden rounded-lg border border-border bg-card"
    >
      <div className="border-b border-border bg-muted/40 px-3 py-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Tenant skills
        </p>
      </div>
      <div className="max-h-[min(28rem,55vh)] overflow-auto p-1.5" role="tree">
        <button
          type="button"
          role="treeitem"
          className={cn(
            ROW,
            "mb-0.5 gap-1.5 px-2",
            rootSelected
              ? "bg-primary/15 text-foreground"
              : "text-foreground/90 hover:bg-muted/70",
          )}
          onClick={() => onSelectFolder("")}
        >
          <FolderOpen className="h-4 w-4 shrink-0 text-amber-600" />
          <span className="truncate">skills</span>
        </button>

        <ul className="m-0 list-none p-0" role="group">
          <li className="relative" role="treeitem">
            <span
              aria-hidden
              className={cn(
                "pointer-events-none absolute top-0 w-px bg-border",
                nodes.length ? "bottom-0" : "h-[14px]",
              )}
              style={{ left: catalogPad - 8 }}
            />
            <button
              type="button"
              title="Tenant skill catalog index"
              className={cn(
                ROW,
                "gap-1.5",
                catalogSelected
                  ? "bg-primary/15 font-medium text-foreground"
                  : "text-foreground/85 hover:bg-muted/70",
              )}
              style={{ paddingLeft: catalogPad + 20 }}
              onClick={onSelectCatalog}
            >
              <FileText className="h-4 w-4 shrink-0 text-amber-700" />
              <span className="truncate">{CATALOG_FILE_PATH}</span>
            </button>
          </li>
        </ul>

        {!nodes.length ? (
          <p className="px-2 py-3 font-mono text-[12px] text-muted-foreground">
            No skill folders or `.md` files yet.
          </p>
        ) : (
          <TreeBranch
            nodes={nodes}
            depth={1}
            folderPath=""
            expanded={expanded}
            selectedFolder={selectedFolder}
            selectedPath={selectedPath}
            onToggle={toggle}
            onSelectFolder={onSelectFolder}
            onSelectSkill={onSelectSkill}
          />
        )}
      </div>
    </nav>
  );
}
