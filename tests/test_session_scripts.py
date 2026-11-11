"""The two scripts the skills call instead of carrying shell: sending the change, saving a report.

Both run against a real git repository in a temporary directory and a real HTTP server on
127.0.0.1, because what they promise is about git's index and about what crosses the wire.
"""
from __future__ import annotations

import http.server
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
TOKEN = "ab" * 32


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def run(script: str, *args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / "app.py").write_text("x = 1\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "first")
    return root


@pytest.fixture
def server():
    seen: dict[str, object] = {"report": b"# Report\n\n```mermaid\nflowchart LR\n```\n", "status": 200}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            seen["upload_token"] = self.headers.get("X-Upload-Token")
            seen["body"] = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(int(seen["status"]))
            self.end_headers()

        def do_GET(self):
            ok = self.headers.get("X-Report-Token") == "r" * 40
            self.send_response(200 if ok else 401)
            self.end_headers()
            if ok:
                self.wfile.write(seen["report"])

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    seen["url"] = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield seen
    httpd.shutdown()


def upload(repo: Path, server, *extra: str, token: str = TOKEN):
    return run("cloudaeye_session.py", "upload", "--session", "0a1b-2c3d", "--url", f"{server['url']}/upload/x", *extra,
               cwd=repo, env={"CE_UPLOAD_TOKEN": token})


def test_head_prints_branch_and_head_and_makes_an_ignored_workspace(repo):
    out = run("cloudaeye_session.py", "head", cwd=repo)
    assert out.returncode == 0 and '"branch": "main"' in out.stdout and git(repo, "rev-parse", "HEAD").strip() in out.stdout
    assert '"repo": "repo"' in out.stdout                    # no remote: the folder's name
    assert (repo / ".cloudaeye" / ".gitignore").read_text(encoding="utf-8") == "*\n"
    assert git(repo, "status", "--short") == ""             # the workspace is not part of the change


def test_a_new_file_is_in_the_diff_and_the_developers_index_is_untouched(repo, server):
    (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
    (repo / "new_module.py").write_text("y = 1\n", encoding="utf-8")
    (repo / ".OWNERS.md").write_text("# written by assign-reviewer\n", encoding="utf-8")
    before = git(repo, "status", "--porcelain=v1")
    out = upload(repo, server)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "base_source=head" in out.stdout and "upload_http=200" in out.stdout and "diff_files=2 total_files=2" in out.stdout
    body = server["body"].decode("utf-8", "replace")
    assert "new_module.py" in body and "+y = 1" in body and "+x = 2" in body
    assert ".OWNERS.md" not in body                         # CloudAEye's own file is not the change
    assert server["upload_token"] == TOKEN and TOKEN not in out.stdout
    assert git(repo, "status", "--porcelain=v1") == before  # `??` stays `??`: nothing was added to the index
    assert (repo / ".cloudaeye" / "session" / "session.diff").read_text(encoding="utf-8").count("diff --git") == 2


def test_a_scope_narrows_the_diff_and_says_how_much_was_left_out(repo, server):
    (repo / "svc").mkdir()
    (repo / "svc" / "a.py").write_text("a = 1\n", encoding="utf-8")
    (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
    out = upload(repo, server, "--scope", "svc")
    assert "diff_files=1 total_files=2 scope=svc" in out.stdout
    assert "svc/a.py" in server["body"].decode() and "app.py" not in server["body"].decode()


@pytest.mark.parametrize("args, token, error", [
    (["--scope", "../elsewhere"], TOKEN, "scope_outside_repo"),
    ([], "short", "bad_upload_token"),
])
def test_bad_input_is_refused_before_anything_is_sent(repo, server, args, token, error):
    out = upload(repo, server, *args, token=token)
    assert out.returncode == 1 and out.stdout.strip() == f"cloudaeye_error={error}" and "body" not in server


def test_a_token_never_goes_to_a_plain_http_host_that_is_not_this_machine(repo):
    out = run("cloudaeye_session.py", "upload", "--session", "0a1b", "--url", "http://example.com/upload/x", cwd=repo,
              env={"CE_UPLOAD_TOKEN": TOKEN})
    assert out.stdout.strip() == "cloudaeye_error=insecure_url"
    out = run("cloudaeye_report.py", "--url", "http://example.com/report/j", "--name", "review-arch", cwd=repo,
              env={"CE_REPORT_TOKEN": "r" * 40})
    assert out.stdout.strip() == "report_error=insecure_url"


def test_a_refused_upload_is_reported_not_hidden(repo, server):
    (repo / "app.py").write_text("x = 3\n", encoding="utf-8")
    server["status"] = 401
    assert "upload_http=401" in upload(repo, server).stdout


def test_the_report_is_saved_whole_under_the_ignored_workspace(repo, server):
    out = run("cloudaeye_report.py", "--url", f"{server['url']}/report/j1", "--name", "review-arch", cwd=repo,
              env={"CE_REPORT_TOKEN": "r" * 40})
    assert out.stdout.strip() == f"report_path=.cloudaeye/reports/review-arch.md report_bytes={len(server['report'])}"
    assert (repo / ".cloudaeye" / "reports" / "review-arch.md").read_bytes() == server["report"]
    assert git(repo, "status", "--short") == "" and "r" * 40 not in out.stdout


@pytest.mark.parametrize("name, token, error", [
    ("review-arch", "x" * 40, "token_refused"),
    ("../../etc/passwd", "r" * 40, "bad_name"),
    ("review-arch", "", "bad_token"),
])
def test_a_report_that_cannot_be_saved_says_why_and_writes_nothing(repo, server, name, token, error):
    out = run("cloudaeye_report.py", "--url", f"{server['url']}/report/j1", "--name", name, cwd=repo,
              env={"CE_REPORT_TOKEN": token})
    assert out.returncode == 1 and out.stdout.strip() == f"report_error={error}"
    assert not (repo / ".cloudaeye" / "reports").exists()


# ── the one command the skills run ────────────────────────────────────────────

def cae(repo: Path, *args: str) -> subprocess.CompletedProcess:
    import shutil

    sh = shutil.which("sh")
    if sh is None:
        pytest.skip("no POSIX shell on this machine")
    return subprocess.run([sh, (SCRIPTS / "cae").as_posix(), *args], cwd=repo, capture_output=True, text=True)


def test_one_plain_command_uploads_from_the_tools_own_answer_and_saves_the_report(repo, server):
    """A skill pre-approves `sh …/scripts/cae *`; a loop, a `VAR=x` prefix or a second command in
    the call would ask the developer for permission, so each step is this command and its arguments."""
    import json

    (repo / "app.py").write_text("x = 5\n", encoding="utf-8")
    answer = {"status": "ok", "session_id": "0a1b-2c3d", "target_branch": "", "upload_url": f"{server['url']}/upload/x",
              "upload_token": TOKEN, "key_url": "", "key_token": ""}
    out = cae(repo, "upload", json.dumps({"result": json.dumps(answer)}))        # as MCP wraps it
    assert out.returncode == 0 and "upload_http=200" in out.stdout and TOKEN not in out.stdout, out.stdout + out.stderr
    assert b"+x = 5" in server["body"] and server["upload_token"] == TOKEN
    saved = cae(repo, "report", "review-arch", json.dumps({"name": "review-arch", "url": f"{server['url']}/report/j", "token": "r" * 40}))
    assert saved.stdout.strip().startswith("report_path=.cloudaeye/reports/review-arch.md")
    assert cae(repo, "upload", "not json").stdout.strip() == "cloudaeye_error=bad_session_json"
    assert cae(repo, "nothing").stdout.strip() == "cloudaeye_error=unknown_command"
