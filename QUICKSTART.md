# Fika Bot - Quick Start (5 minutes)

## TL;DR Steps

### 1️⃣ Create Slack App (2 min)
- Go to https://api.slack.com/apps → Create New App → From scratch
- Name: `Fika Bot`, select your workspace
- Go to OAuth & Permissions
- Add scopes: `chat:write`, `chat:write.public`, `commands`
- Copy **Bot User OAuth Token** (xoxb-...)
- Go to Socket Mode → toggle **on** → generate an app-level token with `connections:write` → copy it (xapp-...)
- Go to Slash Commands → Create New Command → add `/add-me`, `/swap`, `/get-list`, `/my-weeks`, `/skip`, `/undo` (each with a short description)
- Install (or reinstall) to workspace
- Copy your channel ID (e.g., C123456)

### 2️⃣ Set up Email (1 min)
**For Gmail:**
- Enable 2FA at myaccount.google.com
- Generate app password at myaccount.google.com/apppasswords
- Copy the 16-char password

**For other email:** Ask your IT team for SMTP details

### 3️⃣ Create `.env` file (1 min)
Copy `env.template` to `.env` and fill in:
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_CHANNEL_ID=C1234567...
SMTP_SERVER=smtp.gmail.com
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=16-char-password
SENDER_EMAIL=your.email@gmail.com
```

### 4️⃣ Install & Test (1 min)
```bash
pip install -r requirements.txt
python fika_bot.py test
```

Should see:
- ✅ Slack message posted
- ✅ Email sent
- ✅ Rotation complete!

### 5️⃣ Configure Team (1 min)
Edit `fika_config.json`. Each person needs a `slack_id` (their Slack member ID) so the bot can post a real `@mention` — get it from their Slack profile → **"..."** → **"Copy member ID"**:
```json
{
  "department": "Engineering",
  "people": [
    {"name": "Alice", "email": "alice@company.com", "slack_id": "U0123ABC456"},
    {"name": "Bob", "email": "bob@company.com", "slack_id": "U0234BCD567"}
  ]
}
```
If `slack_id` is left blank, the bot just posts the person's plain name instead of pinging them.

### 6️⃣ Run!
```bash
python fika_bot.py
```

✅ **Done!** Bot runs every Monday at 8 AM, and listens for slash commands in Slack.

---

## Slash Commands

All require `SLACK_APP_TOKEN` set and the bot running (`python fika_bot.py`, not `test` mode) — the scheduler alone doesn't listen for commands.

| Command | What it does |
|---------|---------------|
| `/add-me Full Name email@example.com` | Joins you into the rotation, inserted so you come up **last** in the current cycle. Your Slack ID is grabbed automatically; name/email must be typed. No-ops if you're already in. |
| `/swap @user1 @user2` | Swaps the two people's rotation position (use Slack's `@` autocomplete, or their plain name). |
| `/get-list [N]` | Shows the next N people up, starting from whoever's current (default 5). |
| `/my-weeks [N]` | Shows your next N upcoming turns, e.g. "this week" / "next week" / "in 4 weeks" (default 5). |
| `/skip [N]` or `/skip A-B` | Skips the reminder(s) for fika week(s) N or A through B (ISO week numbers, e.g. `/skip 42`, `/skip 42-45`; defaults to whichever week the next reminder covers). `/skip 51-2` wraps across New Year's. Since reminders go out a week early, this correctly suppresses the *prior* week's run(s). Rotation doesn't advance — same person is still up afterward. |
| `/undo` | Rolls the rotation back one step, undoing the last advance. |

---

## If Something Doesn't Work

| Problem | Solution |
|---------|----------|
| SLACK_BOT_TOKEN not set | Check `.env` file exists in same directory as bot |
| channel_not_found error | Invite bot to channel: `/invite @Fika Bot` |
| Can't send email (Gmail) | Use app password, not regular password |
| Bot not running on schedule | Keep terminal open or set up as service |
| @mention doesn't ping anyone | Add the person's real `slack_id` in `fika_config.json` (not their name/handle) |
| `/add-me` doesn't respond | Set `SLACK_APP_TOKEN` in `.env` and make sure the bot is running (not `test` mode) |

See **SETUP.md** for detailed troubleshooting.

---

## Customize When It Runs

Edit `fika_bot.py`, find this section:
```python
day_of_week="fri",  # Change to "mon", "wed", etc.
hour=8,             # Change to desired hour (0-23)
minute=0,           # Change to desired minute
```

**Examples:**
- Monday 4 PM: `day_of_week="mon", hour=16`
- Wednesday 9:30 AM: `day_of_week="wed", hour=9, minute=30`

---

## What It Does

Every week (Friday at 3 PM by default):
1. 📝 Picks next person in round-robin rotation
2. 💬 Posts message in Slack channel announcing fika person
3. 📧 Sends email reminder to that person
4. 🔄 Moves to next person for next week

Perfect for keeping your team caffeinated and connected! ☕🥐
