import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { AgentTracePanel } from "@/components/AgentTracePanel";

export default async function AdminAgentTracePage() {
  const session = await getServerSession(authOptions);

  return (
    <>
      <PageHeader
        title="Agent trace"
        description="Submit a request, inspect orchestrator prompts and plan steps, then read the executor final answer."
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Agent trace" },
        ]}
        className="mb-8"
      />
      <AgentTracePanel accessToken={session?.accessToken ?? null} />
    </>
  );
}
