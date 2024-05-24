"""
This is all of the code for a discord bot that will find a random message in
your channel history and send it in either text or image format and there is also
a game where you have to guess who said the message

Invoke with `/dejavu`
Arguments: text, image, whosaid
"""

import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from random import choices, randrange

from PIL import Image, ImageColor, ImageDraw, ImageFont

import discord
from discord import app_commands

# Load .env file
from dotenv import load_dotenv

load_dotenv()

# Set up bot
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# Set up slash commands
tree = app_commands.CommandTree(bot)

# Colors for the image mode.
VERY_DARK_COLORS = [
    "black",
    "darkblue",
    "darkmagenta",
    "darkslategrey",
    "indigo",
    "midnightblue",
    "navy",
    "purple",
]

# Initalize whosaid game variables
bot.whosaid = {}
bot.whosaid["playing"] = False
bot.whosaid["channel"] = None
bot.whosaid["author"] = None
bot.whosaid["message"] = None
bot.whosaid["second_chance"] = False

# Command setup and argument definition.
@tree.command(
    name="dejavu",
    description="Devjavu bot",
)
@app_commands.choices(
    choices=[
        app_commands.Choice(name="Retrieve a random message.", value="text"),
        app_commands.Choice(
            name="Retrieve a random message and put it in an image.", value="image"
        ),
        app_commands.Choice(
            name="Retrieve a random message and you must guess who said it by mentioning them.",
            value="whosaid",
        ),
    ]
)
async def dejavu(inter, arg: app_commands.Choice[str]):
    """
    On `/dejavu text|image|whosaid` grab a random message and post it in the chosen format.
    """

    # If a game of whosaid is already being played, do not continue.
    if bot.whosaid["playing"] is True:
        await inter.response.send_message("I'm still waiting for you to guess.")
        return

    # Send a message to confirm recipt of command.
    # Else the bot will error.
    # TODO: Find a way to run a command without
    # something like this
    await inter.response.send_message("Command sent.")

    # Get a random datetime between now and when the channel was created
    channel = inter.channel
    created_at = channel.created_at
    end = datetime.utcnow().replace(tzinfo=timezone.utc)
    rand_datetime = get_rand_datetime(created_at, end)

    # Fetch a message using the random datetime
    # limit=1 so we only get one message (we could change this later to add more?)
    async for rand_message in channel.history(limit=1, around=rand_datetime):
        if rand_message.content != "":
            await create_and_send_response(rand_message, channel, arg.value)
            break


def get_rand_datetime(start, end):
    """
    https://stackoverflow.com/questions/553303/generate-a-random-date-between-two-other-dates

    This function will return a random datetime between two datetime objects.
    """
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = randrange(int_delta)
    return start + timedelta(seconds=random_second)


async def create_and_send_response(rand_message, channel, choice):

    text = (
        rand_message.author.name
        + " said: \n"
        + rand_message.content
        + "\nat "
        + rand_message.created_at.strftime("%Y-%m-%d %I:%M %p")
    )

    if choice == "text":
        # Sends the random message with the message author, content,
        # and creation datetime
        # `/dejavu text`
        await channel.send(text)
    elif choice == "image":
        await create_and_send_image(text, channel)
    elif choice == "whosaid":
        # if the choice is whosaid, pass the rand_message and channel to whosaid()
        await whosaid(rand_message, channel)
    else:
        await channel.send("Invalid Command.")


async def create_and_send_image(text, channel):
    """
    `/dejavu image`
    """
    font = ImageFont.truetype("./fonts/Courier.ttf", size=14)  # debian path

    # Convert dict_items to a list
    color_items = list(ImageColor.colormap.items())

    rand_color = choice(color_items)[0]
    img = Image.new('RGB', (1000, 100), color=rand_color)

    img_draw = ImageDraw.Draw(img)

    if rand_color not in VERY_DARK_COLORS:
        img_draw.text((0, 25), text, font=font, fill=(0, 0, 0))
    else:
        img_draw.text((0, 25), text, font=font, fill=(255, 255, 255))

    # Save the image to a BytesIO buffer
    buffer = BytesIO()
    img.save(buffer, "png")
    buffer.seek(0)  # Reset the buffer pointer to the beginning

    file = discord.File(buffer, filename="image.png")
    await channel.send(file=file)


async def whosaid(message, channel):
    """
    A game where a message is presented and the user has to guess who wrote it
    by mentioning the user. They get 2 guesses before game over.
    /dejavu whosaid
    """

    # Set inital game variables and start the game
    bot.whosaid["playing"] = True
    bot.whosaid["channel"] = message.channel.id
    bot.whosaid["second_chance"] = True
    bot.whosaid["author"] = message.author.name
    await channel.send("Who said: " + message.content)


@bot.event
async def on_message(message):
    """
    Check if the ID in the response matches the
    ID of the user whose message got fetched by
    the whosaid game and make sure we're in the
    channel the game started in.

    Then, the game logic runs.
    """

    if message.author.bot == True or bot.whosaid["channel"] != message.channel.id:
        return

    # This if statement only returns true if whosaid() has run before this
    if (
        len(message.mentions) > 0
        and message.mentions[0].name == bot.whosaid["author"]
        and bot.whosaid["playing"] is True
    ):
        await message.reply("Correct.")
        bot.whosaid["playing"] = False
        bot.whosaid["second_chance"] = True
    elif bot.whosaid["playing"] is True and bot.whosaid["second_chance"] is True:
        await message.reply("Wrong! I'll give you one more chance.")
        bot.whosaid["second_chance"] = False
    elif bot.whosaid["playing"] is True and bot.whosaid["second_chance"] is False:
        await message.reply(
            "Wrong again! It was " + bot.whosaid["author"] + "! Game over!."
        )
        bot.whosaid["playing"] = False
        bot.whosaid["second_chance"] = True


# Sync slash command to Discord.
@bot.event
async def on_ready():
    """
    on_ready() syncs and updates the slash commands on the Discord server.
    """
    await tree.sync()


# Run bot and load the Discord bot token from a `.env` file.
bot.run(os.environ.get("DISCORD_TOKEN"))
