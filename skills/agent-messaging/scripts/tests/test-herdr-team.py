#!/usr/bin/env python3
"""Exercise task dispatch with real sh/jq and a controlled Herdr CLI boundary."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "herdr-team.sh"
TARGET = "demo-cx"

HERDR_FIXTURE = r'''
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with open(os.environ["HERDR_TEST_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
config = json.loads(Path(os.environ["HERDR_TEST_CONFIG"]).read_text())
if args[:2] == ["agent", "get"]:
    sys.stdout.write(config["get_stdout"])
    sys.stderr.write(config.get("get_stderr", ""))
    get_calls = sum(
        json.loads(line)[:2] == ["agent", "get"]
        for line in Path(os.environ["HERDR_TEST_LOG"]).read_text().splitlines()
    )
    sys.exit(config.get("diagnostic_get_exit", config.get("get_exit", 0))
             if get_calls > 1 else config.get("get_exit", 0))
if args[:2] == ["agent", "prompt"]:
    sys.stdout.write(config["prompt_stdout"])
    sys.stderr.write(config.get("prompt_stderr", ""))
    sys.exit(config.get("prompt_exit", 0))
if args[:2] == ["agent", "read"]:
    sys.stdout.write("Worker pane output\n")
    sys.exit(0)
sys.stderr.write("Unexpected Herdr command: " + repr(args) + "\n")
sys.exit(90)
'''


def agent_response(status, **fields):
    return json.dumps({"result": {"agent": {"agent_status": status, **fields}}})


@unittest.skipUnless(shutil.which("jq"), "jq is required by herdr-team.sh")
class TaskDispatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="herdr-team-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        fixture = self.directory / "herdr"
        fixture.write_text(f"#!{sys.executable}\n" + HERDR_FIXTURE)
        fixture.chmod(0o755)
        self.config_path = self.directory / "config.json"
        self.log_path = self.directory / "calls.jsonl"
        self.environment = {
            **os.environ,
            "PATH": str(self.directory) + os.pathsep + os.environ["PATH"],
            "HERDR_ENV": "1",
            "HERDR_PANE_ID": "planner:p1",
            "HERDR_TEST_CONFIG": str(self.config_path),
            "HERDR_TEST_LOG": str(self.log_path),
        }
        self.message = (
            "Sửa lỗi nhận task: giữ nguyên tiếng Việt và 'dấu nháy'.\n"
            '"quoted"; $HOME; $(touch '
            + str(self.directory / "must-not-exist")
            + "); `printf injected`; \\literal & | > <"
        )

    def dispatch(self, command="send", timeout=None, **overrides):
        config = {
            "get_stdout": agent_response("idle", interactive_ready=True),
            "prompt_stdout": agent_response("working"),
            **overrides,
        }
        self.config_path.write_text(json.dumps(config))
        self.log_path.write_text("")
        arguments = ["/bin/sh", str(SCRIPT), command, "demo", "cx", self.message]
        if timeout is not None:
            arguments.append(str(timeout))
        result = subprocess.run(
            arguments,
            env=self.environment,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.calls = [json.loads(line) for line in self.log_path.read_text().splitlines()]
        self.assertFalse((self.directory / "must-not-exist").exists())
        self.assertTrue(
            all(tuple(call[:2]) in {
                ("agent", "get"), ("agent", "prompt"), ("agent", "read")
            } for call in self.calls),
            self.calls,
        )
        return result

    def assert_one_submission(self):
        prompts = [call for call in self.calls if call[:2] == ["agent", "prompt"]]
        self.assertEqual(len(prompts), 1, self.calls)
        self.assertEqual(self.calls[0], ["agent", "get", TARGET])
        self.assertEqual(prompts[0][2], TARGET)
        self.assertTrue(prompts[0][3].endswith("\n\n" + self.message))
        return prompts[0]

    def assert_failed(self, result, submitted=True):
        self.assertNotEqual(result.returncode, 0, result)
        self.assertEqual(result.stdout, "", result)
        self.assertTrue(result.stderr.strip(), result)
        self.assertIn("Worker pane output", result.stderr)
        self.assertIn(["agent", "get", TARGET], self.calls)
        if submitted:
            self.assert_one_submission()
        else:
            self.assertFalse(any(call[:2] == ["agent", "prompt"] for call in self.calls))

    def test_send_confirms_working_and_preserves_message(self):
        for initial_status in ("idle", "done"):
            with self.subTest(initial_status=initial_status):
                result = self.dispatch(get_stdout=agent_response(initial_status))
                self.assertEqual(result.returncode, 0, result)
                self.assertEqual(json.loads(result.stdout), {"started": TARGET, "status": "working"})
                prompt = self.assert_one_submission()
                options = prompt[4:]
                self.assertEqual(options.count("--wait"), 1)
                self.assertEqual(options.count("--timeout"), 1)
                self.assertEqual(options[options.index("--timeout") + 1], "15000")
                self.assertCountEqual(
                    [options[index + 1] for index, option in enumerate(options) if option == "--until"],
                    ["working", "blocked"],
                )
                self.assertEqual(len(options), 7)

    def test_ask_returns_output_after_settling_and_uses_timeout(self):
        for status, timeout in (("idle", None), ("done", 321)):
            with self.subTest(status=status, timeout=timeout):
                result = self.dispatch("ask", timeout, prompt_stdout=agent_response(status))
                self.assertEqual(result.returncode, 0, result)
                self.assertEqual(result.stdout, "Worker pane output\n")
                prompt = self.assert_one_submission()
                self.assertEqual(prompt[4:], ["--wait", "--timeout", str(timeout or 1800000)])
                self.assertEqual(self.calls[-1], ["agent", "read", TARGET, "--source", "recent-unwrapped", "--lines", "200"])

    def test_preexisting_nonready_status_never_submits(self):
        for command in ("send", "ask"):
            for status in ("working", "blocked", "unknown"):
                with self.subTest(command=command, status=status):
                    result = self.dispatch(command, get_stdout=agent_response(status))
                    self.assert_failed(result, submitted=False)

    def test_interactive_readiness_false_never_submits(self):
        for command in ("send", "ask"):
            with self.subTest(command=command):
                result = self.dispatch(command, get_stdout=agent_response("idle", interactive_ready=False))
                self.assert_failed(result, submitted=False)

    def test_invalid_preflight_response_never_submits(self):
        for response in ("", "not-json", "{}"):
            with self.subTest(response=response):
                result = self.dispatch(get_stdout=response)
                self.assert_failed(result, submitted=False)

    def test_preflight_failure_keeps_error_and_exit_code(self):
        for command in ("send", "ask"):
            for stream in ("stdout", "stderr"):
                with self.subTest(command=command, stream=stream):
                    error = '{"error":"agent_not_found"}\n'
                    result = self.dispatch(command, **{
                        "get_exit": 7,
                        "diagnostic_get_exit": 19,
                        "get_stdout": error if stream == "stdout" else "",
                        "get_stderr": error if stream == "stderr" else "",
                    })
                    self.assert_failed(result, submitted=False)
                    self.assertEqual(result.returncode, 7)
                    self.assertIn("agent_not_found", result.stderr)
                    self.assertGreaterEqual(
                        sum(call[:2] == ["agent", "get"] for call in self.calls), 2
                    )

    def test_prompt_failure_on_either_stream_keeps_exit_code(self):
        for command in ("send", "ask"):
            for stream in ("stdout", "stderr"):
                with self.subTest(command=command, stream=stream):
                    error = '{"error":"agent_prompt_stalled"}\n'
                    result = self.dispatch(command, **{
                        "prompt_exit": 7,
                        "prompt_stdout": error if stream == "stdout" else "",
                        "prompt_stderr": error if stream == "stderr" else "",
                    })
                    self.assert_failed(result)
                    self.assertEqual(result.returncode, 7)
                    self.assertIn("agent_prompt_stalled", result.stderr)

    def test_empty_or_malformed_prompt_result_is_not_success(self):
        for command in ("send", "ask"):
            for response in ("", "not-json", "{}", '{"result":{"agent":{}}}'):
                with self.subTest(command=command, response=response):
                    result = self.dispatch(command, prompt_stdout=response)
                    self.assert_failed(result)

    def test_blocked_prompt_result_is_not_acknowledged(self):
        for command in ("send", "ask"):
            with self.subTest(command=command):
                result = self.dispatch(command, prompt_stdout=agent_response("blocked"))
                self.assert_failed(result)

    def test_unexpected_prompt_status_is_not_success(self):
        for command, statuses in (("send", ("idle", "done", "unknown")), ("ask", ("working", "unknown"))):
            for status in statuses:
                with self.subTest(command=command, status=status):
                    result = self.dispatch(command, prompt_stdout=agent_response(status))
                    self.assert_failed(result)


if __name__ == "__main__":
    unittest.main()
