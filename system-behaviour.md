# System behaviour — tool discovery

1. When an operator opens discovery status, the system reports whether CLI and MCP upstream URLs are configured without running a search.
2. When an operator searches for CLI tools with a query, the system calls the CLI discovery URL from env and returns matching candidate tools.
3. When an operator searches for MCP tools with a query, the system calls the MCP discovery URL from env and returns matching candidate tools.
4. When the env URL for the requested tool kind is missing, the system rejects the search with a clear configuration error and does not call any upstream service.
5. When discovery returns candidates, the system does not attach them to any tenant and leaves registration to a separate tools create step.
