# fika-bot

A small Slack bot for our team that keeps track of whose turn it is to bring fika (Swedish for coffee break with snacks/pastries). Every week it posts a reminder in Slack tagging the person and also sends them an email, then moves on to the next person in line.

Built this because I was tired of us forgetting whose turn it was and manually pinging people. Full disclosure: I built this mostly by having Claude write it for me and don't fully understand everything that's going on in `fika_bot.py`. It works and I've tested it, but if something breaks and looks weird, that's probably why.

## What it does

- Every Friday at 15:00 it picks the next person in the rotation, posts a message in the configured Slack channel, and emails them a reminder.
- People can manage the rotation themselves via slash commands in Slack, no need to edit the config by hand for most things:
  - `/add-me Full Name email@example.com` - joins the rotation
  - `/swap @user1 @user2` - swaps two people's spots
  - `/get-list [N]` - shows who's coming up
  - `/my-weeks [N]` - shows when you're next up
  - `/skip [N]` or `/skip A-B` - skips a reminder for a specific week (ISO week numbers)
  - `/undo` - undoes the last rotation step, in case someone accidentally triggers it

## Setup

I'm not including this repo's actual config since it has real names/emails/Slack IDs for people in the rotation. If you want to run this yourself:

1. `pip install -r requirements.txt`
2. Copy `env.template` to `.env` and fill in a Slack bot token, Slack app token, channel ID, and SMTP details for email.
3. Create a `fika_config.json` with your own people (see `QUICKSTART.md` for the format).
4. Run `python fika_bot.py test` to try a single rotation without waiting for the schedule.
5. Run `python fika_bot.py` to start it for real (runs the weekly job + listens for the slash commands above).

See `QUICKSTART.md` for the fast version and `SETUP.md` for the longer walkthrough, including setting up the Slack app itself.

## Notes to self / anyone else touching this

- `.env`, `fika_config.json` and `rotation_state.json` are gitignored on purpose since they hold tokens and people's personal info. Don't commit those.
- The schedule (day/time it runs) is hardcoded near the bottom of `fika_bot.py` if it ever needs to change.
