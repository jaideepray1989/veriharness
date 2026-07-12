"""Isolated TextWorld bridge run by the dedicated TextWorld Python environment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# The bridge lives beside the harness adapter named textworld.py. Remove that
# directory before importing the installed TextWorld package.
_BRIDGE_DIR = Path(__file__).resolve().parent
sys.path = [item for item in sys.path if Path(item or ".").resolve() != _BRIDGE_DIR]


def _infos() -> Any:
    from textworld import EnvInfos

    return EnvInfos(
        description=True,
        inventory=True,
        objective=True,
        admissible_commands=True,
        won=True,
        lost=True,
        max_score=True,
    )


def generate_game(payload: Dict[str, Any]) -> Dict[str, Any]:
    import textworld

    game_path = Path(str(payload["game_path"])).expanduser().resolve()
    game_path.parent.mkdir(parents=True, exist_ok=True)
    if not game_path.exists():
        options = textworld.GameOptions()
        options.seeds = int(payload["game_seed"])
        options.nb_rooms = int(payload.get("world_size", 3))
        options.nb_objects = int(payload.get("object_count", 4))
        options.quest_length = int(payload.get("quest_length", 2))
        options.path = str(game_path)
        textworld.make(options)

    env = textworld.start(str(game_path), _infos())
    try:
        state = env.reset()
        return {
            "game_path": str(game_path),
            "game_seed": int(payload["game_seed"]),
            "objective": str(getattr(state, "objective", "")),
            "description": str(getattr(state, "description", "")),
            "inventory": str(getattr(state, "inventory", "")),
            "max_score": int(getattr(state, "max_score", 1) or 1),
        }
    finally:
        env.close()


def evaluate_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    import textworld

    game_path = Path(str(payload["game_path"])).expanduser().resolve()
    commands = payload.get("commands", [])
    max_steps = int(payload.get("max_steps", 4))
    if not isinstance(commands, list) or not all(isinstance(command, str) for command in commands):
        return _failure(
            "action_plan_invalid",
            "The action plan must be a JSON list of command strings.",
            location="LeafOutput.answer.commands",
            expected="a list of TextWorld command strings",
            observed=commands,
        )
    if not commands:
        return _failure(
            "command_missing",
            "The action plan did not include a command.",
            location="LeafOutput.answer.commands[0]",
            expected="at least one command",
            observed=commands,
        )
    if len(commands) > max_steps:
        return _failure(
            "turn_budget_exceeded",
            f"The action plan has {len(commands)} commands but the episode budget is {max_steps}.",
            location="LeafOutput.answer.commands",
            expected=f"at most {max_steps} commands",
            observed=len(commands),
        )

    env = textworld.start(str(game_path), _infos())
    try:
        state = env.reset()
        trace: List[Dict[str, Any]] = []
        for index, raw_command in enumerate(commands):
            command = raw_command.strip()
            admissible = list(getattr(state, "admissible_commands", []) or [])
            if command not in admissible:
                return _failure(
                    "action_invalid",
                    f"Command {index} is not admissible in the current game state.",
                    location=f"LeafOutput.answer.commands[{index}]",
                    expected=admissible[:12],
                    observed=command,
                    trace=trace,
                    feedback=str(getattr(state, "feedback", ""))[-500:],
                )

            state, score, done = env.step(command)
            trace.append(
                {
                    "command": command,
                    "score": int(score),
                    "feedback": str(getattr(state, "feedback", ""))[-500:],
                }
            )
            if bool(getattr(state, "won", False)):
                return {
                    "passed": True,
                    "score": int(score),
                    "max_score": int(getattr(state, "max_score", 1) or 1),
                    "turns_executed": index + 1,
                    "trace": trace,
                }
            if done or bool(getattr(state, "lost", False)):
                return _failure(
                    "game_lost",
                    "The game ended before the objective was completed.",
                    location=f"LeafOutput.answer.commands[{index}]",
                    expected="a command sequence that completes the objective",
                    observed=command,
                    trace=trace,
                )

        return _failure(
            "quest_incomplete",
            "The submitted commands were valid but did not complete the objective.",
            location="LeafOutput.answer.commands",
            expected="a command sequence that completes the visible objective",
            observed=commands,
            trace=trace,
            feedback=str(getattr(state, "feedback", ""))[-500:],
        )
    finally:
        env.close()


def _failure(code: str, message: str, **details: Any) -> Dict[str, Any]:
    return {
        "passed": False,
        "failure": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", choices=["generate", "evaluate"], required=True)
    args = parser.parse_args()
    payload = json.loads(sys.stdin.read() or "{}")
    if args.operation == "generate":
        result = generate_game(payload)
    else:
        result = evaluate_plan(payload)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
