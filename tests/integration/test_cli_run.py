import json

from agentguard.cli import main


def test_cli_runs_echo_scenario_and_writes_jsonl(tmp_path, monkeypatch, capsys) -> None:
    output = tmp_path / "run.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        ["agentguard", "run", "--output", str(output)],
    )

    assert main() == 0
    captured = capsys.readouterr().out
    assert "status: completed" in captured
    assert "stop_reason: completed" in captured

    events = [json.loads(line) for line in output.read_text().splitlines()]
    assert events[0]["event_type"] == "run_started"
    assert events[-1]["event_type"] == "run_finished"
