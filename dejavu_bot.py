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
        "\n at " +
        rand_message.created_at.strftime("%Y-%m-%d %I:%M %p")
    )

    # if the arg is "text" just return the text as a message
    if arg == 'text':
        # handle the case where text is requested
        # /dejavu text
        await channel.send(text)
    elif arg == 'image':
        await create_and_send_image(200, text, channel)

async def create_and_send_image(width_height, text, channel):
    """
    Handle the case where an image is requested
    /dejavu image
    """
    FONT_SIZE = 14

    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/Courier.ttf",
        size=FONT_SIZE
    )

    # Convert dict_items to a list
    color_items = list(ImageColor.colormap.items())
    rand_color = choice(color_items)[0]
    img = Image.new('RGB', (width_height, width_height), color=rand_color)

    img_draw = ImageDraw.Draw(img)

    # text_width, text_height = img_draw.textsize(text, font=font)
    x_text = (width_height - FONT_SIZE) / 2
    y_text = (width_height - FONT_SIZE) / 2

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

bot.run(os.environ.get('DISCORD_TOKEN'))
