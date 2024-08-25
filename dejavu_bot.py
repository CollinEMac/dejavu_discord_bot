"""
Discord bot that finds random messages in channel history and presents them in various formats.
Invoke with `/dejavu`
Arguments: text, image, whosaid
"""

import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from random import choice, randrange
from typing import Literal

from PIL import Image, ImageColor, ImageDraw, ImageFont
import discord
from discord import app_commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
VERY_DARK_COLORS = [
    "black", "darkblue", "darkmagenta", "darkslategrey",
    "indigo", "midnightblue", "navy", "purple",
]

class DejavuBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.whosaid = {
            "playing": False,
            "channel": None,
            "author": None,
            "message": None,
            "second_chance": False
        }

    async def setup_hook(self):
        await self.tree.sync()

bot = DejavuBot()

@bot.tree.command(name="dejavu", description="Dejavu bot")
@app_commands.choices(choices=[
    app_commands.Choice(name="Retrieve a random message.", value="text"),
    app_commands.Choice(name="Retrieve a random message and put it in an image.", value="image"),
    app_commands.Choice(name="Retrieve a random message and guess who said it.", value="whosaid"),
])
async def dejavu(inter: discord.Interaction, choices: app_commands.Choice[str]):
    """Handle the /dejavu command."""
    if bot.whosaid["playing"]:
        await inter.response.send_message("I'm still waiting for you to guess.")
        return

    await inter.response.defer()

    channel = inter.channel
    created_at = channel.created_at
    end = datetime.now(timezone.utc)
    rand_datetime = get_rand_datetime(created_at, end)

    async for rand_message in channel.history(limit=1, around=rand_datetime):
        if rand_message.content:
            await create_and_send_response(rand_message, channel, choices.value)
            break

    await inter.followup.send("Command processed.")

def get_rand_datetime(start: datetime, end: datetime) -> datetime:
    """Return a random datetime between two datetime objects."""
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = randrange(int_delta)
    return start + timedelta(seconds=random_second)

async def create_and_send_response(rand_message: discord.Message, channel: discord.TextChannel, choice: Literal["text", "image", "whosaid"]):
    """Create and send the appropriate response based on the user's choice."""
    text = f"{rand_message.author.name} said: \n{rand_message.content}\nat {rand_message.created_at.strftime('%Y-%m-%d %I:%M %p')}"

    if choice == "text":
        await channel.send(text)
    elif choice == "image":
        await create_and_send_image(text, channel)
    elif choice == "whosaid":
        await whosaid(rand_message, channel)
    else:
        await channel.send("Invalid Command.")

async def create_and_send_image(text: str, channel: discord.TextChannel):
    """Create and send an image with the message text."""
    font = ImageFont.truetype("./fonts/Courier.ttf", size=14)
    rand_color = choice(list(ImageColor.colormap.keys()))
    img = Image.new('RGB', (1000, 100), color=rand_color)
    img_draw = ImageDraw.Draw(img)

    text_color = (0, 0, 0) if rand_color not in VERY_DARK_COLORS else (255, 255, 255)
    img_draw.text((0, 25), text, font=font, fill=text_color)

    buffer = BytesIO()
    img.save(buffer, "png")
    buffer.seek(0)

    file = discord.File(buffer, filename="image.png")
    await channel.send(file=file)

async def whosaid(message: discord.Message, channel: discord.TextChannel):
    """Start a 'Who said' game."""
    bot.whosaid.update({
        "playing": True,
        "channel": channel.id,
        "second_chance": True,
        "author": message.author.name
    })
    await channel.send(f"Who said: {message.content}")

@bot.event
async def on_message(message: discord.Message):
    """Handle messages for the 'Who said' game."""
    if message.author.bot or bot.whosaid["channel"] != message.channel.id:
        return

    if (len(message.mentions) > 0 and
        message.mentions[0].name == bot.whosaid["author"] and
        bot.whosaid["playing"]):
        await message.reply("Correct.")
        bot.whosaid["playing"] = False
        bot.whosaid["second_chance"] = True
    elif bot.whosaid["playing"] and bot.whosaid["second_chance"]:
        await message.reply("Wrong! I'll give you one more chance.")
        bot.whosaid["second_chance"] = False
    elif bot.whosaid["playing"] and not bot.whosaid["second_chance"]:
        await message.reply(f"Wrong again! It was {bot.whosaid['author']}! Game over!")
        bot.whosaid["playing"] = False
        bot.whosaid["second_chance"] = True

# Run the bot
bot.run(os.environ.get("DISCORD_TOKEN"))