# Dejavu Discord Bot

Dejavu is a fun and interactive Discord bot that brings nostalgia and entertainment to your server. It offers various games and features based on your server's message history.

## Features

1. **Random Message Recall**: Fetch random messages from the channel's history.
   - Text format: Display the message as plain text.
   - Image format: Create an image with the message text.

2. **Who Said Game**: Test your memory of who said what in your server.

3. **Word Yapper Game**: Guess who uses certain words most frequently.

4. **Leaderboard**: Keep track of players' scores across different games.

## Commands

- `/dejavu`: Main command to start games or recall random messages.
  - Options:
    - `text`: Display a random message as text.
    - `image`: Create an image with a random message.
    - `whosaid`: Start a "Who Said" game.
    - `wordyapper`: Start a "Word Yapper" game.
  - Additional parameters:
    - `rounds`: Set the number of rounds for games (default: 5, max: 10).
    - `mercy`: Enable Mercy mode for Adam (only for Who Said and Word Yapper).

- `/leaderboard`: View the current leaderboard.

## Setup

1. Clone this repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Set up your Discord bot token in a `.env` file:
   ```
   DISCORD_TOKEN=your_token_here
   ```
4. Run the bot: `python dejavu_bot.py`

## Deployment

This bot is configured to be deployed on Fly.io. Refer to the `fly.toml` file for deployment settings.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Insert your chosen license here]
