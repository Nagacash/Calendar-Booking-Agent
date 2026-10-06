import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import { useKeyStore } from "./store/keys";
import { mintLiveKitToken } from "./lib/token";
import "./App.css";

export default function App() {
  const keys = useKeyStore();
  const [ready, setReady] = useState(false);
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState("Ready");
  const [live, setLive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({
    livekitUrl: "",
    apiKey: "",
    apiSecret: "",
    agentName: "calendar-avatar",
  });

  const videoRef = useRef<HTMLVideoElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const placeholderRef = useRef<HTMLDivElement>(null);
  const roomRef = useRef<Room | null>(null);

  useEffect(() => {
    const ok = keys.hasKeys();
    setReady(ok);
    setEditing(!ok);
    setDraft({
      livekitUrl: keys.livekitUrl,
      apiKey: keys.apiKey,
      apiSecret: keys.apiSecret,
      agentName: keys.agentName || "calendar-avatar",
    });
  }, [keys.livekitUrl, keys.apiKey, keys.apiSecret, keys.agentName]);

  useEffect(() => {
    return () => {
      roomRef.current?.disconnect();
    };
  }, []);

  function saveKeys(e: FormEvent) {
    e.preventDefault();
    keys.setKeys(draft);
    setReady(true);
    setEditing(false);
    setStatus("Keys saved in this browser only");
  }

  function attachTrack(track: Track, identity: string) {
    // Prefer Synthesia avatar worker tracks (publishes on behalf of the agent).
    const fromAvatar =
      identity.includes("synthesia") || identity.includes("avatar");

    if (track.kind === Track.Kind.Video && videoRef.current) {
      track.attach(videoRef.current);
      // Video-only element: keep muted so browsers allow autoplay reliably.
      videoRef.current.muted = true;
      videoRef.current.playsInline = true;
      videoRef.current.style.display = "block";
      if (placeholderRef.current) placeholderRef.current.style.display = "none";
      setLive(true);
      void videoRef.current.play().catch(() => {});
      setStatus(fromAvatar ? `Face live · ${identity}` : `Video · ${identity}`);
    }
    if (track.kind === Track.Kind.Audio && audioRef.current) {
      track.attach(audioRef.current);
      audioRef.current.muted = false;
      audioRef.current.volume = 1;
      void audioRef.current.play().catch(() => {});
      setStatus((prev) =>
        prev.startsWith("Face") ? `${prev} + voice` : `Voice · ${identity}`,
      );
    }
  }

  function resetMedia() {
    if (videoRef.current) {
      videoRef.current.srcObject = null;
      videoRef.current.style.display = "none";
    }
    if (audioRef.current) {
      audioRef.current.srcObject = null;
    }
    if (placeholderRef.current) {
      placeholderRef.current.style.display = "grid";
    }
    setLive(false);
  }

  function stop() {
    const room = roomRef.current;
    roomRef.current = null;
    if (room) {
      room.removeAllListeners();
      room.disconnect();
    }
    resetMedia();
    setBusy(false);
    setStatus("Stopped — Connect again when ready");
  }

  async function connect() {
    if (!keys.hasKeys()) {
      setEditing(true);
      return;
    }
    // End any prior session before starting a new one.
    if (roomRef.current) stop();
    setBusy(true);
    setStatus("Minting room token…");
    try {
      const roomName = `avatar-view-${crypto.randomUUID().slice(0, 8)}`;
      const token = await mintLiveKitToken({
        apiKey: keys.apiKey,
        apiSecret: keys.apiSecret,
        identity: `viewer-${crypto.randomUUID().slice(0, 8)}`,
        name: "Avatar Viewer",
        roomName,
        agentName: keys.agentName,
      });

      const room = new Room({ adaptiveStream: false, dynacast: true });
      roomRef.current = room;
      room.on(RoomEvent.TrackSubscribed, (track, _pub, participant) => {
        attachTrack(track, participant.identity);
      });
      room.on(RoomEvent.ParticipantConnected, (participant) => {
        setStatus(`Joined: ${participant.identity}`);
        for (const pub of participant.trackPublications.values()) {
          if (pub.track) attachTrack(pub.track, participant.identity);
        }
      });
      room.on(RoomEvent.Disconnected, () => {
        if (roomRef.current === room) {
          roomRef.current = null;
          resetMedia();
          setBusy(false);
          setStatus("Disconnected");
        }
      });

      setStatus(`Connecting to ${roomName}…`);
      await room.connect(keys.livekitUrl, token);
      await room.localParticipant.setMicrophoneEnabled(true);
      setStatus("Connected — start your local agent if it is not running");
      for (const p of room.remoteParticipants.values()) {
        for (const pub of p.trackPublications.values()) {
          if (pub.track) attachTrack(pub.track, p.identity);
        }
      }
    } catch (err) {
      console.error(err);
      setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <div className="shell">
        <header className="brand">
          <div className="brand-mark">
            <img src="/logo.png" alt="Logo" />
            <div className="brand-copy">
              <h1>Calendar Face</h1>
              <p>Bring your own keys</p>
            </div>
          </div>
        </header>

        <form className="panel" onSubmit={saveKeys}>
          <h2>Your LiveKit keys</h2>
          <p className="hint">
            Stored only in this browser (Zustand + localStorage). Never sent to
            Naga Codex. You still run <code>python agent.py dev</code> locally
            with the same LiveKit project plus your Synthesia + Google keys.
          </p>

          <label>
            LiveKit URL
            <input
              required
              placeholder="wss://your-project.livekit.cloud"
              value={draft.livekitUrl}
              onChange={(e) => setDraft({ ...draft, livekitUrl: e.target.value })}
            />
          </label>
          <label>
            API Key
            <input
              required
              value={draft.apiKey}
              onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
            />
          </label>
          <label>
            API Secret
            <input
              required
              type="password"
              value={draft.apiSecret}
              onChange={(e) => setDraft({ ...draft, apiSecret: e.target.value })}
            />
          </label>
          <label>
            Agent name
            <input
              required
              value={draft.agentName}
              onChange={(e) => setDraft({ ...draft, agentName: e.target.value })}
            />
          </label>

          <div className="actions">
            <button type="submit">Save & continue</button>
            {ready && (
              <button type="button" className="secondary" onClick={() => setEditing(false)}>
                Cancel
              </button>
            )}
          </div>
          <p className="note">
            Get keys at cloud.livekit.io → Settings → API keys. Clone the repo and
            run the agent on your machine so Synthesia/Google usage bills you, not
            the project author.
          </p>
        </form>

        <footer className="controls">
          <div />
          <a className="powered" href="https://www.nagacodex.cloud/" target="_blank" rel="noreferrer">
            Powered by <span>Naga Codex</span>
          </a>
        </footer>
      </div>
    );
  }

  return (
    <div className="shell">
      <header className="brand">
        <div className="brand-mark">
          <img src="/logo.png" alt="Logo" />
          <div className="brand-copy">
            <h1>Calendar Face</h1>
            <p>Accountability, live</p>
          </div>
        </div>
        <div className={`live-pill${live ? " on" : ""}`}>
          <i /> Live session
        </div>
      </header>

      <section className="stage-wrap">
        <div className="stage">
          <div id="placeholder" ref={placeholderRef}>
            Connect — your calendar gets a face
          </div>
          <video ref={videoRef} autoPlay playsInline />
          <audio ref={audioRef} autoPlay />
        </div>
      </section>

      <footer className="controls">
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <button type="button" disabled={busy} onClick={() => void connect()}>
            Connect
          </button>
          <button
            type="button"
            className="stop"
            disabled={!busy && !live}
            onClick={stop}
          >
            Stop
          </button>
          <button type="button" className="secondary" onClick={() => setEditing(true)}>
            Keys
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              stop();
              keys.clearKeys();
              setEditing(true);
              setStatus("Keys cleared");
            }}
          >
            Clear keys
          </button>
        </div>
        <div className="meta">
          <div id="status">{status}</div>
          <a className="powered" href="https://www.nagacodex.cloud/" target="_blank" rel="noreferrer">
            Powered by <span>Naga Codex</span>
          </a>
        </div>
      </footer>
    </div>
  );
}
