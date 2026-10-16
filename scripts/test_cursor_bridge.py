"""Exercise native OAuth registration against a local mock, never the real issuer."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    os.getenv("MCP_REMOTE_TEST_PROXY"),
    "Set MCP_REMOTE_TEST_PROXY to the pinned bridge's dist/proxy.js for the smoke test",
)
class CursorBridgeTests(unittest.TestCase):
    def test_bridge_registers_native_public_client_with_loopback_callback(self):
        registration = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def respond(self, status, payload, headers=None):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/metadata":
                    self.respond(200, {
                        "resource": f"{base}/mcp",
                        "authorization_servers": [base],
                        "scopes_supported": ["mcp:tools"],
                    })
                elif self.path == "/.well-known/oauth-authorization-server":
                    self.respond(200, {
                        "issuer": base,
                        "authorization_endpoint": f"{base}/authorize",
                        "token_endpoint": f"{base}/token",
                        "registration_endpoint": f"{base}/register",
                        "response_types_supported": ["code"],
                        "grant_types_supported": ["authorization_code", "refresh_token"],
                        "token_endpoint_auth_methods_supported": ["none"],
                        "code_challenge_methods_supported": ["S256"],
                        "scopes_supported": ["mcp:tools", "openid", "offline_access"],
                    })
                else:
                    self.respond(404, {})

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                if self.path == "/mcp":
                    self.respond(401, {"error": "unauthorized"}, {
                        "WWW-Authenticate": f'Bearer resource_metadata="{base}/metadata"',
                    })
                elif self.path == "/register":
                    registration.update(json.loads(body))
                    # Stop before consent/browser launch and token issuance.
                    self.respond(400, {
                        "error": "invalid_client_metadata",
                        "error_description": "mock_registration_stop",
                    })
                else:
                    self.respond(404, {})

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        base = f"http://127.0.0.1:{server.server_port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as cache:
                allowed_env = {
                    "PATH", "SYSTEMROOT", "COMSPEC", "APPDATA", "LOCALAPPDATA",
                    "HOME", "USERPROFILE", "TEMP", "TMP",
                }
                env = {k: v for k, v in os.environ.items() if k.upper() in allowed_env}
                env["MCP_REMOTE_CONFIG_DIR"] = cache
                process = subprocess.Popen(
                    [
                        "node", os.environ["MCP_REMOTE_TEST_PROXY"], f"{base}/mcp",
                        "--allow-http", "--transport", "http-only",
                        "--static-oauth-client-metadata",
                        f"@{ROOT / 'cursor' / 'oauth-client-metadata.json'}",
                    ],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    self.fail("OAuth registration smoke test timed out")
                finally:
                    stdout, stderr = process.communicate()
                output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
                self.assertIn("mock_registration_stop", output)
                self.assertEqual(registration.get("application_type"), "native")
                self.assertEqual(registration.get("token_endpoint_auth_method"), "none")
                self.assertIn("mcp:tools", registration.get("scope", "").split())
                self.assertNotIn("client_secret", registration)
                self.assertEqual(len(registration["redirect_uris"]), 1)
                callback = urlparse(registration["redirect_uris"][0])
                self.assertEqual(callback.scheme, "http")
                self.assertIn(callback.hostname, {"localhost", "127.0.0.1", "::1"})
                self.assertEqual(callback.path, "/oauth/callback")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
