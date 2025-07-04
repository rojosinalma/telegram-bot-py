Telegram Bot
---

Simple Telegram Bot to ping every person in a channel by using `@everyone`

## Rationale

**Problem statement:**<br>
Telegram doesn't have an `@everyone` mention. <br>

**Solution:**<br>
To be able to ping people we need their IDs first because Telegram doesn't give the list of participants of a chat by default, so we capture them when they send any message, store them in a json file and ask if they want to subscribe to mentions of `@everyone`.<br>
<br>
Whenever someone writes `@everyone`, the bot will send a message with the list of people that it has stored in the json file.<br>

**NOTES:**
- The json file is structured to save people per channel, so you can use this bot in many groups/chats.
- The bot will try to ping their username, but not every user may have one, so it also tries their First Name. If all fails, it pings the plain ID.

## Use it<br>
- When people join a channel or chat for the first time after the bot was added, the bot will ask if they want to `@subscribe` to notifications.
- They can leave the notifications with `@unsubscribe`.
- The bot will automatically remove people from the list if they kicked or leave the channel.

## Run it

```bash
docker compose up -d --build
```
