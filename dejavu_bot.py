"""
This is all of the code for a discord bot that will find a random message in
your channel history and send it formatted in an image with a background

invoke with `/dejavu`
"""

import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from random import choice, randrange

from PIL import Image, ImageColor, ImageDraw, ImageFont

import discord
from discord import app_commands

from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

# Set up slash commands
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


VERY_DARK_COLORS = [
    'black',
    'darkblue',
    'darkmagenta',
    'darkslategrey',
    'indigo',
    'midnightblue',
    'navy',
    'purple'
]

bot.who_said_context = None

@tree.command(
    name="dejavu",
    description="Devjavu bot",
)
async def dejavu(interaction: discord.Interaction, arg: str):
    """
    On `/dejavu` grab a random message and post it
    """

    await interaction.response.send_message('Command sent.')    
    
    channel = interaction.channel
    created_at = channel.created_at
    end = datetime.utcnow().replace(tzinfo=timezone.utc)
    rand_datetime = get_rand_datetime(created_at, end)

    # limit=1 so we only get one message (we could change this later to add more?)
    async for rand_message in channel.history(limit=1, around=rand_datetime):
        if rand_message.content != '':
            await create_and_send_response(rand_message, channel, arg)
            break

def get_rand_datetime(start, end):
    """
    https://stackoverflow.com/questions/553303/generate-a-random-date-between-two-other-dates

    This function will return a random datetime between two datetime 
    objects.
    """
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = randrange(int_delta)
    return start + timedelta(seconds=random_second)

async def create_and_send_response(rand_message, channel, arg):
    """
    Creates an image with the message author, content, and creation datetime
    with a random colored background
    """
    text = (
        rand_message.author.name +
        " said: \n" +
        rand_message.content +
        "\nat " +
        rand_message.created_at.strftime("%Y-%m-%d %I:%M %p")
    )

    if arg == 'image':
        await create_and_send_image(text, channel)
    elif arg == 'whosaid':
        # if the arg is whosaid, store the message details in the bot's who_said_context
        bot.who_said_context = {
            'author_id': rand_message.author.id,
            'content': rand_message.content,
            'channel': channel
        }
        await who_said(rand_message.content, channel)
    else:
        # /dejavu text
        # Just return the random message as text
        await channel.send(text)

async def create_and_send_image(text, channel):
    """
    Handle the case where an image is requested
    /dejavu image
    """
    font = ImageFont.truetype(
        "./fonts/Courier.ttf", # debian path
        size=14
    )

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
    img.save(buffer, 'png')
    buffer.seek(0)  # Reset the buffer pointer to the beginning

    file = discord.File(buffer, filename='image.png')
    await channel.send(file=file)

async def who_said(who_said_content, channel):
    """
    Ask who said who_said_content and store the context
    in the bot's who_said_context
    """
    await channel.send('Who said: ' + who_said_content)

@bot.event
async def on_message(message):
    """
    check if the id in the response matches the
    id if the whosaid game is being played
    """
    if message.author == bot.user:
        return

    print(len(message.mentions))
    print(message.mentions[0].id)

    # this if statement only returns true if who_said has run before this
    if len(message.mentions) > 0 and bot.who_said_context is not None:
        print("first if triggered")
        if message.mentions[0].id == bot.who_said_context['author_id']:
            print('2nd if triggered')
            await bot.who_said_context['channel'].send('Correct.')
            bot.who_said_context = None

# Sync slash command to Discord
@bot.event
async def on_ready():
    await tree.sync()

bot.run(os.environ.get('DISCORD_TOKEN'))
