# This example requires the 'message_content' intent.
import os

import discord

from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        # Bot cannot reply to itself
        return

    if message.content.startswith('/dejavu'):
        await message.channel.send('DEJA VU')

client.run(os.environ.get('DISCORD_TOKEN'))