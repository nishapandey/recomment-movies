runnable Python + FastAPI project that demonstrates an agentic architecture (using MCP, A2A and ACP concepts) that (1) recommends movies and (2) tells you where to watch them (streaming / rent / buy)


A2A (Agent-to-Agent): a lightweight in-process AgentBus that routes messages between named agents (UserIntentAgent, RecommenderAgent, AvailabilityAgent, Orchestrator). This demonstrates agent-to-agent task delegation and message passing. 
Akka

MCP (Model Context Protocol): used as the tool integration layer — a MCPClient wraps external APIs (TMDb). Agents call MCPClient using a small, consistent JSON "tool call" format. MCP standardizes tool access. 
InfoWorld

ACP (Agent Communication Protocol): we use a simple structured message format (intent, context, metadata) for negotiation/clarity between agents (useful if agents later run across processes). It’s a small structured schema in code.

How to run: add your_tmdb_api_key, valid username in the sh file, run startup.sh  file