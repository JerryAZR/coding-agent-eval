"""Example pi agent adapter.

The built-in PiOneShotClient (registered as agent_mode="pi") is sufficient
for most use cases.  This file is a stub you can customize if you need:

- Different command-line flags
- Pre/post-processing of prompts
- Custom session management

To register a custom client, subclass AgentClient and use the
@register_client decorator:

    from cae.agent_client import AgentClient, TurnResult, register_client

    @register_client("pi-custom")
    class MyPiClient(AgentClient):
        ...

Then run with --agent-mode pi-custom.
"""

# Built-in pi client is already registered; no need to re-register here.
# from cae.agent_client import register_client, PiOneShotClient
