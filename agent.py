import asyncio
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, function_tool
from livekit.agents.voice.room_io import RoomOptions
from livekit.plugins import silero, synthesia

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
LOCAL_TZ = datetime.now().astimezone().tzinfo or ZoneInfo("UTC")


def load_credentials() -> Credentials:
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        open("token.json", "w").write(creds.to_json())
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        open("token.json", "w").write(creds.to_json())
    return creds


creds = load_credentials()
calendar = build("calendar", "v3", credentials=creds)


def parse_local(dt_str: str) -> datetime:
    """Parse ISO datetime; naive values are treated as local time."""
    raw = dt_str.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ)


def get_events(hours_back: int = 3, days_ahead: int = 7):
    """Fetch calendar events in a window wide enough for 'tomorrow' and this week."""
    now = datetime.now().astimezone(LOCAL_TZ)
    events = (
        calendar.events()
        .list(
            calendarId="primary",
            timeMin=(now - timedelta(hours=hours_back)).isoformat(),
            timeMax=(now + timedelta(days=days_ahead)).isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )

    out = []
    for e in events:
        start = e.get("start", {})
        end = e.get("end", {})
        start_raw = start.get("dateTime") or start.get("date")
        end_raw = end.get("dateTime") or end.get("date")
        title = (e.get("summary") or "").strip() or "(no title)"
        out.append(
            {
                "id": e["id"],
                "title": title,
                "start": start_raw,
                "end": end_raw,
            }
        )
    return out


def format_events_for_speech(events: list[dict]) -> str:
    if not events:
        return "No events in the next week."
    lines = []
    for e in events:
        try:
            start = parse_local(e["start"]) if "T" in e["start"] else e["start"]
            when = start.strftime("%a %b %d at %H:%M") if isinstance(start, datetime) else e["start"]
        except Exception:
            when = e["start"]
        lines.append(f"- {e['title']} on {when} (id={e['id']})")
    return "\n".join(lines)


class CalendarAvatar(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
            You are the user's calendar, given a face. Your job is to hold them accountable.
            You are speaking out loud, so keep replies to one or two short sentences.
            Be dry and deadpan. If they are late for something, say exactly how late.

            Always call get_schedule before answering questions about what is on the calendar.
            When listing events, say the exact title returned by the tool — never invent or guess names.
            When the user asks to schedule something, you MUST call schedule_event.
            Only say an event was created after schedule_event returns success.
            If a tool errors, say it failed — do not pretend it worked.
            Prefer local times. If the user says "tomorrow", use tomorrow's date.
        """
        )

    @function_tool
    async def get_schedule(self) -> str:
        """Get the current time and calendar events from a few hours ago through the next 7 days."""
        now = datetime.now().astimezone(LOCAL_TZ)
        events = get_events()
        return (
            f"Local time is {now:%Y-%m-%d %H:%M %Z}. "
            f"Events:\n{format_events_for_speech(events)}"
        )

    @function_tool
    async def schedule_event(self, title: str, start: str, duration_minutes: int = 60) -> str:
        """Create a new Google Calendar event on the user's primary calendar.
        start is ISO format local time, e.g. 2026-10-07T15:30:00.
        duration_minutes defaults to 60 if the user does not specify a length.
        """
        start_dt = parse_local(start)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        # Use offset in dateTime only — names like "CEST" are rejected by Google.
        body = {
            "summary": title,
            "start": {"dateTime": start_dt.isoformat()},
            "end": {"dateTime": end_dt.isoformat()},
        }
        try:
            created = calendar.events().insert(calendarId="primary", body=body).execute()
        except Exception as e:
            return f"FAILED to create event: {e}"
        shown = created.get("summary") or title
        return (
            f"SUCCESS: Created '{shown}' on {start_dt:%a %b %d at %H:%M} "
            f"(id={created.get('id')})."
        )

    @function_tool
    async def reschedule_event(self, event_id: str, new_start: str) -> str:
        """Move an event to a new start time. new_start is ISO format, e.g. 2026-09-29T15:30:00."""
        event = calendar.events().get(calendarId="primary", eventId=event_id).execute()
        start_key = "dateTime" if "dateTime" in event["start"] else "date"
        if start_key == "date":
            return "Cannot reschedule all-day events with this tool."
        length = datetime.fromisoformat(
            event["end"]["dateTime"].replace("Z", "+00:00")
        ) - datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00"))
        start = parse_local(new_start)
        event["start"] = {"dateTime": start.isoformat()}
        event["end"] = {"dateTime": (start + length).isoformat()}
        try:
            updated = calendar.events().update(
                calendarId="primary", eventId=event_id, body=event
            ).execute()
        except Exception as e:
            return f"FAILED to reschedule: {e}"
        title = updated.get("summary") or "(no title)"
        return f"SUCCESS: Moved '{title}' to {start:%a %b %d at %H:%M}."


async def send_reminders(session: AgentSession):
    reminded = set()
    while True:
        await asyncio.sleep(30)
        for event in get_events(hours_back=0, days_ahead=1):
            start_raw = event["start"]
            if "T" not in str(start_raw):
                continue
            start = parse_local(start_raw)
            minutes_left = (start - datetime.now().astimezone(LOCAL_TZ)).total_seconds() / 60
            if 0 < minutes_left <= 5 and event["id"] not in reminded:
                reminded.add(event["id"])
                session.generate_reply(
                    instructions=(
                        f"Remind the user that '{event['title']}' starts in "
                        f"{round(minutes_left)} minutes."
                    )
                )


# External-drive imports are slow (~40s); default 10s init timeout kills job processes.
server = AgentServer(initialize_process_timeout=120.0)

AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "calendar-avatar")
AVATAR_ID = os.getenv("SYNTHESIA_AVATAR_ID", "7572faa9-15da-400d-8227-ef1ab8932523")


# Match this name in LiveKit Cloud when launching Console / dispatching.
@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt="cartesia/ink-2",  # Speech To Text
        llm="openai/gpt-4.1-mini",  # Large Language Model
        tts="cartesia/sonic-3",  # Text To Speech
        vad=silero.VAD.load(),  # Voice Activity Detection
    )
    avatar = synthesia.AvatarSession(synthesia.AvatarConfig(avatar_ids=[AVATAR_ID]))
    # Avatar must start first: it waits for Synthesia to publish video, then
    # routes TTS audio to the avatar worker (lip-sync) instead of the room.
    await avatar.start(session, room=ctx.room)
    await session.start(
        agent=CalendarAvatar(),
        room=ctx.room,
        # Disable direct room audio — avatar publishes synced audio + video.
        room_options=RoomOptions(audio_output=False),
    )
    session.generate_reply(
        instructions=(
            "Call get_schedule, then open by telling the user the local time and "
            "any event they are late for or that starts soon. Use exact event titles."
        )
    )
    asyncio.create_task(send_reminders(session))


if __name__ == "__main__":
    cli.run_app(server)
