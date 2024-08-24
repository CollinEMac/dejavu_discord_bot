"""
This is all of the code for a discord bot that will find a random message in
your channel history and send it in either text or image format and there is also
a game where you have to guess who said the message

Invoke with `/dejavu`
Arguments: text, image, whosaid, word_champion
"""

import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from random import choice, randrange
from collections import Counter

from PIL import Image, ImageColor, ImageDraw, ImageFont

import discord
from discord import app_commands

# Load .env file
from dotenv import load_dotenv

load_dotenv()

class DejavuBot(discord.Client):
    VERY_DARK_COLORS = [
        "black",
        "darkblue",
        "darkmagenta",
        "darkslategrey",
        "indigo",
        "midnightblue",
        "navy",
        "purple",
    ]

    def __init__(self):
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

    async def setup_hook(self):
        await self.tree.sync()

    @app_commands.command(name="dejavu", description="Retrieve random messages or play guessing games")
    @app_commands.choices(choices=[
        app_commands.Choice(name="Text message", value="text"),
        app_commands.Choice(name="Image message", value="image"),
        app_commands.Choice(name="Guess who said it", value="whosaid"),
        app_commands.Choice(name="Guess word champion", value="word_champion"),
    ])
    async def dejavu(self, inter: discord.Interaction, choices: app_commands.Choice[str]):
        """
        Retrieve a random message or play a guessing game based on the chosen option.
        """

        # If a game of whosaid is already being played, do not continue.
        if self.whosaid["playing"] is True:
            await inter.response.send_message("I'm still waiting for you to guess.")
            return

        # Send a message to confirm recipt of command.
        # Else the bot will error.
        # TODO: Find a way to run a command without
        # something like this
        await inter.response.send_message("Command sent.")

        # Get a random datetime between now and when the channel was created
        channel = inter.channel
        created_at = channel.created_at
        end = datetime.utcnow().replace(tzinfo=timezone.utc)
        rand_datetime = self.get_rand_datetime(created_at, end)

        # Fetch a message using the random datetime
        # limit=1 so we only get one message (we could change this later to add more?)
        async for rand_message in channel.history(limit=1, around=rand_datetime):
            if rand_message.content != "":
                if choices.value == "word_champion":
                    await self.word_champion(channel)
                else:
                    await self.create_and_send_response(rand_message, channel, choices.value)
                break

    async def on_message(self, message: discord.Message):
        """
        Check if the message is a valid guess for the ongoing game and process it.
        """
        if (not message.author.bot and 
            self.whosaid["channel"] == message.channel.id and
            self.whosaid["playing"] and 
            len(message.mentions) > 0):

            guessed_user = message.mentions[0].name
            correct_user = self.whosaid["author"]

            if guessed_user == correct_user:
                await message.reply(f"Correct! {correct_user} said the word the most.")
            else:
                await message.reply(f"Wrong! The correct answer was {correct_user}.")

            self.whosaid["playing"] = False

    async def create_and_send_response(self, rand_message, channel, choice):
        text = (
            rand_message.author.name
            + " said: \n"
            + rand_message.content
            + "\nat "
            + rand_message.created_at.strftime("%Y-%m-%d %I:%M %p")
        )

        if choice == "text":
            # Sends the random message with the message author, content,
            # and creation datetime
            # `/dejavu text`
            await channel.send(text)
        elif choice == "image":
            await self.create_and_send_image(text, channel)
        elif choice == "whosaid":
            # if the choice is whosaid, pass the rand_message and channel to who_said()
            await self.who_said(rand_message, channel)
        else:
            await channel.send("Invalid Command.")

    async def create_and_send_image(self, text, channel):
        """
        `/dejavu image`
        """
        font = ImageFont.truetype("./fonts/Courier.ttf", size=14)  # debian path

        # Convert dict_items to a list
        color_items = list(ImageColor.colormap.items())

        rand_color = choice(color_items)[0]
        img = Image.new('RGB', (1000, 100), color=rand_color)

        img_draw = ImageDraw.Draw(img)

        if rand_color not in self.VERY_DARK_COLORS:
            img_draw.text((0, 25), text, font=font, fill=(0, 0, 0))
        else:
            img_draw.text((0, 25), text, font=font, fill=(255, 255, 255))

        # Save the image to a BytesIO buffer
        buffer = BytesIO()
        img.save(buffer, "png")
        buffer.seek(0)  # Reset the buffer pointer to the beginning

        file = discord.File(buffer, filename="image.png")
        await channel.send(file=file)

    async def who_said(self, message, channel):
        """
        A game where a message is presented and the user has to guess who wrote it
        by mentioning the user. They get 2 guesses before game over.
        /dejavu whosaid
        """

        # Set inital game variables and start the game
        self.whosaid["playing"] = True
        self.whosaid["channel"] = message.channel.id
        self.whosaid["second_chance"] = True
        self.whosaid["author"] = message.author.name
        await channel.send("Who said: " + message.content)

    async def word_champion(self, channel):
        """
        A game where players guess who said a random word most frequently.
        """
        self.whosaid["playing"] = True
        self.whosaid["channel"] = channel.id

        # Fetch a large number of messages
        messages = await channel.history(limit=1000).flatten()

        # Count words for each author
        word_counts = {}
        for message in messages:
            author = message.author.name
            if author not in word_counts:
                word_counts[author] = Counter()
            word_counts[author].update(message.content.lower().split())

        # Find words that appear more than once
        common_words = set()
        for author_counts in word_counts.values():
            common_words.update(word for word, count in author_counts.items() if count > 1)

        if not common_words:
            await channel.send("Not enough data to play the game. Try chatting more!")
            self.whosaid["playing"] = False
            return

        # Choose a random word from common words
        chosen_word = choice(list(common_words))

        # Find the author who said it most
        champion = max(word_counts.keys(), key=lambda author: word_counts[author][chosen_word])

        self.whosaid["author"] = champion
        self.whosaid["message"] = f"Who said the word '{chosen_word}' the most?"

        await channel.send(self.whosaid["message"])

    @staticmethod
    def get_rand_datetime(start, end):
        """
        https://stackoverflow.com/questions/553303/generate-a-random-date-between-two-other-dates

        This function will return a random datetime between two datetime objects.
        """
        delta = end - start
        int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
        random_second = randrange(int_delta)
        return start + timedelta(seconds=random_second)


def main():
    load_dotenv()
    bot = DejavuBot()
    bot.run(os.environ.get("DISCORD_TOKEN"))

if __name__ == "__main__":
    main()