import json
import os
from pathlib import Path

from cae.agent_client import AgentClient, TurnResult, register_client


@register_client("probe")
class ProbeClient(AgentClient):
    def __init__(self, **kwargs):
        pass

    def run_turn(self, prompt, env, cwd, system_prompt_append=""):
        result = {
            "home": os.environ.get("HOME"),
            "probe_var": os.environ.get("CAE_PROBE_VAR"),
            "startup_ran": Path.home().joinpath(".startup-ran").exists(),
            "venv_active": "VIRTUAL_ENV" in os.environ,
            "pythonpath_has_agent": any(
                "probe-template" in p or "agent" in p
                for p in os.environ.get("PYTHONPATH", "").split(":")
            ),
        }
        (cwd / "output.txt").write_text(json.dumps(result))
        return TurnResult(
            success=True,
            output=prompt + "\n<CAE_PHASE_COMPLETE/>"
        )
