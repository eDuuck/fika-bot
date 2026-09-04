# Fika Bot Setup Guide

## Prerequisites

- Python 3.8+
- A Slack workspace where you can create/manage apps
- An email account for sending reminders (Gmail, Outlook, or any SMTP server)

---

## 1. Slack Bot Setup

### Step 1: Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Name it `Fika Bot`
5. Select your workspace
6. Click **"Create App"**

### Step 2: Enable Bot Token Scopes

1. In the left sidebar, go to **"OAuth & Permissions"**
2. Scroll to **"Scopes"**
3. Under **"Bot Token Scopes"**, click **"Add an OAuth Scope"**
4. Add these scopes:
   - `chat:write` — Post messages
   - `chat:write.public` — Post in public channels
   - `commands` — Add slash commands

### Step 2b: Enable Socket Mode & Create the Slash Commands

1. In the left sidebar, go to **"Socket Mode"** and toggle it **on**
   - You'll be prompted to generate an **app-level token** — name it anything, add the `connections:write` scope, and click **"Generate"**
   - Copy this token (starts with `xapp-`) — you'll need it in the `.env` file as `SLACK_APP_TOKEN`
2. In the left sidebar, go to **"Slash Commands"** → **"Create New Command"**, and create each of these (command name + short description, no URL needed since Socket Mode handles delivery):
   - `/add-me` — Join the fika rotation
   - `/swap` — Swap two people's position in the rotation
   - `/get-list` — Show the upcoming fika order
   - `/my-weeks` — Show your upcoming fika weeks
   - `/skip` — Skip a week's fika reminder
   - `/undo` — Roll the rotation back one week
3. Reinstall the app to your workspace if prompted (required after adding scopes/commands)

### Step 3: Get Your Bot Token

1. Still in **"OAuth & Permissions"**, scroll to the top
2. Copy the **"Bot User OAuth Token"** (starts with `xoxb-`)
3. Save this—you'll need it in the `.env` file

### Step 4: Install the App to Your Workspace

1. At the top of the page, click **"Install to Workspace"**
2. Click **"Allow"**

### Step 5: Get Your Channel ID

1. Open your Slack workspace
2. Find the channel where you want fika announcements (e.g., `#general`)
3. Click the channel name at the top → **"About"** tab
4. Scroll down to find **"Channel ID"** (e.g., `C1234567890`)
5. Save this for the `.env` file

---

## 2. Email Setup

You have a few options:

### Option A: Gmail (Recommended for Testing)

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **"2-Step Verification"** if not already enabled
3. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Device: **Mail** | OS: **Windows/Mac/Linux**
4. Generate an app password (16 characters)
5. Use these credentials:
   ```
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your.email@gmail.com
   SMTP_PASSWORD=<16-char app password>
   SENDER_EMAIL=your.email@gmail.com
   ```

### Option B: Outlook/Office 365

```
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=your.email@outlook.com
SMTP_PASSWORD=your_password
SENDER_EMAIL=your.email@outlook.com
```

### Option C: Custom SMTP Server

Contact your IT department for:
- SMTP server address
- SMTP port (usually 587 or 465)
- Username and password
- Sender email address

---

## 3. Environment Variables

Create a `.env` file in the same directory as `fika_bot.py`:

```env
# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
SLACK_CHANNEL_ID=C1234567890

# Email (Gmail example)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=your-app-password
SENDER_EMAIL=your.email@gmail.com
```

**Never commit this file to git!**

---

## 4. Configure Your Team

1. Run the bot once:
   ```bash
   python fika_bot.py test
   ```
   This creates `fika_config.json`

2. Edit `fika_config.json` with your team:
   ```json
   {
     "department": "Engineering",
     "people": [
       {"name": "Alice Johnson", "email": "alice@company.com", "slack_id": "U0123ABC456"},
       {"name": "Bob Smith", "email": "bob@company.com", "slack_id": "U0234BCD567"},
       {"name": "Charlie Brown", "email": "charlie@company.com", "slack_id": "U0345CDE678"}
     ]
   }
   ```

---

## 5. Installation & Running

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Test the Bot

```bash
python fika_bot.py test
```

This will:
- ✅ Post a test message to Slack
- ✅ Send a test email
- ✅ Move to the next person in rotation

### Run the Bot

```bash
python fika_bot.py
```

The bot will now run in the background and send reminders every Monday at 8:00 AM.

**To stop:** Press `Ctrl+C`

---

## 6. Slash Commands

All commands require the bot process to be running with `SLACK_APP_TOKEN` set (see step 2b above) — the scheduler alone won't pick up slash commands.

### `/add-me Full Name email@example.com`
Joins the caller into the rotation.
- Their Slack user ID is taken automatically from the command (used as `slack_id`) — name and email must be typed
- Inserted so they come up **last** in the current rotation cycle (max time before it's their turn)
- If their Slack user ID is already in `fika_config.json`, replies that they're already in and makes no change

### `/swap @user1 @user2`
Swaps two people's position in the rotation list. Use Slack's `@mention` autocomplete for each (also accepts a plain name as typed in `fika_config.json`, matched case-insensitively). If one of them is currently up next, this changes who's up.

### `/get-list [N]`
Shows the next N people in rotation order, starting with whoever's up now. Defaults to 5. Caps at the number of people in the rotation (no repeats).

### `/my-weeks [N]`
Shows the caller's next N upcoming turns (as "this week" / "next week" / "in X weeks"), based on their Slack user ID. Defaults to 5. Replies that they're not in the rotation if their `slack_id` isn't found.

### `/skip [N]` or `/skip A-B`
Skips the reminder(s) *for* given fika week(s) — nothing is sent, and the rotation does **not** advance for them, so whoever was up stays up for the next reminder that does go out. `N` (or `A`/`B`) is the **ISO calendar week number** (1-53, e.g. `/skip 42`, `/skip 42-45`), defaulting to whichever week the next scheduled reminder would announce if `N` is omitted entirely. Assumes this year unless that week number has already passed, in which case it schedules next year's occurrence. `/skip 51-2` wraps across New Year's (e.g. weeks 51, 52, [53 if that ISO year has one], 1, 2). Replies listing which weeks were newly scheduled vs. already pending.

Since the bot announces the *upcoming* week's person (a reminder sent during week 42 is for week 43's fika), `/skip 43` suppresses the run that fires during week 42, not the one during week 43 — the bot works this out automatically, you just name the fika week(s) you want off.

### `/undo`
Rolls the rotation back one step — moves `current_index` back to whoever was up before the last advance (from a scheduled run, a test run, or `/add-me`). Doesn't touch `/swap` or any pending `/skip` schedule.

## 7. Customize the Schedule

Edit `fika_bot.py` and find this section:

```python
scheduler.add_job(
    run_fika_rotation,
    trigger="cron",
    day_of_week="mon",  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    hour=8,             # 0-23
    minute=0,           # 0-59
    id="fika_rotation"
)
```

Examples:
- **Friday at 4 PM:** `day_of_week="fri", hour=16, minute=0`
- **Wednesday at 9:30 AM:** `day_of_week="wed", hour=9, minute=30`
- **Every day at 10 AM:** Change `trigger="cron"` to `trigger="interval", hours=24, start_date=<date>`

---

## 8. Run as a Service (Optional)

### On Linux/Mac: Use systemd or launchd

Create `/etc/systemd/system/fika-bot.service`:

```ini
[Unit]
Description=Fika Rotation Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/fika_bot
ExecStart=/usr/bin/python3 /path/to/fika_bot/fika_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable fika-bot
sudo systemctl start fika-bot
```

### On Windows: Use Task Scheduler

1. Open Task Scheduler
2. Create Basic Task → Name: "Fika Bot"
3. Trigger: At startup
4. Action: Start a program
   - Program: `C:\Python\python.exe`
   - Arguments: `C:\path\to\fika_bot.py`
   - Start in: `C:\path\to\`
5. Click OK

---

## Troubleshooting

### "SLACK_BOT_TOKEN not set!"
- Check that your `.env` file exists in the same directory as `fika_bot.py`
- Run: `echo $SLACK_BOT_TOKEN` to verify it's loaded

### "Error posting to Slack: channel_not_found"
- Make sure your bot is invited to the channel
- Go to your Slack channel and type `/invite @Fika Bot`
- Verify the `SLACK_CHANNEL_ID` is correct

### "@name" appears as plain text instead of a real mention / doesn't notify anyone
- Slack only turns `<@USER_ID>` into a clickable, notifying mention — plain text like `@maggie` is never linked, no matter how it's typed
- Each person in `fika_config.json` needs a `slack_id` — their Slack **member ID** (e.g. `U0123ABC456`), not their name or `@handle`
- To find someone's member ID:
  1. Open their profile in Slack (click their name/avatar)
  2. Click the **"..."** (more) menu
  3. Click **"Copy member ID"**
- If `slack_id` is missing or empty for someone, the bot logs a warning and falls back to posting their plain name (no ping)

### "Error sending email: Authentication failed"
- For Gmail: Make sure you generated an **app password**, not just your regular password
- For Outlook: Verify 2FA is enabled
- Try sending a test email from your email client first

### Bot doesn't run on schedule
- Keep the terminal/process running (don't close it)
- For persistent running, set up as a service (see section 8)

---

## Questions?

If something isn't working:
1. Run `python fika_bot.py test` to see immediate output
2. Check your `.env` file has all required variables
3. Verify Slack channel ID and email credentials
