import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN') or 'YOUR_DISCORD_BOT_TOKEN'
CHANNEL_ID = int(os.getenv('CHANNEL_ID', 0)) or YOUR_CHANNEL_ID
MARINETRAFFIC_API_KEY = os.getenv('MARINETRAFFIC_API_KEY') or 'YOUR_MARINETRAFFIC_API_KEY'
SHIP_MMSI = os.getenv('SHIP_MMSI') or 'YOUR_SHIP_MMSI'

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

class ShipTracker:
    def __init__(self):
        self.api_key = MARINETRAFFIC_API_KEY
        self.mmsi = SHIP_MMSI
    
    async def get_ship_location(self):
        """Fetch ship data from MarineTraffic API"""
        url = "https://services.marinetraffic.com/api/exportvessel/v:8"
        params = {
            'key': self.api_key,
            'v': 2,
            'protocol': 'jsono',
            'mmsi': self.mmsi
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            ship_data = data[0]
                            return {
                                'name': ship_data.get('SHIPNAME', 'Unknown Ship'),
                                'latitude': ship_data.get('LAT'),
                                'longitude': ship_data.get('LON'),
                                'speed': ship_data.get('SPEED', 0),
                                'course': ship_data.get('COURSE', 0),
                                'destination': ship_data.get('DESTINATION', 'Unknown'),
                                'eta': ship_data.get('ETA', 'Unknown'),
                                'timestamp': ship_data.get('TIMESTAMP'),
                                'status': ship_data.get('STATUS', 'Unknown')
                            }
                    else:
                        print(f"API Error: {response.status}")
                        return None
        except Exception as e:
            print(f"Error fetching ship data: {str(e)}")
            return None
    
    def format_ship_embed(self, ship_data):
        """Create a Discord embed with ship information"""
        embed = discord.Embed(
            title="🚢 Ship Location Update",
            description=f"**{ship_data['name']}** - My Best Friend Ship",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        # Position field
        embed.add_field(
            name="📍 Position",
            value=f"Lat: {ship_data['latitude']}°\nLon: {ship_data['longitude']}°",
            inline=True
        )
        
        # Speed and Course
        embed.add_field(
            name="⚡ Speed & Course",
            value=f"{ship_data['speed']} knots\nCourse: {ship_data['course']}°",
            inline=True
        )
        
        # Destination
        embed.add_field(
            name="🎯 Destination",
            value=ship_data['destination'],
            inline=True
        )
        
        # Status
        embed.add_field(
            name="📊 Status",
            value=ship_data['status'],
            inline=True
        )
        
        # ETA
        embed.add_field(
            name="⏰ ETA",
            value=ship_data['eta'],
            inline=True
        )
        
        # Google Maps link
        maps_url = f"https://www.google.com/maps?q={ship_data['latitude']},{ship_data['longitude']}"
        embed.add_field(
            name="🗺️ View on Map",
            value=f"[Click here to view location]({maps_url})",
            inline=False
        )
        
        # Footer with last update time
        if ship_data['timestamp']:
            last_update = datetime.fromtimestamp(ship_data['timestamp'])
            embed.set_footer(text=f"Last ship update: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return embed

# Initialize ship tracker
tracker = ShipTracker()

@bot.event
async def on_ready():
    print(f'{bot.user} has logged in to Discord!')
    print('Ship tracking bot is now online!')
    # Start the scheduled task
    ship_update_task.start()

@tasks.loop(hours=48)  # Every 2 days (48 hours)
async def ship_update_task():
    """Scheduled task to send ship updates every 2 days"""
    await send_ship_update()

@ship_update_task.before_loop
async def before_ship_update():
    """Wait until the bot is ready before starting the loop"""
    await bot.wait_until_ready()

async def send_ship_update():
    """Send ship location update to Discord channel"""
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            print(f"Channel with ID {CHANNEL_ID} not found")
            return
        
        print("Fetching ship location...")
        ship_data = await tracker.get_ship_location()
        
        if ship_data:
            embed = tracker.format_ship_embed(ship_data)
            await channel.send(embed=embed)
            print("Ship update sent successfully!")
        else:
            await channel.send("❌ Could not fetch ship location data. Please check the API key and MMSI number.")
            
    except Exception as e:
        print(f"Error sending ship update: {str(e)}")

@bot.command(name='ship')
async def manual_ship_update(ctx):
    """Manual command to get ship location immediately"""
    await ctx.send("🔍 Fetching ship location...")
    
    ship_data = await tracker.get_ship_location()
    if ship_data:
        embed = tracker.format_ship_embed(ship_data)
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Could not fetch ship location data.")

@bot.command(name='status')
async def bot_status(ctx):
    """Check bot status and next update time"""
    next_run = ship_update_task.next_iteration
    if next_run:
        embed = discord.Embed(
            title="🤖 Bot Status",
            description="Ship tracking bot is running!",
            color=0x00ff00
        )
        embed.add_field(
            name="⏰ Next Update",
            value=f"<t:{int(next_run.timestamp())}:R>",
            inline=False
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("Bot is running, but no scheduled updates are active.")

@bot.command(name='test')
async def test_connection(ctx):
    """Test API connection"""
    await ctx.send("🧪 Testing MarineTraffic API connection...")
    
    try:
        ship_data = await tracker.get_ship_location()
        if ship_data:
            await ctx.send("✅ API connection successful!")
        else:
            await ctx.send("❌ API connection failed. Check your API key and MMSI number.")
    except Exception as e:
        await ctx.send(f"❌ Error testing API: {str(e)}")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f'Error: {error}')

# Run the bot
if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("Bot shutting down...")
    except Exception as e:
        print(f"Error running bot: {str(e)}")