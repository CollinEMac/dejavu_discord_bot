"""
This is all of the code for a discord bot that will find a random message in
your channel history and send it formatted in an image with a background

invoke with `/dejavu`
"""

import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from random import choices, randrange

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

bot.who_said_playing = False
bot.who_said_attempts = 2
bot.who_said_user = None

@tree.command(
    name="dejavu",
    description="Devjavu bot",
)
@app_commands.choices(choices=[
    app_commands.Choice(name="Retrieve a random message.", value="text"),
    app_commands.Choice(name="Retrieve a random message and put it in an image.", value="image"),
    app_commands.Choice(name="Retrieve a random message and you must guess who said it by mentioning them.", value="whosaid"),
    ])
async def dejavu(inter, choices: app_commands.Choice[str]):
    """
    On `/dejavu` grab a random message and post it
    """
    if bot.who_said_playing == True:
        await inter.response.send_message('I\'m still waiting for you to guess.')
        return

    await inter.response.send_message('Command sent.')    

    channel = inter.channel
    created_at = channel.created_at
    end = datetime.utcnow().replace(tzinfo=timezone.utc)
    rand_datetime = get_rand_datetime(created_at, end)

    # limit=1 so we only get one message (we could change this later to add more?)
    async for rand_message in channel.history(limit=1, around=rand_datetime):
        if rand_message.content != '':
            await create_and_send_response(rand_message, channel, choices.value)
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

async def create_and_send_response(rand_message, channel, choice):
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

    if choice == 'text':
        await channel.send(text)
    elif choice == 'image':
        await create_and_send_image(text, channel)
    elif choice == 'whosaid':
        # if the arg is whosaid, pass the rand_message.content to who_said
        await who_said(rand_message, channel)
    else:
        await channel.send('Invalid Command.')

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
    
    rand_color_name = choices(list(ImageColor.colormap.keys()))[0]
    rand_color = ImageColor.getrgb(rand_color_name)
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

async def who_said(who_said_message, channel):
    """
    Set who_said_playing to true so the if statement in on_message gets triggered
    """
    bot.who_said_playing = True
    bot.who_said_user = who_said_message.author.name
    await channel.send('Who said: ' + who_said_message.content)

@bot.event
async def on_message(message):
    """
    check if the id in the response matches the
    id if the whosaid game is being played
    """
    if message.author == bot.user:
        return

    print(bot.who_said_playing)
    
    # this if statement only returns true if who_said has run before this
    if len(message.mentions) > 0 and bot.who_said_playing == True and bot.who_said_attempts > 0:
        await message.reply('Correct.')
        bot.who_said_playing = False
        bot.who_said_attempts = 2
    elif bot.who_said_playing == True and bot.who_said_attempts == 1:
        await message.reply('Wrong! I\'ll give you one more chance.')
        bot.who_said_attempts = 0
    else:
        await message.reply('Wrong again! It was ' + bot.who_said_user + '! Game over!.')
        bot.who_said_playing = False
        bot.who_said_attempts = 2

# Sync slash command to Discord
@bot.event
async def on_ready():
    await tree.sync()

bot.run(os.environ.get('DISCORD_TOKEN'))
