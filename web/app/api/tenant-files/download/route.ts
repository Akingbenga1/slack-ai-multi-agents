import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { apiAuthHeaders, getApiBaseUrl } from "@/lib/api";

export async function GET(request: Request) {
  const session = await getServerSession(authOptions);
  const accessToken = session?.accessToken;
  if (!accessToken) {
    return new Response("Unauthorized", { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const key = searchParams.get("key")?.trim();
  if (!key) {
    return new Response("key is required", { status: 400 });
  }

  const tenantId =
    searchParams.get("tenantId")?.trim() || session.user?.tenantId || null;
  const filename =
    searchParams.get("filename")?.trim() || key.split("/").pop() || "download";

  const upstream = await fetch(
    `${getApiBaseUrl()}/tenant-files/content?key=${encodeURIComponent(key)}`,
    { headers: apiAuthHeaders(accessToken, tenantId) },
  );

  if (!upstream.ok) {
    const detail = await upstream.text();
    return new Response(detail || upstream.statusText, { status: upstream.status });
  }

  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) {
    headers.set("Content-Type", contentType);
  }
  const safeName = filename.replace(/[\r\n"]/g, "");
  headers.set(
    "Content-Disposition",
    upstream.headers.get("content-disposition") ||
      `attachment; filename="${safeName}"; filename*=UTF-8''${encodeURIComponent(filename)}`,
  );

  return new Response(upstream.body, { status: 200, headers });
}
