# Task 14.1 — Wire mention/DM → LangGraph

## Steps

- [x] Replace Slack echo text with `run_agent` grounded answer
- [x] Use install-store bot token (`get_bot_token`) for `chat.postMessage`
- [x] Reply in-thread for `@mentions`; DMs stay top-level
- [x] Stable `conversation_id` for checkpointer (channel + thread root)
- [x] Ack Slack quickly; run agent + post in background (avoid retry storms)
- [x] Keep usage `slack_mention` + skip `X-Slack-Retry-Num`
- [x] Light tests + docs update

## Acceptance criteria

- [x] Mention/DM path invokes LangGraph for the install's `client_id`
- [x] Reply posted via install-store token (in-thread for mentions)
- [x] No more `Echo:` placeholder on the live path
