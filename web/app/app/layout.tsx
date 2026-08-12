import { OrgNav } from "@/components/OrgNav";

export default function OrgAppLayout({
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
          maxWidth: 800,
        }}
      >
        <OrgNav />
      </div>
      {children}
    </>
  );
}
