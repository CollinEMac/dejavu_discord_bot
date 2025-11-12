import discord
from discord.ui import View, Button
from io import BytesIO
import logging
from random import choice
import re
from PIL import Image, ImageDraw, ImageFont
import textwrap
from datetime import datetime, timezone
import os

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('dejavu_bot')

BACKGROUNDS = [
        "babeplease",
        "chad",
        "conspiracy",
        "criticallowbrain",
        "furry",
        "girls",
        "guyatclub",
        "guyatparty",
        "iphone",
        "japmic",
        "nerd",
        "nobitches",
        "npc",
        "owned",
        "random",
        "receives",
        "shutup",
        "simp",
        "smolbrain",
        "whiteboard",
        "yap"
]

MESSAGE_BLACKLIST = [
    r'https?://\S+|www\.\S+',  # URL pattern
    r'\blol\b',                # "lol" (case-insensitive)
    r'\blmao\b',               # "lmao" (case-insensitive)
    r'\brofl\b',               # "rofl" (case-insensitive)
    r'\bwtf\b',                # "wtf" (case-insensitive)
    r'\bkek\b',                # "kek" (case-insensitive)
    r'\b(ha){2,}\b'            # Two or more "ha"s as a standalone word
]

async def create_and_send_image(text: str, channel: discord.TextChannel, background: str, bot_instance=None):
    """Create and send an image with the message text overlaid on the selected background.
    Returns the sent message."""
    logger.debug(f"Creating image with text: {text[:20]}..., background: {background}")
    
    RANDOM = 'random'

    try:
        if background == RANDOM:
            background = choice([bg for bg in BACKGROUNDS if bg != RANDOM])
        
        # Validate background to prevent path traversal
        if background not in BACKGROUNDS:
            logger.error(f"Invalid background: {background}")
            error_message = await channel.send("Invalid background selection.")
            return error_message

        # Load the background image
        background_path = f"assets/images/{background}.jpg"
        logger.debug(f"Loading background image from: {background_path}")
        
        # Verify the file exists
        if not os.path.exists(background_path):
            logger.error(f"Background image not found: {background_path}")
            error_message = await channel.send("Background image not found.")
            return error_message
            
        background_img = Image.open(background_path)
        width, height = background_img.size
        
        # Create a drawing object
        draw = ImageDraw.Draw(background_img)
        
        # Load fonts
        font_large = ImageFont.truetype("assets/fonts/Courier.ttf", size=36)
        font_small = ImageFont.truetype("assets/fonts/Courier.ttf", size=24)
        
        # Split the text
        parts = text.split("\n")
        author = parts[0]
        message = parts[1]
        timestamp = parts[2]
        
        # Wrap the message text
        wrapped_message = textwrap.fill(message, width=40)
        
        # Set colors and alignment based on background
        text_color = (255, 255, 255)  # White for both backgrounds
        if background == "iphone":
            shadow_color = (0, 0, 0)  # Black shadow for iphone
            alignment = "center"
        else:
            shadow_color = None  # No shadow for japmic
            alignment = "top"
        
        # Calculate total text height
        author_bbox = draw.textbbox((0, 0), author, font=font_large)
        author_height = author_bbox[3] - author_bbox[1]
        
        message_lines = wrapped_message.split('\n')
        message_height = sum(draw.textbbox((0, 0), line, font=font_small)[3] - draw.textbbox((0, 0), line, font=font_small)[1] for line in message_lines)
        
        timestamp_bbox = draw.textbbox((0, 0), timestamp, font=font_small)
        timestamp_height = timestamp_bbox[3] - timestamp_bbox[1]
        
        total_height = author_height + message_height + timestamp_height + 40  # 40 for padding
        
        # Set starting y position based on alignment
        if alignment == "center":
            start_y = (height - total_height) // 2
        else:  # top
            start_y = 20
        
        # Draw text with optional shadow effect
        def draw_text_with_shadow(position, text, font, shadow_color, text_color):
            if shadow_color:
                # Draw shadow
                shadow_offset = 2
                for offset in [(0, 0), (0, shadow_offset), (shadow_offset, 0), (shadow_offset, shadow_offset)]:
                    draw.text((position[0]+offset[0], position[1]+offset[1]), text, font=font, fill=shadow_color)
            # Draw main text
            draw.text(position, text, font=font, fill=text_color)
        
        # Draw author
        author_bbox = draw.textbbox((0, 0), author, font=font_large)
        author_width = author_bbox[2] - author_bbox[0]
        author_position = ((width - author_width) // 2, start_y)
        draw_text_with_shadow(author_position, author, font_large, shadow_color, text_color)
        
        # Draw message
        current_y = start_y + author_height + 20  # 20 for padding
        for line in message_lines:
            line_bbox = draw.textbbox((0, 0), line, font=font_small)
            line_width = line_bbox[2] - line_bbox[0]
            line_position = ((width - line_width) // 2, current_y)
            draw_text_with_shadow(line_position, line, font_small, shadow_color, text_color)
            current_y += line_bbox[3] - line_bbox[1]
        
        # Draw timestamp
        timestamp_width = timestamp_bbox[2] - timestamp_bbox[0]
        timestamp_position = ((width - timestamp_width) // 2, current_y + 20)  # 20 for padding
        draw_text_with_shadow(timestamp_position, timestamp, font_small, shadow_color, text_color)
        
        # Save and send the image
        buffer = BytesIO()
        background_img.save(buffer, "PNG")
        buffer.seek(0)
        
        file = discord.File(buffer, filename=f"dejavu_message_{background}.png")
        
        # Create view with pin button if bot_instance is provided
        view = None
        if bot_instance:
            # We'll create the view after sending the message so we have the message ID
            sent_message = await channel.send(file=file)
            view = PinButtonView(bot_instance, sent_message.id, text, background)
            # Edit the message to add the view
            await sent_message.edit(view=view)
            return sent_message
        else:
            sent_message = await channel.send(file=file)
            return sent_message
    except Exception as e:
        logger.error(f"Error creating image: {str(e)}")
        error_message = await channel.send("An error occurred while creating the image.")
        return error_message


def is_blacklisted(message_content):
    # Check if the string is explicitly blacklisted
    for pattern in MESSAGE_BLACKLIST:
        if re.search(pattern, message_content, re.IGNORECASE):
            return True

    return False


class PinButtonView(View):
    """View containing a pin button for bot-generated images."""
    
    def __init__(self, bot_instance, message_id: int, original_text: str, background: str):
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot_instance
        self.message_id = message_id
        self.original_text = original_text
        self.background = background
        
        # Parse original_text to extract components
        parts = original_text.split("\n")
        if len(parts) >= 3:
            # Format: "author said: \nmessage\nat timestamp"
            author_line = parts[0]  # "author said: "
            self.author_name = author_line.replace(" said:", "").strip()
            self.original_message_text = parts[1].strip()
            self.timestamp_str = parts[2].replace("at ", "").strip()
        else:
            # Fallback if format is unexpected
            self.author_name = "Unknown"
            self.original_message_text = original_text
            self.timestamp_str = "Unknown"
        
    @discord.ui.button(label="Pin to Hall of Fame", emoji="📌", style=discord.ButtonStyle.primary)
    async def pin_button(self, interaction: discord.Interaction, button: Button):
        """Handle pin button click."""
        try:
            # Get the message
            message = interaction.message
            
            # Check if already pinned
            message_id_str = str(message.id)
            if message_id_str in self.bot.hall_of_fame:
                await interaction.response.send_message("This image is already pinned!", ephemeral=True)
                return
            
            # Get image URL from attachment
            image_url = None
            if message.attachments:
                image_url = message.attachments[0].url
            
            # Use structured metadata instead of parsing original_text
            author_name = self.author_name
            original_message_text = self.original_message_text
            timestamp_str = self.timestamp_str
            
            # Store in Hall of Fame
            pin_entry = {
                "message_id": message.id,
                "channel_id": message.channel.id,
                "guild_id": message.guild.id if message.guild else None,
                "image_urls": [image_url] if image_url else [],
                "original_message_text": original_message_text[:1000],  # Truncate if needed
                "author_name": author_name,
                "timestamp": timestamp_str,
                "background_used": self.background,
                "pinned_by": interaction.user.name,
                "pinned_at": datetime.now(timezone.utc).isoformat(),
                "pin_type": "bot_image"
            }
            
            self.bot.hall_of_fame[message_id_str] = pin_entry
            self.bot.save_hall_of_fame()
            
            # Add 📌 reaction to message for consistency
            try:
                await message.add_reaction("📌")
            except Exception as e:
                logger.warning(f"Could not add 📌 reaction: {e}")
            
            # React with ✅ checkmark
            try:
                await message.add_reaction("✅")
            except Exception as e:
                logger.warning(f"Could not add ✅ reaction: {e}")
            
            # Disable the button
            button.disabled = True
            await interaction.response.edit_message(view=self)
            
        except Exception as e:
            logger.error(f"Error pinning image: {str(e)}")
            await interaction.response.send_message("An error occurred while pinning the image.", ephemeral=True)


