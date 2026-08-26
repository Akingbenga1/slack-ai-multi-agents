/** Match api.app.admin.provision.slug_from_name / normalize_slug preview. */
export function slugFromName(name: string): string {
  let slug = (name || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  slug = slug.slice(0, 64).replace(/^-+|-+$/g, "");
  return slug;
}
