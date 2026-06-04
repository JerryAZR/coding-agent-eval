# Echo Agent Template

A minimal CAE agent template for testing. The echo agent writes the prompt to
`output.txt` and randomly appends the completion marker.

This template exists to prove that built-in agents are handled through the same
mechanism as custom agents: the framework discovers the agent by importing the
`agent/` package and checking what client was registered.
