"""
This is all of the code for a discord bot that will find a random message in
your channel history and send it formatted in an image with a background

invoke with `/dejavu`
"""

import os
from datetime import datetime, timezone
from io import BytesIO
from random import choice, randrange

from PIL import Image, ImageColor, ImageDraw, ImageFont

import discord
from discord.ext import commands

from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='/', intents=intents)

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

@client.event
async def on_ready():
    """
    Print something on ready for testing
    """
    print(f'We have logged in as {client.user}')

@bot.command()
async def dejavu(ctx, arg):
    """
    On `/dejavu` grab a random message and post it
    """
    channel = ctx.channel
    created_at = channel.created_at
    rand_datetime = get_rand_datetime(created_at, datetime.now(tzinfo=timezone.utc))

    rand_message = channel.history(limit=1, around=rand_datetime)[0]

    if rand_message.content != '':
        create_and_send_response(rand_message, channel, arg)

def get_rand_datetime(start, end):
    """
    https://stackoverflow.com/questions/553303/generate-a-random-date-between-two-other-dates

    This function will return a random datetime between two datetime 
    objects.
    """
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = randrange(int_delta)
    return start + datetime.timedelta(seconds=random_second)

def create_and_send_response(rand_message, channel, arg):
    """
    Creates an image with the message author, content, and creation datetime
    with a random colored background
    """
    font = ImageFont.truetype("FreeMono.ttf", size=20)
    text = (
        rand_message.author +
        " said: \n" +
        rand_message.content +
        "\n at " +
        str(rand_message.created_at)
    )

    # if the arg is "text" just return the text as a message
    if arg == 'text':
        # handle the case where text is requested
        # /dejavu text
        channel.send(text)
    elif arg == 'image':
        create_and_send_image(100, text, font, channel)

async def create_and_send_image(width_height, text, font, channel):
    """
    Handle the case where an image is requested
    /dejavu image
    """

    # the second element is the color name
    rand_color = choice(ImageColor.colormap.items())[0]
    img = Image.new('RGB', (width_height, width_height), color=rand_color)

    img_draw = ImageDraw.Draw(img)

    text_width, text_height = img_draw.textsize(text, font=font)
    x_text = (width_height - text_width) / 2
    y_text = (width_height - text_height) / 2

    if rand_color not in VERY_DARK_COLORS:
        img_draw.text((x_text, y_text), text, font=font, fill=(0, 0, 0))
    else:
        img_draw.text((x_text, y_text), text, font=font, fill=(255, 255, 255))

    # Save the image to a BytesIO buffer
    buffer = BytesIO()
    img.save(buffer, 'png')
    buffer.seek(0)  # Reset the buffer pointer to the beginning

    file = discord.File(buffer, filename='image.png')
    await channel.send(file=file)

client.run(os.environ.get('DISCORD_TOKEN'))
