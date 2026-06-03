## High-Level Architecture

### Components

| Component | Role | Lifetime |
|---|---|---|
| **Manager** | Orchestrator. Owns the lifecycle. Spawns worker and tester. Reads results. Injects new requirements. | One per benchmark run. |
| **Worker** | Agent's environment. Persistent. Network on. The agent writes code, builds, runs self-tests here. | One per task group. Survives across phases. |
| **Tester** | Evaluation environment. Ephemeral. Network off. Receives the artifact + hidden tests. Reports pass/fail. | One per evaluation event. Fresh spawn every time. |
| **Shared Volume** | The only channel between worker and the outside world. Holds artifacts, task specs, and communication state. | One per task group. Destroyed with the group. |

### Boundaries

- **Manager ↔ Worker**: Indirect. The manager writes to the volume; the worker (or its tool wrapper) reads. The worker writes to the volume; the manager polls and reacts. No direct socket, exec, or API call.
- **Worker ↔ Tester**: None. The tester never talks to the worker. The tester only sees a snapshot of the volume mounted read-only.
- **Tester ↔ Manager**: Direct. The tester reports to the manager via stdout/exit code. The manager interprets this and decides what to tell the worker next.

### Lifecycle

1. **Create**: Manager creates a fresh volume and a fresh worker container for a new task group.
2. **Inject**: Manager places the initial task specification into the volume.
3. **Work**: The agent inside the worker builds the system. It may write to the volume at any time.
4. **Signal**: When the agent (or its tool) decides it is ready, it writes a submission marker into the volume.
5. **Evaluate**: Manager detects the marker, spawns a tester with the volume mounted read-only, and runs hidden tests against the artifact.
6. **Report**: Tester returns results to the manager. Manager writes feedback and, if applicable, updated requirements into the volume.
7. **Evolve or Close**: If the task group has more phases, the worker continues with the new requirements. If done, the manager destroys the worker and volume.

### What Is Explicitly Not Decided Here

- The exact format of task specs, submission markers, or feedback messages.
- Whether the agent natively understands the protocol or uses a wrapper tool.
- Polling strategy (inotify, interval, or other).
- How hidden tests are packaged or delivered to the tester.
- Whether the tester runs locally inside the container or delegates to another process.
- Scoring oracle implementation.

These are implementation details for the coding agent to resolve.