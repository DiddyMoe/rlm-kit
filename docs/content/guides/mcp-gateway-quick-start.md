# MCP gateway quick start

Minimal steps to run the RLM MCP Gateway and use it from your IDE.

---

## Local (stdio) mode

1. Add the MCP server to `.cursor/mcp.json` or `.vscode/settings.json` (see [Quick start](../getting-started/quick-start.md)).
2. Restart the IDE.
3. In chat, ask: “What RLM tools are available?”

The gateway runs in the same workspace; agents still use MCP tools for repo access.

---

## Remote (HTTP) mode

1. **Start the gateway** (on the host that has the repo):

   ```bash
   python scripts/rlm_mcp_gateway.py \
     --mode http \
     --host 0.0.0.0 \
     --port 8080 \
     --repo-path /repo/rlm-kit \
     --api-key your-secret-api-key
   ```

2. **Thin workspace** (on the IDE host):

   ```bash
   python scripts/setup_thin_workspace.py --output-dir ~/rlm-kit-thin
   ```

3. **MCP config** in the thin workspace (e.g. `.cursor/mcp.json`):

   ```json
   {
     "mcpServers": {
       "rlm-gateway": {
         "command": "curl",
         "args": [
           "-X", "POST",
           "https://your-gateway-host:8080/mcp",
           "-H", "Authorization: Bearer ${RLM_GATEWAY_API_KEY}",
           "-H", "Content-Type: application/json",
           "--data-binary", "@-"
         ],
         "env": {
           "RLM_GATEWAY_API_KEY": "${env:RLM_GATEWAY_API_KEY}"
         }
       }
     }
   }
   ```

4. Set `RLM_GATEWAY_API_KEY` and open the thin workspace in the IDE.

See [Remote isolation](remote-isolation.md) and [Installation](../getting-started/installation.md). for full deployment options.
