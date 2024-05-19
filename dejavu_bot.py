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
from discord.ext import commands

from dotenv import load_dotenv
load_dotenv()

import threading
from threading import Thread

import time

intents = discord.Intents.default()
intents.message_content = True

# client = discord.Client(intents=intents)
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


@bot.command()
async def dejavu(ctx, arg):
    """
    On `/dejavu` grab a random message and post it
    """
    channel = ctx.channel
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

    # if the arg is "text" just return the text as a message
    if arg == 'text':
        # handle the case where text is requested
        # /dejavu text
        await channel.send(text)
    elif arg == 'image':
        await create_and_send_image(text, channel)
    elif arg == 'whosaid':
        who_said_id = rand_message.author.id
        print(rand_message.author.id)
        who_said_content = rand_message.content
        await who_said(who_said_id, who_said_content, channel)

async def create_and_send_image(text, channel):
    """
    Handle the case where an image is requested
    /dejavu image
    """
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/Courier.ttf",
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

async def who_said(who_said_id, who_said_content, channel):
    print(who_said_id)
    await channel.send('Who said: ' + who_said_content)
    who_said_response_id = ''
    while True:
        if who_said_response_id == who_said_id:
            channel.send('Correct.')
        else:
            time.sleep(1)

WHO_SAID_THREAD = Thread(target = who_said)
WHO_SAID_THREAD.run()

@bot.event
async def on_message(message):
    print('on_message called')
    while WHO_SAID_THREAD.is_alive():
        print('ydsfgdf')
        who_said_response_id = message.mentions.id
        print(who_said_response_id)

bot.run(os.environ.get('DISCORD_TOKEN'))
