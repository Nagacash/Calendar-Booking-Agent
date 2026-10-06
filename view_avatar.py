"""Local page that joins LiveKit and shows the Synthesia video track.

Run with `python agent.py dev` already running, then:

    python view_avatar.py

Open http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from livekit import api
from livekit.protocol.agent_dispatch import RoomAgentDispatch
from livekit.protocol.room import RoomConfiguration

load_dotenv()

ROOT = Path(__file__).resolve().parent
AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "calendar-avatar")
PORT = 8765


def mint_token(room_name: str) -> str:
    key = os.environ["LIVEKIT_API_KEY"]
    secret = os.environ["LIVEKIT_API_SECRET"]
    room_config = RoomConfiguration()
    room_config.agents.append(RoomAgentDispatch(agent_name=AGENT_NAME))

    return (
        api.AccessToken(key, secret)
        .with_identity(f"viewer-{uuid.uuid4().hex[:8]}")
        .with_name("Avatar Viewer")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .with_room_config(room_config)
        .to_jwt()
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[viewer] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/viewer.html"):
            html = (ROOT / "viewer.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
            return
        if path == "/logo.png":
            logo = ROOT / "logo.png"
            if not logo.exists():
                self._send(404, b"Missing logo.png", "text/plain; charset=utf-8")
                return
            self._send(200, logo.read_bytes(), "image/png")
            return
        if path == "/token":
            missing = [
                k
                for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
                if not os.environ.get(k)
            ]
            if missing:
                msg = f"Missing env vars: {', '.join(missing)}".encode()
                self._send(500, msg, "text/plain; charset=utf-8")
                return
            room_name = f"avatar-view-{uuid.uuid4().hex[:8]}"
            payload = {
                "token": mint_token(room_name),
                "url": os.environ["LIVEKIT_URL"],
                "roomName": room_name,
                "agentName": AGENT_NAME,
            }
            self._send(200, json.dumps(payload).encode(), "application/json")
            return
        self._send(404, b"Not found", "text/plain; charset=utf-8")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Open http://127.0.0.1:{PORT}")
    print("Keep `python agent.py dev` running in another terminal.")
    server.serve_forever()
