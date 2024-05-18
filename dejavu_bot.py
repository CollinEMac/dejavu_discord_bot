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

from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

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

@client.event
async def on_message(message):
    """
    This will run on every message...
    However, if the message is `/dejavu` we'll do stuff
    """
    if message.author == client.user or not message.content.startswith('/dejavu'):
        # Bot cannot reply to itself
        return

    channel = client.get_channel(os.environ.get('DISCORD_TOKEN'))
    created_at = channel.created_at
    rand_datetime = get_rand_datetime(created_at, datetime.now(tzinfo=timezone.utc))

    rand_message = channel.history(limit=1, around=rand_datetime)[0]

    if rand_message.content != '':
        create_and_send_image(rand_message, channel)

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

async def create_and_send_image(rand_message, channel):
    """
    Creates an image with the message author, content, and creation datetime
    with a random colored background
    """
    width = 100
    height = 100
    font = ImageFont.truetype("FreeMono.ttf", size=20)
    text = (
        rand_message.author +
        " said: " +
        rand_message.content +
        " at " +
        str(rand_message.created_at)
    )

    # the second element is the color name
    rand_color = choice(ImageColor.colormap.items())[0]
    img = Image.new('RGB', (width, height), color=rand_color)

    img_draw = ImageDraw.Draw(img)

    text_width, text_height = img_draw.textsize(text, font=font)
    x_text = (width - text_width) / 2
    y_text = (height - text_height) / 2

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
