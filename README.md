# Discord Bot Ship Tracker

A Discord bot that tracks the real-time journey of a ship and posts updates to a Discord channel. Designed to monitor a friend's (Kanakaris) voyage, this bot scrapes ship data and coordinates, formats them into engaging updates (including maps and status), and posts them to Discord on a schedule or on demand.

## Features

- **Automated Ship Tracking:** Regularly scrapes current ship data (name, speed, course, type, and coordinates) using Selenium from online ship tracking sites.
- **Discord Integration:** Posts rich embed updates to a specified channel, including Google Maps links to the current position.
- **Resilient Storage:** Maintains ship data in JSON files for historical reference and fallback.
- **Custom Farewell Messages:** Sends motivational and friendly messages alongside technical data.
- **Manual or Scheduled Updates:** Users can run the `!kanakaris` command for an instant update or rely on scheduled posts.
- **Automated Cleanup:** Periodically deletes excess screenshots and old JSON files to keep storage clean.

## Setup

### Prerequisites

- Python 3.8+
- A Discord bot token and a target channel ID
- Chrome browser (for Selenium) and ChromeDriver (auto-managed)
- [MyShipTracking](https://www.myshiptracking.com/) ship MMSI (default is for STI MAESTRO)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/npapoutsakis/discord-bot-ship-tracker.git
   cd discord-bot-ship-tracker
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**

   Create a `.env` file in the root directory with the following contents:
   ```
   DISCORD_TOKEN=your_discord_token
   DISCORD_CHANNEL_ID=your_channel_id
   SHIP_MMSI=538010457
   SHIP_NAME=STI MAESTRO
   FRIEND_NAME=Kanakaris
   ```

   Adjust values as needed.

### Running the Bot

```bash
python main.py
```

The bot will connect to Discord, clean up old data, and begin automatic scheduled updates.

## Usage

- **Manual Update:**  
  In your Discord server, type:
  ```
  !kanakaris
  ```
  The bot will respond with the latest tracked data for the ship.

- **Automatic Updates:**  
  The bot posts updates every hour by default (adjustable in environment variables or code).

## How It Works

- Uses Selenium to scrape ship tracking sites for fresh data.
- Saves each scrape in a JSON file with timestamp.
- Sends a rich embed to Discord with ship stats, location, and a Google Maps link.
- Handles consent banners and dynamic popups on the source site.
- Cleans up old screenshots and JSON data automatically.

## Customization

- **Change the tracked ship:**  
  Set `SHIP_MMSI` and `SHIP_NAME` in your `.env` file.
- **Farewell Messages:**  
  Edit the `farewell_messages` list in `main.py` to personalize send-off messages.
- **Update Frequency:**  
  Adjust `UPDATE_INTERVAL_HOURS` in `main.py` to change how often the bot scrapes and posts.

## Dependencies

See [`requirements.txt`](requirements.txt) for the full list:
- discord.py
- python-dotenv
- aiohttp
- beautifulsoup4
- selenium
- webdriver-manager

## Troubleshooting

- Make sure Chrome and ChromeDriver are installed and compatible.
- Ensure the bot has permissions to post in your Discord channel.
- Check `ship_bot.log` for detailed logs.
- If scraping fails, ensure the ship tracking site has not changed its layout or added extra protections.

## License

MIT License

---

**Happy tracking, and safe travels to all sailors!**
