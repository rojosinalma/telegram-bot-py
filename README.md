Telegram Bot
---

Simple Telegram Bot to ping every person in a channel by using `@everyone`

## Rationale

**Problem statement:**<br>
Telegram doesn't provide the list of participants of a channel by default.<br>

**Solution:**<br>
To be able to ping people we need their IDs first, so we capture them when they send any message and store them in a json file.<br>
<br>
Whenever someone writes @everyone, the bot will send a message with the list of people that it has stored in the json file.<br>

**NOTES:**
- The json file is structured to save people per channel, so you can use this bot in many groups/chats.
- The bot will try to ping their username, but not every user may have one, so it also tries their First Name. If all fails, it pings the plain ID.

## Run it

```bash
docker compose up -d --build
```
