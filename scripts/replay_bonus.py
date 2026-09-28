"""Replay observed bonus evidence locally; coach/grader still decides points."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.config import get_red_model, get_red_provider
from agents.agent import create_red_agent_default
from agents.guards_agent import create_red_agent_advance
from attacks.attacks import run_attacks


async def replay(evidence):
    data = json.loads(evidence.read_text(encoding="utf-8"))
    if (data["llm_provider"], data["llm_model"]) != (get_red_provider(), get_red_model()):
        raise ValueError("Replay must use the provider/model recorded in the evidence")
    bonus = data.get("selected_bonus")
    if bonus not in {"B1", "B2"}:
        raise ValueError("No observed successful attack to replay yet")
    field = "guards_attacks" if bonus == "B2" else "unsafe_attacks"
    attack = next(r for r in data[field] if r.get("leaked") and not r.get("error"))
    factory = create_red_agent_advance if bonus == "B2" else create_red_agent_default
    agent, runner = factory()
    results = await run_attacks(
        agent, runner, prompts=[attack],
        target_name="red_advance" if bonus == "B2" else "red_default",
        output_path=evidence.parent / "bonus_replay.json",
    )
    if not results[0]["leaked"] or results[0].get("error"):
        raise RuntimeError("Local replay did not reproduce the leak; no bonus claimed")
    print(f"{bonus} reproduced locally. Coach/grader replay determines the awarded points.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=ROOT / "outputs" / "attack_results.json")
    asyncio.run(replay(parser.parse_args().evidence))
