- [command](#command)
- [goal](#goal)

## command

Configure OpenCode's Penpot MCP connection in the base Docker image using `/home/container/.config/opencode/opencode.json` and a fixed, self-hosted local MCP URL. Confirm the actual MCP endpoint before setting the URL. Preserve existing OpenCode settings and ensure the container user owns the configuration. Do not bake keys, tokens, or credentials into the image; supply any required secrets at runtime.

## goal

Provide a container-user-owned OpenCode configuration in the base image that connects to the confirmed self-hosted Penpot MCP endpoint, preserves existing settings, and keeps any required credentials outside the image for runtime injection.
