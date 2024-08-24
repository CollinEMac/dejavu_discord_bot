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
import enchant
import asyncio

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
    'people', 'into', 'year', 'your', 'good', 'some', 'could', 'these', 'give', 'day', 'most', 'us'
}

# Add this constant near the top of the file, with other constants
DICTIONARY = enchant.Dict("en_US")

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('dejavu_bot')

# Add these constants
LEADERBOARD_FILE = "leaderboard.json"
STREAK_BONUS = 1  # Points awarded for maintaining a streak

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
            "rounds": 0,
            "max_rounds": 5,
            "scores": defaultdict(int),
            "streak": defaultdict(int)
        }
        self.word_yapper = {
            "playing": False,
            "channel": None,
            "word": None,
            "top_user": None,
            "rounds": 0,
            "max_rounds": 5,
            "scores": defaultdict(int),
            "used_words": set(),
            "streak": defaultdict(int)
        }
        self.word_cache = self.load_word_cache()
        self.leaderboard = self.load_leaderboard()

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

    def load_leaderboard(self):
        logger.debug("Loading leaderboard from file")
        if os.path.exists(LEADERBOARD_FILE):
            with open(LEADERBOARD_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_leaderboard(self):
        logger.debug("Saving leaderboard to file")
        with open(LEADERBOARD_FILE, 'w') as f:
            json.dump(self.leaderboard, f)

    def update_leaderboard(self, game_type, scores):
        for player, score in scores.items():
            if player not in self.leaderboard:
                self.leaderboard[player] = {"total": 0, "whosaid": 0, "wordyapper": 0}
            self.leaderboard[player]["total"] += score
            self.leaderboard[player][game_type] += score
        self.save_leaderboard()

    async def setup_hook(self):
        logger.debug("Setting up command tree")
        await self.tree.sync()

bot = DejavuBot()

@bot.tree.command(name="dejavu", description="Find random messages from channel history or play games")
@app_commands.choices(choices=[
    app_commands.Choice(name="Text", value="text"),
    app_commands.Choice(name="Image", value="image"),
    app_commands.Choice(name="Guess who", value="whosaid"),
    app_commands.Choice(name="Word Yapper", value="wordyapper"),
])
@app_commands.describe(
    choices="Choose the game or output format",
    rounds="Number of rounds to play for games (default: 5, max: 10)",
    mercy_mode="Enable Mercy Mode (only for Who Said and Word Yapper)"
)
async def dejavu(
    inter: discord.Interaction, 
    choices: app_commands.Choice[str], 
    rounds: int = 5,
    mercy_mode: bool = False
):
    """Handle the /dejavu command."""
    logger.debug(f"Dejavu command invoked with choice: {choices.value}, rounds: {rounds}, mercy_mode: {mercy_mode}")
    
    if bot.whosaid["playing"] or bot.word_yapper["playing"]:
        await inter.response.send_message("A game is already in progress.")
        return

    if choices.value in ["whosaid", "wordyapper"]:
        if rounds < 1 or rounds > 10:
            await inter.response.send_message("Number of rounds must be between 1 and 10.")
            return
    elif rounds != 5:
        await inter.response.send_message("Number of rounds is only applicable for game modes.")
        return
    
    if choices.value not in ["whosaid", "wordyapper"] and mercy_mode:
        await inter.response.send_message("Mercy Mode is only available for Who Said and Word Yapper games.")
        return

    await inter.response.defer()

    channel = inter.channel
    if choices.value == "wordyapper":
        await start_word_yapper(channel, rounds, mercy_mode)
    elif choices.value == "whosaid":
        await start_whosaid(channel, rounds, mercy_mode)
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

async def create_and_send_response(rand_message: discord.Message, channel: discord.TextChannel, choice: Literal["text", "image"]):
    """Create and send the appropriate response based on the user's choice."""
    logger.debug(f"Creating response for choice: {choice}")
    text = f"{rand_message.author.name} said: \n{rand_message.content}\nat {rand_message.created_at.strftime('%Y-%m-%d %I:%M %p')}"

    if choice == "text":
        await channel.send(text)
    elif choice == "image":
        await create_and_send_image(text, channel)
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

async def start_whosaid(channel: discord.TextChannel, rounds: int, mercy_mode: bool):
    """Start a 'Who said' game with multiple rounds."""
    logger.debug(f"Starting 'Who said' game with {rounds} rounds, Mercy Mode: {mercy_mode}")
    bot.whosaid.update({
        "playing": True,
        "channel": channel.id,
        "rounds": 0,
        "max_rounds": rounds,
        "scores": defaultdict(int),
        "mercy_mode": mercy_mode
    })
    await play_whosaid_round(channel)

async def play_whosaid_round(channel: discord.TextChannel):
    """Play a single round of 'Who said' game."""
    created_at = channel.created_at
    end = datetime.now(timezone.utc)
    
    while True:
        rand_datetime = get_rand_datetime(created_at, end)
        async for rand_message in channel.history(limit=1, around=rand_datetime):
            if rand_message.content and (not bot.whosaid["mercy_mode"] or rand_message.author.id != 523214931533889598):
                bot.whosaid.update({
                    "author": rand_message.author.name,
                    "message": rand_message.content
                })
                bot.whosaid["rounds"] += 1
                await channel.send(f"Round {bot.whosaid['rounds']}/{bot.whosaid['max_rounds']}\nWho said: {rand_message.content}")
                
                # Add timeout
                try:
                    await asyncio.wait_for(wait_for_correct_answer(channel), timeout=60.0)
                except asyncio.TimeoutError:
                    await channel.send("No one answered in time. Game aborted.")
                    await end_whosaid_game(channel)
                return
        # If we didn't find a suitable message, we'll try again with a new random datetime

async def wait_for_correct_answer(channel: discord.TextChannel):
    while True:
        message = await bot.wait_for('message', check=lambda m: m.channel == channel and not m.author.bot and m.mentions)
        if message.mentions[0].name == bot.whosaid["author"]:
            await process_whosaid_guess(message)
            break
        else:
            await message.reply("Wrong! Try again.")

async def process_whosaid_guess(message: discord.Message):
    """Process a guess for the 'Who said' game."""
    points = 1
    bot.whosaid["scores"][message.author.name] += points
    await message.reply(f"Correct! You get {points} point(s).")
    await continue_or_end_whosaid(message.channel)

async def continue_or_end_whosaid(channel: discord.TextChannel):
    """Continue to the next round or end the 'Who said' game."""
    if bot.whosaid["rounds"] < bot.whosaid["max_rounds"]:
        await asyncio.sleep(2)  # Short delay before next round
        await play_whosaid_round(channel)
    else:
        await end_whosaid_game(channel)

async def end_whosaid_game(channel: discord.TextChannel):
    """End the 'Who said' game and display final scores."""
    scores = bot.whosaid["scores"]
    winner = max(scores, key=scores.get) if scores else None
    
    embed = Embed(title="Who Said - Game Over", color=discord.Color.gold())
    embed.add_field(name="Final Scores", value="\n".join(f"{player}: {score}" for player, score in scores.items()), inline=False)
    if winner:
        embed.add_field(name="Winner", value=f"🏆 {winner} with {scores[winner]} points!", inline=False)
    
    await channel.send(embed=embed)
    bot.update_leaderboard("whosaid", scores)
    await show_leaderboard_after_game(channel)
    bot.whosaid["playing"] = False

async def start_word_yapper(channel: discord.TextChannel, rounds: int, mercy_mode: bool):
    """Start a Word Yapper game with multiple rounds."""
    logger.debug(f"Starting Word Yapper game. Rounds: {rounds}, Mercy Mode: {mercy_mode}")
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
            if message.author.bot or (mercy_mode and message.author.id == 523214931533889598):
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

    bot.word_yapper.update({
        "playing": True,
        "channel": channel.id,
        "rounds": 0,
        "max_rounds": rounds,
        "scores": defaultdict(int),
        "mercy_mode": mercy_mode,
        "used_words": set()
    })

    await play_word_yapper_round(channel, word_counts, message_count)

async def play_word_yapper_round(channel: discord.TextChannel, word_counts, message_count):
    """Play a single round of Word Yapper game."""
    logger.debug("Playing Word Yapper round")
    common_words = [word for word, counts in word_counts.items() 
                    if sum(counts.values()) >= 1  # Said at least once
                    and word not in COMMON_WORDS_TO_EXCLUDE
                    and DICTIONARY.check(word)  # Check if it's a valid English word
                    and len(word) > 2  # Exclude very short words
                    and not word.isdigit()  # Exclude strings of just numbers
                    and word not in bot.word_yapper["used_words"]]

    if not common_words:
        logger.warning("Not enough words found with current criteria. Relaxing restrictions.")
        common_words = [word for word, counts in word_counts.items() 
                        if sum(counts.values()) >= 1
                        and word not in COMMON_WORDS_TO_EXCLUDE
                        and len(word) > 1
                        and not word.isdigit()
                        and word not in bot.word_yapper["used_words"]]

    if not common_words:
        await channel.send("Not enough unique words left to continue the game. Ending the game now.")
        await end_word_yapper_game(channel)
        return

    chosen_word = choice(common_words)
    bot.word_yapper["used_words"].add(chosen_word)
    top_user = max(word_counts[chosen_word], key=word_counts[chosen_word].get)

    bot.word_yapper.update({
        "word": chosen_word,
        "top_user": top_user
    })
    bot.word_yapper["rounds"] += 1

    logger.debug(f"Word Yapper round {bot.word_yapper['rounds']} started with word: {chosen_word}, top user: {top_user}")

    game_start_embed = Embed(
        title="Word Yapper",
        description=f"Word Yapper - Round {bot.word_yapper['rounds']}/{bot.word_yapper['max_rounds']}",
        color=discord.Color.green()
    )
    game_start_embed.add_field(name="Question", value=f"Who do you think said '{chosen_word}' most often?", inline=False)
    game_start_embed.set_footer(text="Mention the user you think said it most!")
    await channel.send(embed=game_start_embed)
    
    # Add timeout
    try:
        await asyncio.wait_for(wait_for_correct_word_yapper_answer(channel), timeout=60.0)
    except asyncio.TimeoutError:
        await channel.send("No one answered in time. Game aborted.")
        await end_word_yapper_game(channel)

async def wait_for_correct_word_yapper_answer(channel: discord.TextChannel):
    while True:
        message = await bot.wait_for('message', check=lambda m: m.channel == channel and not m.author.bot and m.mentions)
        if message.mentions[0].name == bot.word_yapper["top_user"]:
            await process_word_yapper_guess(message)
            break
        else:
            await message.reply("Wrong! Try again.")

async def process_word_yapper_guess(message: discord.Message):
    """Process a guess for the Word Yapper game."""
    points = 1
    bot.word_yapper["scores"][message.author.name] += points
    await message.reply(f"Correct! {bot.word_yapper['top_user']} said '{bot.word_yapper['word']}' most often. You get {points} point(s).")
    await continue_or_end_word_yapper(message.channel)

async def continue_or_end_word_yapper(channel: discord.TextChannel):
    """Continue to the next round or end the Word Yapper game."""
    if bot.word_yapper["rounds"] < bot.word_yapper["max_rounds"]:
        await asyncio.sleep(2)  # Short delay before next round
        await play_word_yapper_round(channel, bot.word_cache["data"], sum(sum(author_counts.values()) for author_counts in bot.word_cache["data"].values()))
    else:
        await end_word_yapper_game(channel)

async def end_word_yapper_game(channel: discord.TextChannel):
    """End the Word Yapper game and display final scores."""
    scores = bot.word_yapper["scores"]
    winner = max(scores, key=scores.get) if scores else None
    
    embed = Embed(title="Word Yapper - Game Over", color=discord.Color.gold())
    embed.add_field(name="Final Scores", value="\n".join(f"{player}: {score}" for player, score in scores.items()), inline=False)
    if winner:
        embed.add_field(name="Winner", value=f"🏆 {winner} with {scores[winner]} points!", inline=False)
    
    await channel.send(embed=embed)
    bot.update_leaderboard("wordyapper", scores)
    await show_leaderboard_after_game(channel)
    bot.word_yapper["playing"] = False

async def show_leaderboard_after_game(channel: discord.TextChannel):
    sorted_players = sorted(bot.leaderboard.items(), key=lambda x: x[1]["total"], reverse=True)
    
    embed = Embed(title="Updated Leaderboard", color=discord.Color.gold())
    for i, (player, scores) in enumerate(sorted_players[:5], 1):
        embed.add_field(
            name=f"{i}. {player}",
            value=f"Total: {scores['total']} | Who Said: {scores['whosaid']} | Word Yapper: {scores['wordyapper']}",
            inline=False
        )
    
    await channel.send(embed=embed)

@bot.tree.command(name="leaderboard", description="View the leaderboard")
async def show_leaderboard(inter: discord.Interaction):
    await inter.response.defer()
    
    sorted_players = sorted(bot.leaderboard.items(), key=lambda x: x[1]["total"], reverse=True)
    
    embed = Embed(title="Leaderboard", color=discord.Color.gold())
    for i, (player, scores) in enumerate(sorted_players[:10], 1):
        embed.add_field(
            name=f"{i}. {player}",
            value=f"Total: {scores['total']} | Who Said: {scores['whosaid']} | Word Yapper: {scores['wordyapper']}",
            inline=False
        )
    
    await inter.followup.send(embed=embed)

@bot.event
async def on_message(message: discord.Message):
    """Handle messages for the 'Who said' and 'Word Yapper' games."""
    if message.author.bot or not message.mentions:
        return

    logger.debug(f"Processing mention: {message.content[:20]}...")  # Log first 20 chars of message

    if bot.whosaid["playing"] and bot.whosaid["channel"] == message.channel.id:
        if message.mentions[0].name == bot.whosaid["author"]:
            await process_whosaid_guess(message)
        else:
            await message.reply("Wrong! Try again.")
    elif bot.word_yapper["playing"] and bot.word_yapper["channel"] == message.channel.id:
        if message.mentions[0].name == bot.word_yapper["top_user"]:
            await process_word_yapper_guess(message)
        else:
            await message.reply("Wrong! Try again.")

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name}")

logger.info("Starting DejavuBot")
bot.run(os.environ.get("DISCORD_TOKEN"))