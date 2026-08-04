# Agent Engine runtime dependencies

Vertex Agent Engine installs packages from **`clintrace_agent/requirements.txt`**.

```bash
make deploy-agent
# copy AGENT_ENGINE_RESOURCE_ID from deploy output into .env
```

Deploy defaults to **source-file** mode (ADK/doc inline tarball). It stages a
filtered copy of `clintrace_agent/` that excludes `.env`, `.adk/`, and
`__pycache__/`. Use `--deploy-mode=pickle` only if you need the agent-object /
`package_spec` path.

Build logs should show requirements installed from
`./clintrace_agent/requirements.txt`.
