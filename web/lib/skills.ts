/** Tenant skills client (`/skills`) — catalog tree + markdown skills. */

import { ApiError, apiClient } from "@/lib/api";

/** Rel path of the tenant catalog index file (shown in the skills file tree). */
export const CATALOG_FILE_PATH = "catalog.json";

export type SkillCatalogNode =
  | {
      type: "folder";
      id?: string;
      name: string;
      children?: SkillCatalogNode[];
    }
  | {
      type: "skill";
      id?: string;
      name: string;
      description?: string;
      path: string;
    };

export type SkillCatalog = {
  version?: number;
  children: SkillCatalogNode[];
};

export type SkillRecord = {
  name: string;
  description: string;
  path: string;
  content: string;
};

/** Flat folder paths from a catalog tree ("" = skills root). */
export function listSkillFolderPaths(
  nodes: SkillCatalogNode[],
  parent = "",
  out: string[] = [""],
): string[] {
  for (const node of nodes) {
    if (node.type !== "folder") continue;
    const path = parent ? `${parent}/${node.name}` : node.name;
    out.push(path);
    listSkillFolderPaths(node.children ?? [], path, out);
  }
  return out;
}

export function skillParentFolder(path: string): string {
  const parts = path.split("/").filter(Boolean);
  if (parts.length <= 1) return "";
  return parts.slice(0, -1).join("/");
}

export function skillBasename(path: string): string {
  const base = path.split("/").pop() || path;
  return base.endsWith(".md") ? base : `${base}.md`;
}

export function skillsApiErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Sign in to manage skills.";
    if (err.status === 403) return err.message || "Not allowed.";
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

/** Strip YAML front matter so the editor edits the body only. */
export function skillBodyFromMarkdown(content: string): string {
  const match = /^(---\s*\n[\s\S]*?\n---\s*\n?)([\s\S]*)$/.exec(content);
  if (match) return match[2] ?? "";
  return content;
}

export async function getSkillCatalog(
  accessToken: string,
  tenantId: string | null,
): Promise<SkillCatalog> {
  const res = await apiClient.get<{ catalog: SkillCatalog }>("/skills/catalog", {
    accessToken,
    clientId: tenantId,
  });
  return res?.catalog ?? { children: [] };
}

export async function createSkillFolder(
  accessToken: string,
  tenantId: string | null,
  input: { name: string; parent_path?: string },
): Promise<SkillCatalog> {
  const res = await apiClient.post<{ catalog: SkillCatalog }>("/skills/folders", {
    accessToken,
    clientId: tenantId,
    json: {
      name: input.name.trim(),
      parent_path: input.parent_path ?? "",
    },
  });
  return res?.catalog ?? { children: [] };
}

export async function deleteSkillFolder(
  accessToken: string,
  tenantId: string | null,
  folderPath: string,
  mode: "delete" | "relocate" = "delete",
): Promise<SkillCatalog> {
  const q = encodeURIComponent(folderPath);
  const children = encodeURIComponent(mode);
  const res = await apiClient.delete<{ catalog: SkillCatalog }>(
    `/skills/folders?folder_path=${q}&children=${children}`,
    { accessToken, clientId: tenantId },
  );
  return res?.catalog ?? { children: [] };
}

export async function createSkill(
  accessToken: string,
  tenantId: string | null,
  input: {
    name: string;
    description?: string;
    body?: string;
    folder_path?: string;
  },
): Promise<SkillRecord> {
  const res = await apiClient.post<SkillRecord>("/skills", {
    accessToken,
    clientId: tenantId,
    json: {
      name: input.name.trim(),
      description: (input.description || "").trim(),
      body: input.body || "",
      folder_path: input.folder_path ?? "",
    },
  });
  if (!res) throw new Error("Empty skill create response");
  return res;
}

export async function getSkill(
  accessToken: string,
  tenantId: string | null,
  path: string,
): Promise<SkillRecord> {
  const q = encodeURIComponent(path);
  const res = await apiClient.get<SkillRecord>(`/skills/file?path=${q}`, {
    accessToken,
    clientId: tenantId,
  });
  if (!res) throw new Error("Empty skill response");
  return res;
}

export async function updateSkill(
  accessToken: string,
  tenantId: string | null,
  path: string,
  input: {
    name?: string;
    description?: string;
    body?: string;
    dest_folder_path?: string;
    new_filename?: string;
  },
): Promise<SkillRecord> {
  const q = encodeURIComponent(path);
  const res = await apiClient.patch<SkillRecord>(`/skills/file?path=${q}`, {
    accessToken,
    clientId: tenantId,
    json: {
      name: input.name,
      description: input.description,
      body: input.body,
      dest_folder_path: input.dest_folder_path,
      new_filename: input.new_filename,
    },
  });
  if (!res) throw new Error("Empty skill update response");
  return res;
}

export async function deleteSkill(
  accessToken: string,
  tenantId: string | null,
  path: string,
): Promise<SkillCatalog> {
  const q = encodeURIComponent(path);
  const res = await apiClient.delete<{ catalog: SkillCatalog }>(
    `/skills/file?path=${q}`,
    { accessToken, clientId: tenantId },
  );
  return res?.catalog ?? { children: [] };
}
