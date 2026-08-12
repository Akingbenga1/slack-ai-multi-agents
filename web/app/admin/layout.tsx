import { AdminNav } from "@/components/AdminNav";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <div
        style={{
          padding: "1.25rem 2rem 0",
          fontFamily: "system-ui, sans-serif",
          maxWidth: 960,
        }}
      >
        <AdminNav />
      </div>
      {children}
    </>
  );
}
