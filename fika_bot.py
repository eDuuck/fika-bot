"""
Fika Rotation Bot - Posts weekly Slack message and sends email reminder
for the person responsible for office fika (Swedish coffee break)
"""

import os
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv(Path(__file__).resolve().parent / ".env")

# Configuration
CONFIG_FILE = "fika_config.json"
ROTATION_STATE_FILE = "rotation_state.json"

# Load environment variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL_ID", "#general")

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")


def load_config():
    """Load or create department configuration."""
    if not Path(CONFIG_FILE).exists():
        print(f"❌ Config file '{CONFIG_FILE}' not found!")
        print("Creating template...")
        template = {
            "department": "Engineering",
            "public_responses": False,
            "schedule": {"day_of_week": "mon", "hour": 8, "minute": 0},
            "people": [
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Bob", "email": "bob@example.com"},
                {"name": "Charlie", "email": "charlie@example.com"},
            ]
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(template, f, indent=2)
        print(f"✅ Template created at {CONFIG_FILE}")
        print("📝 Edit it with your team members and run again!")
        exit(1)
    
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def public_responses_enabled() -> bool:
    """Whether slash command replies should be posted publicly to the channel
    (response_type "in_channel") instead of only visible to the invoking user
    (response_type "ephemeral", Slack's default)."""
    return bool(load_config().get("public_responses", False))


def respond_command(respond, message: str):
    """Send a slash command response, honoring the `public_responses` config flag."""
    if public_responses_enabled():
        respond(message, response_type="in_channel")
    else:
        respond(message)


def load_rotation_state():
    """Load rotation state or initialize it."""
    if Path(ROTATION_STATE_FILE).exists():
        with open(ROTATION_STATE_FILE, "r") as f:
            return json.load(f)
    return {"current_index": 0}


def save_rotation_state(state):
    """Save rotation state."""
    with open(ROTATION_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_next_person() -> dict:
    """Get the next person in the rotation."""
    config = load_config()
    state = load_rotation_state()
    
    people = config["people"]
    current_index = state["current_index"]
    
    # Get current person
    person = people[current_index]
    
    # Update state for next rotation
    next_index = (current_index + 1) % len(people)
    state["current_index"] = next_index
    state["last_updated"] = datetime.now().isoformat()
    save_rotation_state(state)
    
    return person


def add_person(name: str, email: str, slack_id: str):
    """Add a new person into the rotation, positioned so they come up last
    in the current cycle (max delay before they're responsible).

    Inserted right before the current upcoming person in the list, with
    current_index bumped forward so the upcoming person stays the same.
    """
    config = load_config()
    state = load_rotation_state()
    people = config["people"]

    if any(p.get("slack_id") == slack_id for p in people):
        return False, "You're already in the fika rotation."

    current_index = state.get("current_index", 0)
    people.insert(current_index, {"name": name, "email": email, "slack_id": slack_id})

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    state["current_index"] = current_index + 1
    save_rotation_state(state)

    return True, f"Welcome to the fika rotation, {name}! You'll be up last in the current cycle."


def _find_person_index(people: list, token: str):
    """Resolve a /swap argument to an index in `people`.

    Accepts a Slack mention (`<@USER_ID>`, as Slack auto-expands `@name`
    typed in a slash command) or falls back to a case-insensitive name match.
    """
    mention = re.fullmatch(r"<@([A-Z0-9]+)(?:\|[^>]+)?>", token)
    if mention:
        slack_id = mention.group(1)
        for i, p in enumerate(people):
            if p.get("slack_id") == slack_id:
                return i
        return None

    for i, p in enumerate(people):
        if p["name"].lower() == token.lower():
            return i
    return None


def swap_people(token1: str, token2: str):
    """Swap the rotation position of two people, identified by @mention or name."""
    config = load_config()
    people = config["people"]

    i1 = _find_person_index(people, token1)
    i2 = _find_person_index(people, token2)

    if i1 is None:
        return False, f'Couldn\'t find "{token1}" in the rotation.'
    if i2 is None:
        return False, f'Couldn\'t find "{token2}" in the rotation.'
    if i1 == i2:
        return False, "That's the same person twice."

    name1, name2 = people[i1]["name"], people[i2]["name"]
    people[i1], people[i2] = people[i2], people[i1]

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    return True, f"Swapped {name1} and {name2}."


def get_upcoming(n: int) -> list:
    """Return the next `n` people in rotation order, starting with who's up now."""
    config = load_config()
    state = load_rotation_state()
    people = config["people"]

    if not people:
        return []

    count = min(n, len(people))
    current_index = (state.get("current_index", 0) + len(people) - 1) % len(people)
    return [people[(current_index + i) % len(people)] for i in range(count)]


def _week_label(n: int) -> str:
    if n == 0:
        return "this week"
    if n == 1:
        return "next week"
    return f"in {n} weeks"


def undo_last_rotation():
    """Move current_index back one step, undoing the last rotation advance."""
    config = load_config()
    state = load_rotation_state()
    people = config["people"]

    if not people:
        return False, "The rotation is empty."

    current_index = state.get("current_index", 0)
    state["current_index"] = (current_index - 1) % len(people)
    state["last_updated"] = datetime.now().isoformat()
    save_rotation_state(state)

    return True, f"Rolled back one week — {people[state['current_index']]['name']} is up now."


def get_my_weeks(slack_id: str, n: int) -> list:
    """Return, as week offsets from now (0 = this week), the next `n` times
    the given slack_id is up in the rotation."""
    config = load_config()
    state = load_rotation_state()
    people = config["people"]

    my_indices = {i for i, p in enumerate(people) if p.get("slack_id") == slack_id}
    if not my_indices:
        return []

    current_index = state.get("current_index", 0)
    weeks = []
    offset = 0
    # Safety cap: never look further ahead than n full cycles of the list.
    while len(weeks) < n and offset <= n * len(people):
        if (current_index + offset) % len(people) in my_indices:
            weeks.append(offset)
        offset += 1

    return weeks


def get_slack_mention(person: dict) -> str:
    """Format a real @-mention from the person's configured Slack user ID.

    Falls back to their plain name if no slack_id is configured.
    """
    slack_id = person.get("slack_id")
    if not slack_id:
        print(f"⚠️  No slack_id configured for {person['name']}, posting plain name")
        return person["name"]

    return f"<@{slack_id}>"


def send_slack_message(person: dict):
    """Send the fika announcement to Slack."""
    if not SLACK_BOT_TOKEN:
        print("❌ SLACK_BOT_TOKEN not set!")
        return False

    client = WebClient(token=SLACK_BOT_TOKEN)
    mention = get_slack_mention(person)

    message = f""":kanelbulle: *FIKA REMINDER!* :kanelbulle:

The next week's fika champion: *{person["name"]}*

{mention} , you're responsible for bringing treats and coffee for the fika the next week.

A reminder email has been sent to you! ☕"""
    
    try:
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message,
            mrkdwn=True
        )
        print(f"✅ Slack message posted: {response['ts']}")
        return True
    except SlackApiError as e:
        print(f"❌ Error posting to Slack: {e.response['error']}")
        return False


def send_email_reminder(person_name, email):
    """Send email reminder to the fika person."""
    if not all([SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD, SENDER_EMAIL]):
        print("❌ Email configuration incomplete!")
        return False
    
    subject = f"🥐 Your turn for fika! - {datetime.now().strftime('%B %d, %Y')}"
    
    body = f"""Hi {person_name},

You've been selected as the next week's fika champion!

Your mission: Bring delicious treats and coffee for a Swedish fika break the next week.

Fika is a Swedish tradition for taking a proper coffee break—a time to pause, enjoy some pastries, and connect with colleagues.

Thanks for keeping the team caffeinated and happy! ☕🥐

Best regards,
The Fika Bot"""
    
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)

        print(body)
        print(f"✅ Email sent to {email}")
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False


def _iso_year_week(dt: datetime) -> list:
    """[ISO year, ISO week number] for the given datetime, e.g. [2026, 37]."""
    iso = dt.isocalendar()
    return [iso[0], iso[1]]


def _target_week() -> list:
    """The ISO [year, week] a reminder sent right now would be announcing.

    The bot announces the *upcoming* week's fika person (see the message text
    in send_slack_message), so a reminder sent during ISO week W is for W+1.
    """
    return _iso_year_week(datetime.now() + timedelta(days=7))


def _resolve_skip_range(start_week: int, end_week: int) -> list:
    """Resolve a `/skip A-B` (or single-week `/skip N`, as A==B) argument to
    a list of [year, week] pairs.

    Anchored to the next possible occurrence of `start_week` (rolling into
    next year if it's earlier than the soonest skippable week), then walks
    forward to `end_week` — wrapping into the following ISO year if
    `end_week < start_week` (e.g. 51-2 spans New Year's).
    """
    next_target = _target_week()
    year = next_target[0]
    if start_week < next_target[1]:
        year += 1

    if end_week >= start_week:
        return [[year, w] for w in range(start_week, end_week + 1)]

    last_week_of_year = datetime(year, 12, 28).isocalendar()[1]
    weeks = [[year, w] for w in range(start_week, last_week_of_year + 1)]
    weeks += [[year + 1, w] for w in range(1, end_week + 1)]
    return weeks


def run_fika_rotation():
    """Main function to run the weekly rotation."""
    print(f"\n🔄 Running fika rotation at {datetime.now()}")

    target_week = _target_week()
    state = load_rotation_state()
    skip_weeks = state.get("skip_weeks", [])

    if target_week in skip_weeks:
        state["skip_weeks"] = [w for w in skip_weeks if w != target_week]
        save_rotation_state(state)
        print(f"⏭️  Skipping week {target_week[1]}'s fika reminder (requested via /skip)\n")
        return

    person = get_next_person()
    
    print(f"📋 This week's fika person: {person['name']} ({person['email']})")
    
    # Post to Slack
    send_slack_message(person)
    
    # Send email reminder
    send_email_reminder(person["name"], person["email"])
    
    print("✅ Rotation complete!\n")


bolt_app = App(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None


if bolt_app:
    @bolt_app.command("/add-me")
    def handle_add_me(ack, respond, command):
        ack()

        text = command.get("text", "").strip()
        parts = text.split()

        if len(parts) < 2 or "@" not in parts[-1]:
            respond_command(respond, "Usage: `/add-me Full Name email@example.com`")
            return

        email = parts[-1]
        name = " ".join(parts[:-1])
        slack_id = command["user_id"]

        _, message = add_person(name, email, slack_id)
        respond_command(respond, message)


    @bolt_app.command("/swap")
    def handle_swap(ack, respond, command):
        ack()

        parts = command.get("text", "").strip().split()
        if len(parts) != 2:
            respond_command(respond, "Usage: `/swap @user1 @user2`")
            return

        _, message = swap_people(parts[0], parts[1])
        respond_command(respond, message)


    @bolt_app.command("/get-list")
    def handle_get_list(ack, respond, command):
        ack()

        text = command.get("text", "").strip()
        n = 5
        if text:
            if not text.isdigit() or int(text) < 1:
                respond_command(respond, "Usage: `/get-list [N]` (N must be a positive whole number, default 5)")
                return
            n = int(text)

        upcoming = get_upcoming(n)
        if not upcoming:
            respond_command(respond, "The rotation is empty.")
            return

        lines = [f"{i + 1}. {p['name']}" for i, p in enumerate(upcoming)]
        note = f"\n_(only {len(upcoming)} people in the rotation)_" if len(upcoming) < n else ""
        respond_command(respond, "*Upcoming fika order:*\n" + "\n".join(lines) + note)


    @bolt_app.command("/my-weeks")
    def handle_my_weeks(ack, respond, command):
        ack()

        text = command.get("text", "").strip()
        n = 5
        if text:
            if not text.isdigit() or int(text) < 1:
                respond_command(respond, "Usage: `/my-weeks [N]` (N must be a positive whole number, default 5)")
                return
            n = int(text)

        weeks = get_my_weeks(command["user_id"], n)
        if not weeks:
            respond_command(respond, "You're not currently in the fika rotation.")
            return

        lines = [f"- {_week_label(w)}" for w in weeks]
        respond_command(respond, "*Your upcoming fika weeks:*\n" + "\n".join(lines))


    @bolt_app.command("/skip")
    def handle_skip(ack, respond, command):
        ack()

        text = command.get("text", "").strip()
        usage = ("Usage: `/skip [N]` or `/skip A-B` (ISO week numbers 1-53; "
                  "a range wraps into next year if B < A). Defaults to the next upcoming reminder's week.")

        if not text:
            targets = [_target_week()]
        else:
            range_match = re.fullmatch(r"(\d{1,2})\s*-\s*(\d{1,2})", text)
            if range_match:
                start_week, end_week = int(range_match.group(1)), int(range_match.group(2))
            elif text.isdigit():
                start_week = end_week = int(text)
            else:
                respond_command(respond, usage)
                return

            if not (1 <= start_week <= 53 and 1 <= end_week <= 53):
                respond_command(respond, usage)
                return

            targets = _resolve_skip_range(start_week, end_week)

        state = load_rotation_state()
        skip_weeks = state.get("skip_weeks", [])

        added, already = [], []
        for t in targets:
            if t in skip_weeks:
                already.append(t)
            else:
                skip_weeks.append(t)
                added.append(t)

        state["skip_weeks"] = skip_weeks
        save_rotation_state(state)

        def fmt(pairs):
            return ", ".join(f"{w} ({y})" for y, w in pairs)

        parts = []
        if added:
            plural = "s" if len(added) != 1 else ""
            parts.append(f"Skipping week{plural}: {fmt(added)}.")
        if already:
            parts.append(f"Already scheduled: {fmt(already)}.")
        respond_command(respond, " ".join(parts))


    @bolt_app.command("/undo")
    def handle_undo(ack, respond, command):
        ack()

        _, message = undo_last_rotation()
        respond_command(respond, message)


def start_command_listener():
    """Start listening for slash commands over Socket Mode. Blocks."""
    if not bolt_app:
        print("❌ SLACK_BOT_TOKEN not set - can't start command listener!")
        return
    if not SLACK_APP_TOKEN:
        print("❌ SLACK_APP_TOKEN not set - can't start command listener!")
        return

    print("✅ Command listener started (Socket Mode)")
    SocketModeHandler(bolt_app, SLACK_APP_TOKEN).start()


DAY_NAMES = {
    "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
    "fri": "Friday", "sat": "Saturday", "sun": "Sunday",
}


def start_scheduler():
    """Start the background scheduler for weekly rotations."""
    config = load_config()
    schedule = config.get("schedule", {"day_of_week": "mon", "hour": 8, "minute": 0})
    day_of_week = schedule.get("day_of_week", "mon")
    hour = schedule.get("hour", 8)
    minute = schedule.get("minute", 0)

    scheduler = BackgroundScheduler()

    # Configure the schedule via the "schedule" key in fika_config.json:
    # - day_of_week: mon/tue/wed/thu/fri/sat/sun
    # - hour: 0-23
    # - minute: 0-59
    scheduler.add_job(
        run_fika_rotation,
        trigger="cron",
        day_of_week=day_of_week,
        hour=hour,
        minute=minute,
        id="fika_rotation"
    )

    scheduler.start()
    print("✅ Scheduler started!")
    day_label = DAY_NAMES.get(day_of_week, day_of_week)
    print(f"📅 Fika rotation scheduled for every {day_label} at {hour:02d}:{minute:02d}")

    return scheduler


def test_mode():
    """Run a test rotation immediately."""
    print("🧪 Running test mode...\n")
    run_fika_rotation()


if __name__ == "__main__":
    import sys
    import time

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_mode()
    else:
        scheduler = start_scheduler()
        print("\n⏳ Bot is running. Press Ctrl+C to stop.\n")
        try:
            if SLACK_APP_TOKEN:
                start_command_listener()  # blocks
            else:
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            scheduler.shutdown()
            print("\n👋 Bot stopped")
