import os
import re
import json
from datetime import datetime, timezone

import discord
import gspread
from google.oauth2.service_account import Credentials


DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
GOOGLE_CREDENTIALS_JSON = os.environ["GOOGLE_CREDENTIALS_JSON"]


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1


latest_ball = None
match_conditions = {
    "pitch": "",
    "weather": "",
}


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def clean(text: str) -> str:
    return (text or "").replace("**", "").strip()


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")


@client.event
async def on_message(message):
    global latest_ball, match_conditions

    if message.channel.id != CHANNEL_ID:
        return

    if message.author == client.user:
        return

    content = message.content or ""
    embed_description = ""

    if message.embeds:
        embed = message.embeds[0]
        embed_description = embed.description or ""

    # Match card: Pitch + Weather
    pitch_match = re.search(r"Pitch:\s*([\s\S]*?)\s*Weather:", embed_description, re.I)
    weather_match = re.search(r"Weather:\s*([\s\S]*?)\s*Expires:", embed_description, re.I)

    if pitch_match or weather_match:
        match_conditions = {
            "pitch": clean(pitch_match.group(1)) if pitch_match else "",
            "weather": clean(weather_match.group(1)) if weather_match else "",
        }
        print("Stored match conditions:", match_conditions)
        return

    # Delivery message
    delivery_match = re.search(
        r"A\s+\*\*(.*?)\*\*\s+is coming at\s+(.*?)\s+at\s+\*\*([\d.]+)\s+kmph\*\*!",
        content,
        re.I,
    )

    if delivery_match:
        latest_ball = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": message.channel.name,
            "batter": clean(delivery_match.group(2)),
            "ball_type": clean(delivery_match.group(1)),
            "speed": clean(delivery_match.group(3)),
            "raw_delivery": content,
        }
        print("Stored delivery:", latest_ball)
        return

    # Outcome embed
    outcome_text = embed_description

    outcome_match = re.search(
        r"^(.*?)\s+\*\*(.*?)\*\*\s+the\s+(.*?)!",
        outcome_text,
        re.I,
    )

    if outcome_match and latest_ball:
        commentary = clean(outcome_text.replace(outcome_match.group(0), ""))

        row = [
            latest_ball["timestamp"],
            "",  # Match ID blank
            latest_ball["channel"],
            latest_ball["batter"],
            latest_ball["ball_type"],
            latest_ball["speed"],
            clean(outcome_match.group(2)),
            commentary,
            latest_ball["raw_delivery"],
            outcome_text,
            match_conditions.get("pitch", ""),
            match_conditions.get("weather", ""),
        ]

        sheet.append_row(row, value_input_option="USER_ENTERED")
        print("Logged row:", row)

        latest_ball = None


client.run(DISCORD_TOKEN)
