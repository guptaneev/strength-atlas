---
purpose: Local engineering reference for Browser Use Cloud SDK usage in this repository
status: snapshot
source: user-provided context
---

# Browser Use Cloud SDK Reference

This document is a local reference snapshot for Browser Use Cloud usage in this repository. It may drift from upstream Browser Use documentation over time.

## Package overview

Both APIs are in the same package, `browser-use-sdk`:

- BU Agent API (v3 Experimental) - `browser-use-sdk/v3`
- Browser Use Cloud v2 - `browser-use-sdk`

## Install and setup

### Install

- Python: `pip install browser-use-sdk`
- TypeScript: `npm install browser-use-sdk`

### Setup

Set `BROWSER_USE_API_KEY` as an environment variable, or pass `api_key` and `apiKey` to the constructor.

Get a key at [cloud.browser-use.com/settings?tab=api-keys](https://cloud.browser-use.com/settings?tab=api-keys)

## BU Agent API (v3 Experimental)

### Python SDK (v3)

```python
from browser_use_sdk.v3 import AsyncBrowserUse, FileUploadItem
from pydantic import BaseModel

client = AsyncBrowserUse()

# Run a task (await for result)
result = await client.run("Find the top HN post")  # -> SessionResult[str]
print(result.output)   # str
print(result.id)       # session UUID
print(result.status)   # BuAgentSessionStatus (e.g. idle, stopped)

# Structured output
class Product(BaseModel):
    name: str
    price: float

result = await client.run("Get product info from amazon.com/dp/...", output_schema=Product)
print(result.output)  # Product(name=..., price=...)
```

#### Constructor

```python
# Async client (recommended)
client = AsyncBrowserUse(api_key="...", base_url="...", timeout=30.0)

# Sync client (blocking, no async/await needed)
from browser_use_sdk.v3 import BrowserUse
client = BrowserUse(api_key="...", base_url="...", timeout=30.0)

# Context manager (sync only)
with BrowserUse() as client:
    result = client.run("Find the top HN post")
```

- `api_key: str` - default: `BROWSER_USE_API_KEY` env var
- `base_url: str` - default: `https://api.browser-use.com/api/v3`
- `timeout: float` - HTTP request timeout in seconds, default `30.0`. This is not the polling timeout.

#### `run()` parameters (v3)

All optional keyword arguments:

- `model: str` - `"bu-mini"` by default or `"bu-max"` for a more capable model
- `output_schema: type[BaseModel]` - Pydantic model for structured output, alias: `schema`
- `session_id: str` - reuse an existing session
- `keep_alive: bool` - keep session idle after task, default `False`
- `max_cost_usd: float` - cost cap in USD
- `profile_id: str` - persistent browser profile for cookies and local storage
- `proxy_country_code: str` - residential proxy country such as `"us"` or `"de"`

`run()` returns an `AsyncSessionRun` for async clients or `SessionResult` for sync clients.

- `AsyncSessionRun` is awaitable. After `await`, it gives a `SessionResult`.
- It also has `.session_id`, `.result`, and `.output` properties.
- Polling defaults: interval `2` seconds, timeout `300` seconds.
- It raises `TimeoutError` if polling exceeds the timeout.
- Terminal statuses: `idle`, `stopped`, `timed_out`, `error`

#### `SessionResult` fields

- `output` - typed output, either `str` or a Pydantic model
- `id` - session UUID
- `status` - `created`, `idle`, `running`, `stopped`, `timed_out`, or `error`
- `model` - `bu-mini` or `bu-max`
- `title` - auto-generated title or `None`
- `live_url` - real-time browser monitoring URL
- `profile_id`, `proxy_country_code`, `max_cost_usd` - echo of request params
- `total_input_tokens`, `total_output_tokens` - token usage
- `llm_cost_usd`, `proxy_cost_usd`, `proxy_used_mb`, `total_cost_usd` - cost breakdown as strings
- `created_at`, `updated_at` - timestamps

#### Resources (v3)

```python
# Sessions - reusable browser environments
session = await client.sessions.create(proxy_country_code="us")
result1 = await client.run("Log into example.com", session_id=str(session.id), keep_alive=True)
result2 = await client.run("Now click settings", session_id=str(session.id))
await client.sessions.stop(str(session.id))

# Sessions with profiles - persistent login state
session = await client.sessions.create(profile_id="your-profile-uuid")

# Files - upload to a session before running a task
upload_resp = await client.sessions.upload_files(
    str(session.id),
    files=[FileUploadItem(name="data.csv", content_type="text/csv")],
)
# PUT each file to upload_resp.files[i].upload_url with matching Content-Type header
# Each FileUploadResponseItem has: .name, .upload_url, .path (S3-relative)

# Files - list/download from session workspace
file_list = await client.sessions.files(
    str(session.id),
    include_urls=True,
    prefix="outputs/",
    limit=50,
    cursor=None,
)
# Each FileInfo has: .path, .size, .last_modified, .url
# FileListResponse has: .files, .next_cursor, .has_more

# Session management
sessions_list = await client.sessions.list(page=1, page_size=20)
details = await client.sessions.get(str(session.id))
await client.sessions.stop(str(session.id), strategy="task")
await client.sessions.stop(str(session.id), strategy="session")
await client.sessions.delete(str(session.id))

# Cost tracking
print(result.total_cost_usd, result.llm_cost_usd, result.proxy_cost_usd)
print(result.total_input_tokens, result.total_output_tokens)

# Cleanup
await client.close()
```

#### `sessions.create()` parameters (v3)

Creates a session and optionally dispatches a task. All parameters are optional:

- `task: str` - omit to create an idle session
- `model: str` - `"bu-mini"` by default or `"bu-max"`
- `session_id: str` - dispatch to an existing idle session instead of creating a new one
- `keep_alive: bool` - keep session alive after task, default `False`
- `max_cost_usd: float` - cost cap in USD
- `profile_id: str` - browser profile to load
- `proxy_country_code: str` - residential proxy country
- `output_schema: dict` - raw JSON Schema for structured output; prefer `run()` with Pydantic or Zod

#### `FileUploadItem` fields

- `name: str` - required filename, such as `"data.csv"`
- `content_type: str` - MIME type such as `"text/csv"`, default `"application/octet-stream"`

#### Error handling (v3)

```python
from browser_use_sdk.v3 import AsyncBrowserUse, BrowserUseError

try:
    result = await client.run("Do something")
except TimeoutError:
    print("SDK polling timed out (5 min default)")
except BrowserUseError as e:
    print(f"API error: {e}")
```

### TypeScript SDK (v3)

```typescript
import { BrowserUse } from "browser-use-sdk/v3";
import { readFileSync } from "fs";
import { z } from "zod";

const client = new BrowserUse();

const result = await client.run("Find the top HN post");
console.log(result.output);

// Structured output (Zod)
const Product = z.object({ name: z.string(), price: z.number() });
const typed = await client.run("Get product info", { schema: Product });

// Resources: client.sessions
const session = await client.sessions.create({ proxyCountryCode: "us" });
await client.run("Log in", { sessionId: session.id, keepAlive: true });
await client.run("Click settings", { sessionId: session.id });
await client.sessions.stop(session.id);

// File upload
const upload = await client.sessions.uploadFiles(session.id, {
  files: [{ name: "data.csv", contentType: "text/csv" }],
});
await fetch(upload.files[0].uploadUrl, { method: "PUT", body: readFileSync("data.csv") });

// File listing
const files = await client.sessions.files(session.id, {
  includeUrls: true, prefix: "outputs/", limit: 50, cursor: null,
});

// Session management
const list = await client.sessions.list({ page: 1, page_size: 20 });
const details = await client.sessions.get(session.id);
await client.sessions.stop(session.id, { strategy: "task" });
await client.sessions.delete(session.id);
```

#### Constructor options (v3)

```typescript
const client = new BrowserUse({
  apiKey: "...",
  baseUrl: "...",
  maxRetries: 2,
  timeout: 30_000,
});
```

- `apiKey` - default: `process.env.BROWSER_USE_API_KEY`
- `baseUrl` - default: `https://api.browser-use.com/api/v3`
- `maxRetries` - retry count for `429` errors
- `timeout` - HTTP request timeout in milliseconds, not the polling timeout

#### `run()` options (v3)

- `model` - `"bu-mini"` by default or `"bu-max"`
- `schema` - Zod schema for structured output
- `sessionId` - reuse an existing session
- `keepAlive` - keep session alive after task, default `false`
- `maxCostUsd` - cost cap in USD
- `profileId` - persistent browser profile UUID
- `proxyCountryCode` - residential proxy country code
- `outputSchema` - raw JSON Schema object; prefer `schema` with Zod
- `timeout` - max polling time in ms, default `300_000`
- `interval` - polling interval in ms, default `2_000`

`run()` returns a `SessionRun<T>`, which is awaitable. After `await`, it yields a `SessionResult<T>`. It also has `.sessionId` and `.result` properties.

## Key concepts (v3)

- Task: text prompt to agent execution to returned output
- Session: stateful browser sandbox
- Profile: persistent browser state that survives across sessions
- Profile Sync: upload local cookies to cloud with `curl -fsSL https://browser-use.com/profile.sh | sh`
- Proxies: set `proxy_country_code` on a session or `run()`
- Stealth: enabled by default
- Models: `bu-mini` and `bu-max`
- Cost control: set `max_cost_usd` and inspect `total_cost_usd`
- Autonomous execution: the agent decides how many steps to take
- `keep_alive`: when `true`, the session stays idle for follow-up tasks
- Live URL: every session has a `live_url`
- File I/O: upload files before a task and download results from the workspace after
- Stop strategies: `strategy="session"` destroys the sandbox, `strategy="task"` stops only the task
- Integrations: the agent can discover and use third-party service integrations automatically

## Browser Use Cloud v2 SDK

### Python SDK (v2)

```python
from browser_use_sdk import AsyncBrowserUse
from pydantic import BaseModel

client = AsyncBrowserUse()

# Run a task (await for result)
result = await client.run("Find the top HN post")  # -> TaskResult[str]
print(result.output)   # str
print(result.id)       # task ID
print(result.status)   # "finished"

# Structured output
class Product(BaseModel):
    name: str
    price: float

result = await client.run("Get product info from amazon.com/dp/...", output_schema=Product)
print(result.output)  # Product(name=..., price=...)

# Stream steps
async for step in client.run("Go to google.com and search for 'browser use'"):
    print(f"[{step.number}] {step.next_goal} - {step.url}")
```

#### `run()` parameters (v2)

All optional keyword arguments:

- `session_id: str` - reuse an existing session
- `llm: str` - model override, default: Browser Use LLM
- `start_url: str` - initial page URL
- `max_steps: int` - max agent steps, default `100`
- `output_schema: type[BaseModel]` - Pydantic model for structured output, alias: `schema`
- `secrets: dict[str, str]` - domain-scoped credentials
- `allowed_domains: list[str]` - restrict the agent to these domains
- `session_settings: SessionSettings` - proxy, profile, and browser config
- `flash_mode: bool` - faster but less careful
- `thinking: bool` - extended reasoning
- `vision: bool | str` - vision or screenshot mode
- `highlight_elements: bool` - highlight interactive elements
- `system_prompt_extension: str` - append to the system prompt
- `judge: bool` - enable quality judge
- `skill_ids: list[str]` - skills to use
- `op_vault_id: str` - 1Password vault ID for 2FA and credentials
- `metadata: dict[str, str]` - custom metadata

#### Resources (v2)

```python
# Sessions - reusable browser environments
session = await client.sessions.create(proxy_country_code="us")
result1 = await client.run("Log into example.com", session_id=session.id)
result2 = await client.run("Now click settings", session_id=session.id)
await client.sessions.stop(session.id)

# Profiles - persistent login state
profile = await client.profiles.create(name="my-profile")
session = await client.sessions.create(profile_id=profile.id)

# Files
url_info = await client.files.session_url(
    session_id,
    file_name="input.pdf",
    content_type="application/pdf",
    size_bytes=1024,
)
output = await client.files.task_output(task_id, file_id)

# Browser API - direct CDP access
browser = await client.browsers.create(proxy_country_code="de")
# Connect via browser.cdp_url with Playwright/Puppeteer/Selenium

# Skills - turn websites into APIs
skill = await client.skills.create(goal="Extract product data from Amazon", agent_prompt="...")
result = await client.skills.execute(skill.id, parameters={"url": "..."})

# Marketplace
skills = await client.marketplace.list()
result = await client.marketplace.execute(skill_id, parameters={...})

# Billing
account = await client.billing.account()
```

### TypeScript SDK (v2)

```typescript
import { BrowserUse } from "browser-use-sdk";
import { z } from "zod";

const client = new BrowserUse();

const result = await client.run("Find the top HN post");
console.log(result.output);

// Structured output (Zod)
const Product = z.object({ name: z.string(), price: z.number() });
const typed = await client.run("Get product info", { schema: Product });

// Stream steps
for await (const step of client.run("Go to google.com")) {
  console.log(`[${step.number}] ${step.nextGoal}`);
}
```

#### `run()` options (v2)

- `sessionId`
- `llm`
- `startUrl`
- `maxSteps`
- `schema` for Zod
- `secrets`
- `allowedDomains`
- `sessionSettings`
- `flashMode`
- `thinking`
- `vision`
- `highlightElements`
- `systemPromptExtension`
- `judge`
- `skillIds`
- `opVaultId`
- `timeout` in ms, default `300000`
- `interval` in ms, default `2000`

## Key concepts (v2)

- Task: text prompt to agent execution to returned output
- Session: stateful browser environment
- Profile: persistent browser state across sessions
- Profile Sync: upload local cookies to cloud with `curl -fsSL https://browser-use.com/profile.sh | sh`
- Proxies: set `proxy_country_code` on sessions
- Stealth: enabled by default
- Browser Use LLM: the default model for browser tasks
- Vision: agent can take screenshots
- 1Password: auto-fill passwords and TOTP codes with `op_vault_id`
