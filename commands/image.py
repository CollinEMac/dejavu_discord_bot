import discord
from io import BytesIO
import logging
from random import choice
import re
from PIL import Image, ImageDraw, ImageFont
import textwrap

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('dejavu_bot')

BACKGROUNDS = [
        "babeplease",
        "chad",
        "criticallowbrain",
        "furry",
        "girls",
        "guyatparty",
        "japmic",
        "iphone",
        "nerd",
        "nobitches",
        "npc",
        "random",
        "receives",
        "shutup",
        "simp",
        "smolbrain",
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

async def create_and_send_image(text: str, channel: discord.TextChannel, background: str):
    """Create and send an image with the message text overlaid on the selected background."""
    logger.debug(f"Creating image with text: {text[:20]}..., background: {background}")
    
    RANDOM = 'random'

    try:
        if background == RANDOM:
            background = choice([bg for bg in BACKGROUNDS if bg != RANDOM])

        # Load the background image
        background_path = f"assets/images/{background}.jpg"
        logger.debug(f"Loading background image from: {background_path}")
        background_img = Image.open(background_path)
        width, height = background_img.size
        
        # Create a drawing object
        draw = ImageDraw.Draw(background_img)
        
        # Load fonts
        font_large = ImageFont.truetype(f"assets/fonts/Courier.ttf", size=36)
        font_small = ImageFont.truetype(f"assets/fonts/Courier.ttf", size=24)
        
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
        await channel.send(file=file)
    except Exception as e:
        logger.error(f"Error creating image: {str(e)}")
        await channel.send("An error occurred while creating the image.")


def is_blacklisted(message_content):
    # Check if the string is explicitly blacklisted
    for pattern in MESSAGE_BLACKLIST:
        if re.search(pattern, message_content, re.IGNORECASE):
            return True

    return False


