"""
Discord bot that finds random messages in channel history and presents them in various formats.
Invoke with `/dejavu`
Arguments: text, image, whosaid
"""

import os
from datetime import datetime, timedelta, timezone
from random import choice, randrange
from typing import Literal
import re
from collections import defaultdict
import time
import discord
from discord import app_commands, Embed
import logging
import json
import enchant
import asyncio
from io import BytesIO
import aiohttp
from discord.ui import View, Button

from dotenv import load_dotenv

from commands.image import BACKGROUNDS, create_and_send_image, is_blacklisted

# Load environment variables
load_dotenv()

###
### Constants
###

VERY_DARK_COLORS = [
    "black", "darkblue", "darkmagenta", "darkslategrey",
    "indigo", "midnightblue", "navy", "purple",
]

CACHE_FILE_PATH = "word_cache.json"

COMMON_WORDS_TO_EXCLUDE = {
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
    'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
    'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
    'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
    'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me',
    'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know', 'take',
    'people', 'into', 'year', 'your', 'good', 'some', 'could', 'these', 'give', 'day', 'most', 'us'
}

DICTIONARY = enchant.Dict("en_US")

LEADERBOARD_FILE = "leaderboard.json"
HALL_OF_FAME_FILE = "hall_of_fame.json"
STREAK_BONUS = 1  # Points awarded for maintaining a streak

MERCY_USER_ID = int(os.environ.get("MERCY_USER_ID", 0))

MAX_RETRIES = 3

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
        self.hall_of_fame = self.load_hall_of_fame()

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

    def load_hall_of_fame(self):
        logger.debug("Loading Hall of Fame from file")
        if os.path.exists(HALL_OF_FAME_FILE):
            try:
                with open(HALL_OF_FAME_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Error decoding Hall of Fame JSON, starting fresh")
                return {}
        return {}

    def save_hall_of_fame(self):
        logger.debug("Saving Hall of Fame to file")
        with open(HALL_OF_FAME_FILE, 'w') as f:
            json.dump(self.hall_of_fame, f)

    async def setup_hook(self):
        logger.debug("Setting up command tree")
        await self.tree.sync()

bot = DejavuBot()

dejavu = app_commands.Group(name="dejavu", description="Dejavu commands and games")

@dejavu.command(name="text", description="Get a random message as text")
async def dejavu_text(inter: discord.Interaction):
    """Handle the /dejavu text command."""
    logger.debug("Dejavu text command invoked")
    await inter.response.defer()
    await process_dejavu_command(inter, "text")

@dejavu.command(name="image", description="Get a random message as an image")
@app_commands.describe(background="Choose the background image (default: iphone)")
@app_commands.choices(background=[
    app_commands.Choice(name=choice, value=choice) for choice in BACKGROUNDS
])
async def dejavu_image(
    inter: discord.Interaction,
    background: str
):
    """Handle the /dejavu image command."""
    logger.debug(f"Dejavu image command invoked with background: {background}")
    await inter.response.defer()
    await process_dejavu_command(inter, "image", background)

@dejavu.command(name="whosaid", description="Play 'Who Said' game")
@app_commands.describe(
    rounds="Number of rounds to play (default: 5, max: 10)",
    mercy_mode="Enable Mercy Mode"
)
async def whosaid(
    inter: discord.Interaction, 
    rounds: int = 5,
    mercy_mode: bool = False
):
    """Handle the /dejavu whosaid command."""
    logger.debug(f"Who Said game invoked with rounds: {rounds}, mercy_mode: {mercy_mode}")
    
    if bot.whosaid["playing"] or bot.word_yapper["playing"]:
        await inter.response.send_message("A game is already in progress.")
        return

    if rounds < 1 or rounds > 10:
        await inter.response.send_message("Number of rounds must be between 1 and 10.")
        return

    await inter.response.defer()
    await start_whosaid(inter.channel, rounds, mercy_mode)
    await inter.followup.send("Who Said game started.")

@dejavu.command(name="wordyapper", description="Play 'Word Yapper' game")
@app_commands.describe(
    rounds="Number of rounds to play (default: 5, max: 10)",
    mercy_mode="Enable Mercy Mode"
)
async def wordyapper(
    inter: discord.Interaction, 
    rounds: int = 5,
    mercy_mode: bool = False
):
    """Handle the /dejavu wordyapper command."""
    logger.debug(f"Word Yapper game invoked with rounds: {rounds}, mercy_mode: {mercy_mode}")
    
    if bot.whosaid["playing"] or bot.word_yapper["playing"]:
        await inter.response.send_message("A game is already in progress.")
        return

    if rounds < 1 or rounds > 10:
        await inter.response.send_message("Number of rounds must be between 1 and 10.")
        return

    await inter.response.defer()
    await start_word_yapper(inter.channel, rounds, mercy_mode)
    await inter.followup.send("Word Yapper game started.")

bot.tree.add_command(dejavu)

async def process_dejavu_command(inter: discord.Interaction, format: Literal["text", "image"], background: str = "japmic"):
    """Process the dejavu command for text and image formats."""
    logger.debug(f"Processing dejavu command. Format: {format}, Background: {background}")
    channel = inter.channel
    created_at = channel.created_at
    end = datetime.now(timezone.utc)
    
    try:
        for _ in range(MAX_RETRIES):
            logger.debug(f"Channel created at: {created_at}, Current time: {end}")
            rand_datetime = get_rand_datetime(created_at, end)
            logger.debug(f"Random datetime generated: {rand_datetime}")
    
            message_found = False
            async for rand_message in channel.history(limit=5, around=rand_datetime):
                if rand_message.content and not is_blacklisted(rand_message.content):
                    logger.debug(f"Random message found: {rand_message.content[:20]}...")  # Log first 20 chars
                    await create_and_send_response(rand_message, channel, format, background)
                    message_found = True
                    break
            if message_found:
                break
        
        if not message_found:
            logger.warning("No suitable message found in channel history")
            await inter.followup.send("No suitable message found. Please try again.")
        else:
            await inter.followup.send("Command processed successfully.")
    except discord.errors.Forbidden:
        logger.error("Bot doesn't have permission to read message history")
        await inter.followup.send("I don't have permission to read message history in this channel.")
    except Exception as e:
        logger.error(f"Error processing dejavu command: {str(e)}")
        await inter.followup.send("An error occurred while processing the command. Please try again later.")

    logger.debug("Dejavu command processing completed")

def get_rand_datetime(start: datetime, end: datetime) -> datetime:
    """Return a random datetime between two datetime objects."""
    logger.debug(f"Generating random datetime between {start} and {end}")
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = randrange(int_delta)
    return start + timedelta(seconds=random_second)

async def create_and_send_response(rand_message: discord.Message, channel: discord.TextChannel, choice: Literal["text", "image"], background: str):
    """Create and send the appropriate response based on the user's choice."""
    logger.debug(f"Creating response for choice: {choice}, background: {background}")
    text = f"{rand_message.author.name} said: \n{rand_message.content}\nat {rand_message.created_at.strftime('%Y-%m-%d %I:%M %p')}"

    try:
        if choice == "text":
            logger.debug("Sending text response")
            await channel.send(text)
        elif choice == "image":
            logger.debug("Creating and sending image response")
            await create_and_send_image(text, channel, background, bot)
        else:
            logger.warning(f"Invalid choice: {choice}")
            await channel.send("Invalid Command.")
    except Exception as e:
        logger.error(f"Error in create_and_send_response: {str(e)}")
        await channel.send("An error occurred while creating the response.")

    logger.debug("Response sent successfully")

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
            if rand_message.content and (not bot.whosaid["mercy_mode"] or rand_message.author.id != MERCY_USER_ID):
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
        try:
            message = await bot.wait_for('message', check=lambda m: m.channel == channel and not m.author.bot and m.mentions, timeout=60.0)
            if message.mentions[0].name == bot.whosaid["author"]:
                await process_whosaid_guess(message)
                break
            else:
                await message.reply("Wrong! Try again.")
        except asyncio.TimeoutError:
            await channel.send("No one answered in time. Game aborted.")
            await end_whosaid_game(channel)
            break

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
            if message.author.bot or (mercy_mode and message.author.id == MERCY_USER_ID):
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
        try:
            message = await bot.wait_for('message', check=lambda m: m.channel == channel and not m.author.bot and m.mentions, timeout=60.0)
            if message.mentions[0].name == bot.word_yapper["top_user"]:
                await process_word_yapper_guess(message)
                break
            else:
                await message.reply("Wrong! Try again.")
        except asyncio.TimeoutError:
            await channel.send("No one answered in time. Game aborted.")
            await end_word_yapper_game(channel)
            break

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


class HallOfFameView(View):
    """View for Hall of Fame pagination and sharing."""
    
    def __init__(self, bot_instance, entries: list, page: int = 0, per_page: int = 10):
        super().__init__(timeout=300)  # 5 minute timeout
        self.bot = bot_instance
        self.entries = entries
        self.page = page
        self.per_page = per_page
        self.total_pages = (len(entries) + per_page - 1) // per_page if entries else 1
        
    def get_page_entries(self):
        """Get entries for current page."""
        start = self.page * self.per_page
        end = start + self.per_page
        return self.entries[start:end]
    
    def create_embed(self):
        """Create embed for current page."""
        page_entries = self.get_page_entries()
        
        if not page_entries:
            embed = Embed(
                title="Hall of Fame",
                description="No pinned items yet.",
                color=discord.Color.gold()
            )
            return embed
        
        embed = Embed(
            title="Hall of Fame",
            description=f"Page {self.page + 1}/{self.total_pages} ({len(self.entries)} total)",
            color=discord.Color.gold()
        )
        
        for i, entry in enumerate(page_entries, start=self.page * self.per_page + 1):
            # Truncate message preview
            message_preview = entry.get("original_message_text", "")[:500]
            if len(entry.get("original_message_text", "")) > 500:
                message_preview += "..."
            
            # Build field value
            value_parts = []
            if message_preview:
                value_parts.append(f"**Message:** {message_preview}")
            
            if entry.get("background_used"):
                value_parts.append(f"**Background:** {entry['background_used']}")
            
            if entry.get("image_urls"):
                image_count = len(entry["image_urls"])
                value_parts.append(f"**Images:** {image_count} image(s)")
                # Add first image URL
                if entry["image_urls"][0]:
                    value_parts.append(f"**Image:** {entry['image_urls'][0]}")
            
            value_parts.append(f"**Timestamp:** {entry.get('timestamp', 'Unknown')}")
            value_parts.append(f"**Pinned by:** {entry.get('pinned_by', 'Unknown')}")
            
            # Create jump link
            try:
                message_id = entry.get("message_id")
                channel_id = entry.get("channel_id")
                guild_id = entry.get("guild_id")
                if message_id and channel_id:
                    jump_url = f"https://discord.com/channels/{guild_id or '@me'}/{channel_id}/{message_id}"
                    value_parts.append(f"[Jump to message]({jump_url})")
            except Exception:
                pass
            
            field_name = f"{i}. {entry.get('author_name', 'Unknown')}"
            field_value = "\n".join(value_parts)
            
            embed.add_field(
                name=field_name,
                value=field_value[:1024],  # Discord embed field limit
                inline=False
            )
        
        return embed
    
    @discord.ui.button(label="Previous", emoji="◀️", style=discord.ButtonStyle.secondary, disabled=True)
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        if self.page > 0:
            self.page -= 1
            self.prev_button.disabled = self.page == 0
            self.next_button.disabled = self.page >= self.total_pages - 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="Next", emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if self.page < self.total_pages - 1:
            self.page += 1
            self.prev_button.disabled = self.page == 0
            self.next_button.disabled = self.page >= self.total_pages - 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="Share", emoji="📤", style=discord.ButtonStyle.primary, row=1)
    async def share_button(self, interaction: discord.Interaction, button: Button):
        """Share selected entry to current channel."""
        # For now, share first entry on page. Could be enhanced with select menu
        page_entries = self.get_page_entries()
        if not page_entries:
            await interaction.response.send_message("No entries to share.", ephemeral=True)
            return
        
        # Defer response first
        await interaction.response.defer(ephemeral=True)
        
        # Share first entry
        entry = page_entries[0]
        await self.share_entry(entry, interaction.channel, interaction)
    
    async def share_entry(self, entry: dict, channel: discord.TextChannel, interaction: discord.Interaction):
        """Share a Hall of Fame entry to a channel."""
        try:
            # Try to fetch original message
            message_id = entry.get("message_id")
            channel_id = entry.get("channel_id")
            
            original_message = None
            if message_id and channel_id:
                try:
                    target_channel = bot.get_channel(channel_id)
                    if target_channel:
                        original_message = await target_channel.fetch_message(message_id)
                except Exception:
                    pass
            
            if original_message:
                # Repost original message content and attachments
                if original_message.attachments:
                    files = []
                    async with aiohttp.ClientSession() as session:
                        for attachment in original_message.attachments:
                            async with session.get(attachment.url) as resp:
                                if resp.status == 200:
                                    data = await resp.read()
                                    files.append(discord.File(BytesIO(data), filename=attachment.filename))
                    
                    if original_message.content:
                        await channel.send(content=original_message.content, files=files)
                    else:
                        await channel.send(files=files)
                else:
                    if original_message.content:
                        await channel.send(original_message.content)
                
                await interaction.followup.send("Shared to channel!", ephemeral=True)
            else:
                # Fallback: repost stored data
                content = entry.get("original_message_text", "")
                if entry.get("image_urls"):
                    # Try to download and repost images
                    async with aiohttp.ClientSession() as session:
                        files = []
                        for img_url in entry["image_urls"][:10]:  # Limit to 10 images
                            try:
                                async with session.get(img_url) as resp:
                                    if resp.status == 200:
                                        data = await resp.read()
                                        files.append(discord.File(BytesIO(data), filename="image.png"))
                            except Exception:
                                pass
                        
                        if content:
                            await channel.send(content=content, files=files if files else None)
                        elif files:
                            await channel.send(files=files)
                        else:
                            await channel.send("Could not retrieve original content.")
                    
                    await interaction.followup.send("Shared to channel!", ephemeral=True)
                else:
                    if content:
                        await channel.send(content)
                        await interaction.followup.send("Shared to channel!", ephemeral=True)
                    else:
                        await interaction.followup.send("Could not retrieve original content.", ephemeral=True)
                        
        except Exception as e:
            logger.error(f"Error sharing entry: {str(e)}")
            try:
                await interaction.followup.send("An error occurred while sharing.", ephemeral=True)
            except:
                pass


@dejavu.command(name="halloffame", description="Browse the Hall of Fame")
async def hall_of_fame(inter: discord.Interaction):
    """Handle the /dejavu halloffame command."""
    await inter.response.defer()
    
    # Get all entries, sorted by pinned_at (newest first)
    entries = list(bot.hall_of_fame.values())
    entries.sort(key=lambda x: x.get("pinned_at", ""), reverse=True)
    
    if not entries:
        embed = Embed(
            title="Hall of Fame",
            description="No pinned items yet.",
            color=discord.Color.gold()
        )
        await inter.followup.send(embed=embed)
        return
    
    # Create view with pagination
    view = HallOfFameView(bot, entries, page=0, per_page=10)
    embed = view.create_embed()
    
    # Disable prev button on first page
    view.prev_button.disabled = True
    view.next_button.disabled = len(entries) <= 10
    
    await inter.followup.send(embed=embed, view=view)

# Add alias command
@dejavu.command(name="hof", description="Browse the Hall of Fame (alias)")
async def hall_of_fame_alias(inter: discord.Interaction):
    """Handle the /dejavu hof command (alias for halloffame)."""
    await hall_of_fame(inter)

@bot.event
async def on_message(message: discord.Message):
    """Handle messages for the 'Who said' and 'Word Yapper' games."""
    if message.author.bot or not message.mentions:
        return

    logger.debug(f"Processing mention: {message.content[:20]}...")  # Log first 20 chars of message

@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """Handle pin reactions (📌) to pin messages to Hall of Fame."""
    # Skip if bot's own reaction
    if user.bot:
        return
    
    # Only handle 📌 reactions
    if str(reaction.emoji) != "📌":
        return
    
    try:
        message = reaction.message
        message_id_str = str(message.id)
        
        # Check if already pinned
        if message_id_str in bot.hall_of_fame:
            return
        
        # Extract message metadata
        image_urls = []
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    image_urls.append(attachment.url)
        
        # Truncate message content if too long
        message_content = message.content[:1000] if message.content else ""
        
        # Store in Hall of Fame
        pin_entry = {
            "message_id": message.id,
            "channel_id": message.channel.id,
            "guild_id": message.guild.id if message.guild else None,
            "image_urls": image_urls,
            "original_message_text": message_content,
            "author_name": message.author.name,
            "timestamp": message.created_at.strftime('%Y-%m-%d %I:%M %p'),
            "background_used": None,  # Not a bot image
            "pinned_by": user.name,
            "pinned_at": datetime.now(timezone.utc).isoformat(),
            "pin_type": "message"
        }
        
        bot.hall_of_fame[message_id_str] = pin_entry
        bot.save_hall_of_fame()
        
        # React with ✅ checkmark
        try:
            await message.add_reaction("✅")
        except Exception as e:
            logger.warning(f"Could not add ✅ reaction: {e}")
            
    except Exception as e:
        logger.error(f"Error handling pin reaction: {str(e)}")

@bot.event
async def on_reaction_remove(reaction: discord.Reaction, user: discord.User):
    """Handle removal of pin reactions (📌) to unpin messages from Hall of Fame."""
    # Skip if bot's own reaction removal
    if user.bot:
        return
    
    # Only handle 📌 reactions
    if str(reaction.emoji) != "📌":
        return
    
    try:
        message = reaction.message
        message_id_str = str(message.id)
        
        # Check if message is pinned
        if message_id_str not in bot.hall_of_fame:
            return
        
        # Check if there are any other 📌 reactions (don't unpin if others still have it)
        # Get fresh reaction data
        try:
            message = await message.channel.fetch_message(message.id)
            pin_reactions = [r for r in message.reactions if str(r.emoji) == "📌"]
            if pin_reactions:
                # Check if any non-bot users still have the reaction
                pin_reaction = pin_reactions[0]
                users_with_pin = [u async for u in pin_reaction.users() if not u.bot]
                if users_with_pin:
                    # Other users still have it pinned, don't unpin
                    return
        except Exception as e:
            logger.warning(f"Could not fetch message for reaction check: {e}")
        
        # Remove from Hall of Fame
        del bot.hall_of_fame[message_id_str]
        bot.save_hall_of_fame()
        
        # Remove ✅ checkmark if present
        try:
            checkmark_reactions = [r for r in message.reactions if str(r.emoji) == "✅"]
            if checkmark_reactions:
                await message.remove_reaction("✅", bot.user)
        except Exception as e:
            logger.warning(f"Could not remove ✅ reaction: {e}")
            
    except Exception as e:
        logger.error(f"Error handling unpin reaction: {str(e)}")

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name}")

logger.info("Starting DejavuBot")
bot.run(os.environ.get("DISCORD_TOKEN"))
