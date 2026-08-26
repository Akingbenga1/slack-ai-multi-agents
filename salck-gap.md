**Verdict:** Slack routing and posting work. Remaining gaps are tool/MCP wiring and missing RAG evidence plumbing.

- **MCP server is still an empty FastMCP shell.** If a tool is registered as `kind=mcp`, execution will fail until tools are registered on that server (or tools use another kind).
- **Empty Qdrant means no useful retrieval.** The agent may still reply, but answers will not be grounded in your data.
- **Tool failures mark the run as failed.** Delivery may still post, but with error text or hedge=true.
- `retrieved_chunks` **is never filled in the Slack path.** Citation/formatting cannot show RAG evidence from the new facade yet.
- **Advice-only or halt-only plans can succeed without real tool work.** That can look like success while grounded Q&A still fails when tools are missing or broken.
