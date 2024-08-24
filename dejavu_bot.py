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
import re
from collections import defaultdict, Counter
import time
import discord
from discord import app_commands, Embed
import logging
import json
import enchant  # Add this import at the top of the file

from PIL import Image, ImageColor, ImageDraw, ImageFont

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
VERY_DARK_COLORS = [
    "black", "darkblue", "darkmagenta", "darkslategrey",
    "indigo", "midnightblue", "navy", "purple",
]

# Add this constant for the cache file path
CACHE_FILE_PATH = "word_cache.json"

# Add this constant near the top of the file, with other constants
COMMON_WORDS_TO_EXCLUDE = {
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
    'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
    'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
    'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
    'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me',
    'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know', 'take',
    'people', 'into', 'year', 'your', 'good', 'some', 'could', 'them', 'see', 'other',
    'than', 'then', 'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
    'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first', 'well', 'way',
    'even', 'new', 'want', 'because', 'any', 'these', 'give', 'day', 'most', 'us'
}

# Add this constant near the top of the file, with other constants
DICTIONARY = enchant.Dict("en_US")

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('dejavu_bot')

class DejavuBot(discord.Client):
    def __init__(self):
        logger.debug("Initializing DejavuBot")
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
        self.word_yapper = {
            "playing": False,
            "channel": None,
            "word": None,
            "top_user": None,
            "second_chance": False,
            "meme_mode": False
        }
        self.word_cache = self.load_word_cache()

    def load_word_cache(self):
        logger.debug("Loading word cache from file")
        if os.path.exists(CACHE_FILE_PATH):
            with open(CACHE_FILE_PATH, 'r') as f:
                cache = json.load(f)
            # Convert defaultdict(int) back from JSON
            cache['data'] = defaultdict(lambda: defaultdict(int), {k: defaultdict(int, v) for k, v in cache['data'].items()})
            return cache
        else:
            return {
                "data": defaultdict(lambda: defaultdict(int)),
                "last_update": 0,
                "cache_duration": 3600
            }

    def save_word_cache(self):
        logger.debug("Saving word cache to file")
        cache_to_save = {
            "data": {k: dict(v) for k, v in self.word_cache['data'].items()},
            "last_update": self.word_cache['last_update'],
            "cache_duration": self.word_cache['cache_duration']
        }
        with open(CACHE_FILE_PATH, 'w') as f:
            json.dump(cache_to_save, f)

    async def setup_hook(self):
        logger.debug("Setting up command tree")
        await self.tree.sync()

bot = DejavuBot()

@bot.tree.command(name="dejavu", description="Find random messages from channel history")
@app_commands.choices(choices=[
    app_commands.Choice(name="Text", value="text"),
    app_commands.Choice(name="Image", value="image"),
    app_commands.Choice(name="Guess who", value="whosaid"),
    app_commands.Choice(name="Word Yapper", value="wordyapper"),
])
@app_commands.describe(
    choices="Choose the game or output format",
    meme="Use meme mode for Word Yapper (more common words)"
)
async def dejavu(inter: discord.Interaction, choices: app_commands.Choice[str], meme: bool = False):
    """Handle the /dejavu command."""
    logger.debug(f"Dejavu command invoked with choice: {choices.value}, meme: {meme}")
    if bot.whosaid["playing"] or bot.word_yapper["playing"]:
        await inter.response.send_message("A game is already in progress.")
        return

    await inter.response.defer()

    channel = inter.channel
    if choices.value == "wordyapper":
        await start_word_yapper(channel, meme)
    else:
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
    logger.debug(f"Generating random datetime between {start} and {end}")
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = randrange(int_delta)
    return start + timedelta(seconds=random_second)

async def create_and_send_response(rand_message: discord.Message, channel: discord.TextChannel, choice: Literal["text", "image", "whosaid"]):
    """Create and send the appropriate response based on the user's choice."""
    logger.debug(f"Creating response for choice: {choice}")
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
    logger.debug("Creating and sending image")
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
    logger.debug("Starting 'Who said' game")
    bot.whosaid.update({
        "playing": True,
        "channel": channel.id,
        "second_chance": True,
        "author": message.author.name
    })
    await channel.send(f"Who said: {message.content}")

async def start_word_yapper(channel: discord.TextChannel, meme_mode: bool):
    """Start a Word Yapper game."""
    logger.debug(f"Starting Word Yapper game. Meme mode: {meme_mode}")
    current_time = time.time()
    
    # Check if cache is valid
    if current_time - bot.word_cache["last_update"] > bot.word_cache["cache_duration"]:
        logger.debug("Cache invalid, updating word cache")
        loading_embed = Embed(
            title="Word Yapper",
            description="Updating word cache... This may take a moment.",
            color=discord.Color.blue()
        )
        loading_embed.set_footer(text="Please wait while I analyze the channel history.")
        loading_message = await channel.send(embed=loading_embed)

        word_counts = defaultdict(lambda: defaultdict(int))
        message_count = 0
        async for message in channel.history(limit=10000):  # Adjust limit as needed
            if message.author.bot:
                continue
            words = re.findall(r'\w+', message.content.lower())
            for word in words:
                word_counts[word][message.author.name] += 1
            message_count += 1
        
        bot.word_cache["data"] = word_counts
        bot.word_cache["last_update"] = current_time
        bot.save_word_cache()  # Save cache after updating

        await loading_message.delete()
    else:
        logger.debug("Using existing word cache")
        word_counts = bot.word_cache["data"]
        message_count = sum(sum(author_counts.values()) for author_counts in word_counts.values())

    if meme_mode:
        common_words = [word for word, counts in word_counts.items() 
                        if sum(counts.values()) > message_count * 0.01 
                        and word not in COMMON_WORDS_TO_EXCLUDE
                        and len(word) > 2  # Exclude very short words
                        and not word.isdigit()]  # Exclude strings of just numbers
    else:
        common_words = [word for word, counts in word_counts.items() 
                        if sum(counts.values()) >= 1  # Said at least once
                        and word not in COMMON_WORDS_TO_EXCLUDE
                        and DICTIONARY.check(word)  # Check if it's a valid English word
                        and len(word) > 2  # Exclude very short words
                        and not word.isdigit()]  # Exclude strings of just numbers

    if not common_words:
        await channel.send("Not enough data to start a game. Try again later.")
        return

    chosen_word = choice(common_words)
    top_user = max(word_counts[chosen_word], key=word_counts[chosen_word].get)

    bot.word_yapper.update({
        "playing": True,
        "channel": channel.id,
        "word": chosen_word,
        "top_user": top_user,
        "second_chance": True,
        "meme_mode": meme_mode
    })

    logger.debug(f"Word Yapper game started with word: {chosen_word}, top user: {top_user}")

    mode = "meme words" if meme_mode else "regular words"
    game_start_embed = Embed(
        title="Word Yapper",
        description=f"Word Yapper ({mode}) has started!",
        color=discord.Color.green()
    )
    game_start_embed.add_field(name="Question", value=f"Who do you think said '{chosen_word}' most often?", inline=False)
    game_start_embed.set_footer(text="Mention the user you think said it most!")
    await channel.send(embed=game_start_embed)

@bot.event
async def on_message(message: discord.Message):
    """Handle messages for the 'Who said' and 'Word Yapper' games."""
    if message.author.bot or not message.mentions:
        return

    logger.debug(f"Processing mention: {message.content[:20]}...")  # Log first 20 chars of message

    if bot.whosaid["playing"] and bot.whosaid["channel"] == message.channel.id:
        logger.debug("Processing 'Who said' game message")
        if message.mentions[0].name == bot.whosaid["author"]:
            await message.reply("Correct!")
            bot.whosaid["playing"] = False
        elif bot.whosaid["second_chance"]:
            await message.reply("Wrong! I'll give you one more chance.")
            bot.whosaid["second_chance"] = False
        else:
            await message.reply(f"Wrong again! It was {bot.whosaid['author']}! Game over!")
            bot.whosaid["playing"] = False

    elif bot.word_yapper["playing"] and bot.word_yapper["channel"] == message.channel.id:
        logger.debug("Processing Word Yapper game message")
        if message.mentions[0].name == bot.word_yapper["top_user"]:
            await message.reply(f"Correct! {bot.word_yapper['top_user']} said '{bot.word_yapper['word']}' most often.")
            bot.word_yapper["playing"] = False
        elif bot.word_yapper["second_chance"]:
            await message.reply("Wrong! I'll give you one more chance.")
            bot.word_yapper["second_chance"] = False
        else:
            await message.reply(f"Wrong again! It was {bot.word_yapper['top_user']}! Game over!")
            bot.word_yapper["playing"] = False

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name}")

logger.info("Starting DejavuBot")
bot.run(os.environ.get("DISCORD_TOKEN"))