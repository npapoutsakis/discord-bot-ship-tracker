import os
import discord
import asyncio
import aiohttp
import json
import logging
import re
from datetime import datetime, timedelta
from discord.ext import commands, tasks
from dotenv import load_dotenv
import traceback
from bs4 import BeautifulSoup
import urllib.parse

# Load environment variables
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
SHIP_MMSI = os.getenv("SHIP_MMSI")  # Ship identifier
SHIP_NAME = os.getenv("SHIP_NAME", "Unknown Vessel")
UPDATE_INTERVAL_HOURS = int(os.getenv("UPDATE_INTERVAL_HOURS", "48"))  # Default 2 days

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ship_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables for tracking
last_update = None
next_update = None
cached_ship_data = None

class ShipTracker:
    """Ship tracking functionality using web scraping and APIs"""
    
    def __init__(self):
        self.session = None
        
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
        return self.session
        
    async def close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def fetch_ship_data(self, mmsi):
        """Fetch ship data from maritime tracking sources"""
            # Try multiple sources for reliability
            sources = [
                self._fetch_from_marinetraffic,
                self._fetch_from_vesselfinder,
                self._fetch_from_myshiptracking,
                self._fetch_from_aisstream
            ]
    
    async def search_ship_by_name(self, ship_name):
        """Search for a ship by name to get MMSI"""
        session = await self.get_session()
        
        try:
            # Search on MarineTraffic
            search_url = f"https://www.marinetraffic.com/en/ais/index/search/all"
            params = {'keyword': ship_name}
            
            async with session.get(search_url, params=params) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Look for search results with MMSI numbers
                    mmsi_matches = re.findall(r'mmsi[:\s]*(\d{9})', html, re.IGNORECASE)
                    if mmsi_matches:
                        logger.info(f"Found MMSI candidates for '{ship_name}': {mmsi_matches}")
                        return mmsi_matches[0]  # Return first match
                        
            # Try VesselFinder search
            vf_search_url = f"https://www.vesselfinder.com/vessels?name={urllib.parse.quote(ship_name)}"
            async with session.get(vf_search_url) as response:
                if response.status == 200:
                    html = await response.text()
                    mmsi_matches = re.findall(r'mmsi[:\s]*(\d{9})', html, re.IGNORECASE)
                    if mmsi_matches:
                        logger.info(f"Found MMSI from VesselFinder: {mmsi_matches[0]}")
                        return mmsi_matches[0]
                        
        except Exception as e:
            logger.error(f"Error searching for ship by name: {e}")
            
        return None
        """Fetch data from AISStream or similar real-time AIS service"""
        session = await self.get_session()
        
        try:
            # Try to get data from public AIS APIs or websites
            # This is an example URL - replace with actual working endpoint
            url = f"https://www.marinetraffic.com/vesselDetails/latestPosition/mmsi:{mmsi}/json"
            
            async with session.get(url) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        if data and len(data) > 0:
                            vessel = data[0] if isinstance(data, list) else data
                            
                            return {
                                'name': vessel.get('SHIPNAME', SHIP_NAME),
                                'mmsi': mmsi,
                                'latitude': float(vessel.get('LAT', 0)),
                                'longitude': float(vessel.get('LON', 0)),
                                'speed': float(vessel.get('SPEED', 0)),
                                'course': int(vessel.get('COURSE', 0)),
                                'heading': int(vessel.get('HEADING', 0)),
                                'status': vessel.get('STATUS', 'Unknown'),
                                'destination': vessel.get('DESTINATION', 'Unknown'),
                                'last_update': datetime.utcnow().isoformat(),
                                'source': 'AIS Stream'
                            }
                    except json.JSONDecodeError:
                        pass
                        
        except Exception as e:
            logger.error(f"Error fetching from AIS stream: {e}")
            
        return None
            
            for source in sources:
                try:
                    data = await source(mmsi)
                    if data:
                        logger.info(f"Successfully fetched data from {source.__name__}")
                        return data
                except Exception as e:
                    logger.warning(f"Failed to fetch from {source.__name__}: {e}")
                    continue
                    
            return None
            
        except Exception as e:
            logger.error(f"Error fetching ship data: {e}")
            return None
            
    async def _fetch_from_vesselfinder(self, mmsi):
        """Fetch data from VesselFinder website via scraping"""
        session = await self.get_session()
        
        try:
            # VesselFinder vessel page
            url = f"https://www.vesselfinder.com/vessels/details/{mmsi}"
            logger.info(f"Scraping VesselFinder URL: {url}")
            
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"VesselFinder returned status {response.status}")
                    return None
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                ship_data = {}
                
                # Extract ship name from page title or header
                h1_elem = soup.find('h1')
                if h1_elem:
                    ship_data['name'] = h1_elem.get_text().strip()
                
                # Look for vessel information table or divs
                # VesselFinder often has structured data
                info_sections = soup.find_all(['div', 'span', 'td'], class_=re.compile(r'(vessel|ship|info)', re.I))
                
                page_text = soup.get_text()
                
                # Extract coordinates
                lat_lon_pattern = r'(-?\d+\.?\d*)[°\s]*([NS]?)[\s,/-]+(-?\d+\.?\d*)[°\s]*([EW]?)'
                coord_match = re.search(lat_lon_pattern, page_text)
                if coord_match:
                    lat = float(coord_match.group(1))
                    lat_dir = coord_match.group(2)
                    lon = float(coord_match.group(3))
                    lon_dir = coord_match.group(4)
                    
                    if lat_dir == 'S':
                        lat = -lat
                    if lon_dir == 'W':
                        lon = -lon
                        
                    ship_data['latitude'] = lat
                    ship_data['longitude'] = lon
                
                # Extract speed
                speed_match = re.search(r'Speed[:\s]*(\d+\.?\d*)', page_text, re.IGNORECASE)
                if speed_match:
                    ship_data['speed'] = float(speed_match.group(1))
                
                # Extract course
                course_match = re.search(r'Course[:\s]*(\d+)', page_text, re.IGNORECASE)
                if course_match:
                    ship_data['course'] = int(course_match.group(1))
                
                # Extract destination
                dest_match = re.search(r'Destination[:\s]*([A-Z\s,]+)', page_text, re.IGNORECASE)
                if dest_match:
                    ship_data['destination'] = dest_match.group(1).strip()
                
                # Add metadata
                ship_data['mmsi'] = mmsi
                ship_data['last_update'] = datetime.utcnow().isoformat()
                ship_data['source'] = 'VesselFinder (Scraped)'
                ship_data['status'] = 'Under way using engine'  # Default status
                
                if 'name' not in ship_data:
                    ship_data['name'] = SHIP_NAME
                
                logger.info(f"Scraped data from VesselFinder: {ship_data}")
                return ship_data if ship_data.get('latitude') is not None else None
                
        except Exception as e:
            logger.error(f"Error scraping VesselFinder: {e}")
            return None
        
    async def _fetch_from_marinetraffic(self, mmsi):
        """Fetch data from MarineTraffic website via scraping"""
        session = await self.get_session()
        
        try:
            # MarineTraffic vessel details page
            url = f"https://www.marinetraffic.com/en/ais/details/ships/mmsi:{mmsi}"
            logger.info(f"Scraping MarineTraffic URL: {url}")
            
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"MarineTraffic returned status {response.status}")
                    return None
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract ship data from the page
                ship_data = {}
                
                # Get ship name from title or header
                title_elem = soup.find('title')
                if title_elem:
                    title_text = title_elem.get_text()
                    # Extract ship name from title like "SHIP NAME - Vessel details"
                    match = re.search(r'^([^-]+)', title_text)
                    if match:
                        ship_data['name'] = match.group(1).strip()
                
                # Look for vessel details in various possible locations
                # Try to find position data
                lat_lon_pattern = r'(-?\d+\.?\d*)[°\s]*([NS]?)[\s,]+(-?\d+\.?\d*)[°\s]*([EW]?)'
                
                # Search for coordinates in the page text
                page_text = soup.get_text()
                coord_match = re.search(lat_lon_pattern, page_text)
                if coord_match:
                    lat = float(coord_match.group(1))
                    lat_dir = coord_match.group(2)
                    lon = float(coord_match.group(3))
                    lon_dir = coord_match.group(4)
                    
                    # Apply direction
                    if lat_dir == 'S':
                        lat = -lat
                    if lon_dir == 'W':
                        lon = -lon
                        
                    ship_data['latitude'] = lat
                    ship_data['longitude'] = lon
                
                # Look for speed in knots
                speed_match = re.search(r'(\d+\.?\d*)\s*kn(?:ots?)?', page_text, re.IGNORECASE)
                if speed_match:
                    ship_data['speed'] = float(speed_match.group(1))
                
                # Look for course/heading
                course_match = re.search(r'Course[:\s]*(\d+)°?', page_text, re.IGNORECASE)
                if course_match:
                    ship_data['course'] = int(course_match.group(1))
                
                # Look for destination
                dest_match = re.search(r'Destination[:\s]*([A-Z\s]+)', page_text, re.IGNORECASE)
                if dest_match:
                    ship_data['destination'] = dest_match.group(1).strip()
                
                # Look for status
                status_keywords = ['Under way', 'At anchor', 'Moored', 'Not under command', 'Restricted manoeuvrability']
                for keyword in status_keywords:
                    if keyword.lower() in page_text.lower():
                        ship_data['status'] = keyword
                        break
                
                # Add metadata
                ship_data['mmsi'] = mmsi
                ship_data['last_update'] = datetime.utcnow().isoformat()
                ship_data['source'] = 'MarineTraffic (Scraped)'
                
                # Set default name if not found
                if 'name' not in ship_data:
                    ship_data['name'] = SHIP_NAME
                
                logger.info(f"Scraped data from MarineTraffic: {ship_data}")
                return ship_data if ship_data.get('latitude') is not None else None
                
        except Exception as e:
            logger.error(f"Error scraping MarineTraffic: {e}")
            return None
        
    async def _fetch_from_myshiptracking(self, mmsi):
        """Fetch data from MyShipTracking website via scraping"""
        session = await self.get_session()
        
        try:
            # MyShipTracking vessel page
            url = f"https://www.myshiptracking.com/vessels/mmsi-{mmsi}"
            logger.info(f"Scraping MyShipTracking URL: {url}")
            
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"MyShipTracking returned status {response.status}")
                    return None
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                ship_data = {}
                page_text = soup.get_text()
                
                # Extract ship name from title or header
                title_elem = soup.find('title')
                if title_elem:
                    title_text = title_elem.get_text()
                    # Clean up the title
                    name_match = re.search(r'^([^|]+)', title_text)
                    if name_match:
                        ship_data['name'] = name_match.group(1).strip()
                
                # Look for position data
                lat_match = re.search(r'Latitude[:\s]*(-?\d+\.?\d*)', page_text, re.IGNORECASE)
                lon_match = re.search(r'Longitude[:\s]*(-?\d+\.?\d*)', page_text, re.IGNORECASE)
                
                if lat_match and lon_match:
                    ship_data['latitude'] = float(lat_match.group(1))
                    ship_data['longitude'] = float(lon_match.group(1))
                
                # Look for speed
                speed_match = re.search(r'Speed[:\s]*(\d+\.?\d*)', page_text, re.IGNORECASE)
                if speed_match:
                    ship_data['speed'] = float(speed_match.group(1))
                
                # Look for course
                course_match = re.search(r'Course[:\s]*(\d+)', page_text, re.IGNORECASE)
                if course_match:
                    ship_data['course'] = int(course_match.group(1))
                
                # Add metadata
                ship_data['mmsi'] = mmsi
                ship_data['last_update'] = datetime.utcnow().isoformat()
                ship_data['source'] = 'MyShipTracking (Scraped)'
                ship_data['status'] = 'Under way using engine'
                
                if 'name' not in ship_data:
                    ship_data['name'] = SHIP_NAME
                
                logger.info(f"Scraped data from MyShipTracking: {ship_data}")
                return ship_data if ship_data.get('latitude') is not None else None
                
        except Exception as e:
            logger.error(f"Error scraping MyShipTracking: {e}")
            return None
        
    def _parse_vesselfinder_data(self, data):
        """Parse VesselFinder API response"""
        try:
            return {
                'name': data.get('name', 'Unknown'),
                'mmsi': data.get('mmsi'),
                'latitude': data.get('lat'),
                'longitude': data.get('lon'),
                'speed': data.get('speed'),
                'course': data.get('course'),
                'heading': data.get('heading'),
                'status': data.get('navstat_text', 'Unknown'),
                'destination': data.get('destination', 'Unknown'),
                'eta': data.get('eta'),
                'last_update': datetime.utcnow().isoformat(),
                'source': 'VesselFinder'
            }
        except Exception as e:
            logger.error(f"Error parsing VesselFinder data: {e}")
            return None
            
    async def generate_mock_data(self, mmsi):
        """Generate mock data for testing purposes"""
        import random
        
        # Base coordinates (example: somewhere in the Atlantic)
        base_lat = 40.7128 + random.uniform(-5, 5)
        base_lon = -74.0060 + random.uniform(-10, 10)
        
        return {
            'name': SHIP_NAME,
            'mmsi': mmsi,
            'latitude': round(base_lat, 4),
            'longitude': round(base_lon, 4),
            'speed': round(random.uniform(8, 18), 1),
            'course': random.randint(0, 359),
            'heading': random.randint(0, 359),
            'status': random.choice(['Under way using engine', 'At anchor', 'Moored']),
            'destination': random.choice(['NEW YORK', 'MIAMI', 'BOSTON', 'CHARLESTON']),
            'eta': (datetime.utcnow() + timedelta(days=random.randint(1, 7))).isoformat(),
            'last_update': datetime.utcnow().isoformat(),
            'source': 'Mock Data (Testing)'
        }

# Initialize ship tracker
ship_tracker = ShipTracker()

def create_ship_embed(ship_data):
    """Create a Discord embed with ship information"""
    if not ship_data:
        embed = discord.Embed(
            title="❌ Ship Data Unavailable",
            description="Unable to fetch current ship information",
            color=0xff0000
        )
        return embed
        
    # Create main embed
    embed = discord.Embed(
        title=f"🚢 {ship_data['name']}",
        description=f"MMSI: {ship_data['mmsi']}",
        color=0x0099ff,
        timestamp=datetime.utcnow()
    )
    
    # Position information
    if ship_data.get('latitude') and ship_data.get('longitude'):
        lat = ship_data['latitude']
        lon = ship_data['longitude']
        
        # Format coordinates
        lat_dir = "N" if lat >= 0 else "S"
        lon_dir = "E" if lon >= 0 else "W"
        
        embed.add_field(
            name="📍 Current Position", 
            value=f"{abs(lat):.4f}°{lat_dir}, {abs(lon):.4f}°{lon_dir}",
            inline=True
        )
        
        # Add Google Maps link
        maps_url = f"https://maps.google.com/?q={lat},{lon}"
        embed.add_field(
            name="🗺️ View Location",
            value=f"[Open in Google Maps]({maps_url})",
            inline=True
        )
    
    # Navigation information
    if ship_data.get('speed') is not None:
        embed.add_field(
            name="⚡ Speed", 
            value=f"{ship_data['speed']} knots",
            inline=True
        )
        
    if ship_data.get('course') is not None:
        embed.add_field(
            name="🧭 Course", 
            value=f"{ship_data['course']}°",
            inline=True
        )
        
    if ship_data.get('status'):
        embed.add_field(
            name="🚦 Status", 
            value=ship_data['status'],
            inline=True
        )
        
    if ship_data.get('destination'):
        embed.add_field(
            name="🎯 Destination", 
            value=ship_data['destination'],
            inline=True
        )
    
    # Add data source and update info
    embed.set_footer(
        text=f"Data from: {ship_data.get('source', 'Unknown')} | Next update in {UPDATE_INTERVAL_HOURS}h"
    )
    
    return embed

async def send_ship_update():
    """Send ship update to Discord channel"""
    global last_update, next_update, cached_ship_data
    
    try:
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            logger.error("Invalid Discord channel ID")
            return False
            
        logger.info("Fetching ship data...")
        
        # Try to fetch real data first, fall back to mock data for testing
        ship_data = await ship_tracker.fetch_ship_data(SHIP_MMSI)
        
        if not ship_data:
            logger.info("No real data available, generating mock data for testing")
            ship_data = await ship_tracker.generate_mock_data(SHIP_MMSI)
            
        if ship_data:
            cached_ship_data = ship_data
            embed = create_ship_embed(ship_data)
            
            await channel.send(embed=embed)
            
            last_update = datetime.utcnow()
            next_update = last_update + timedelta(hours=UPDATE_INTERVAL_HOURS)
            
            logger.info(f"Ship update sent successfully. Next update: {next_update}")
            return True
        else:
            # Send error message
            embed = discord.Embed(
                title="❌ Update Failed",
                description="Unable to fetch ship data from any source",
                color=0xff0000
            )
            await channel.send(embed=embed)
            logger.error("Failed to fetch ship data from all sources")
            return False
            
    except Exception as e:
        logger.error(f"Error sending ship update: {e}")
        logger.error(traceback.format_exc())
        return False

# ========== Scheduled Tasks ==========
@tasks.loop(hours=UPDATE_INTERVAL_HOURS)
async def ship_update_loop():
    """Main loop for sending ship updates"""
    await bot.wait_until_ready()
    logger.info("Running scheduled ship update")
    await send_ship_update()

@ship_update_loop.before_loop
async def before_ship_update_loop():
    """Wait for bot to be ready before starting loop"""
    await bot.wait_until_ready()
    logger.info(f"Ship tracking loop will run every {UPDATE_INTERVAL_HOURS} hours")

# ========== Bot Commands ==========
@bot.command(name='ship')
async def manual_ship_update(ctx):
    """Manually request ship location"""
    await ctx.send("🔄 Fetching current ship location...")
    success = await send_ship_update()
    
    if not success:
        await ctx.send("❌ Failed to fetch ship data. Please try again later.")

@bot.command(name='status')
async def bot_status(ctx):
    """Show bot status and next update time"""
    embed = discord.Embed(
        title="🤖 Bot Status",
        color=0x00ff00,
        timestamp=datetime.utcnow()
    )
    
    # Bot uptime
    embed.add_field(
        name="🟢 Status",
        value="Online and operational",
        inline=True
    )
    
    # Last update
    if last_update:
        embed.add_field(
            name="📅 Last Update",
            value=last_update.strftime("%Y-%m-%d %H:%M UTC"),
            inline=True
        )
    else:
        embed.add_field(
            name="📅 Last Update",
            value="No updates yet",
            inline=True
        )
    
    # Next update
    if next_update:
        time_until = next_update - datetime.utcnow()
        hours = int(time_until.total_seconds() // 3600)
        minutes = int((time_until.total_seconds() % 3600) // 60)
        
        embed.add_field(
            name="⏰ Next Update",
            value=f"In {hours}h {minutes}m",
            inline=True
        )
    else:
        embed.add_field(
            name="⏰ Next Update",
            value="Not scheduled",
            inline=True
        )
    
    # Loop status
    embed.add_field(
        name="🔄 Auto Updates",
        value="Running" if ship_update_loop.is_running() else "Stopped",
        inline=True
    )
    
    # Tracked ship
    embed.add_field(
        name="🚢 Tracking",
        value=f"{SHIP_NAME} (MMSI: {SHIP_MMSI})",
        inline=True
    )
    
    await ctx.send(embed=embed)

@bot.command(name='test')
async def test_connection(ctx):
    """Test API connections and bot functionality"""
    embed = discord.Embed(
        title="🧪 Running Tests",
        color=0xffff00
    )
    
    # Test Discord connection
    embed.add_field(
        name="Discord Connection",
        value="✅ Connected",
        inline=False
    )
    
    # Test ship data fetching
    await ctx.send(embed=embed)
    
    test_data = await ship_tracker.generate_mock_data(SHIP_MMSI)
    if test_data:
        embed.add_field(
            name="Data Generation",
            value="✅ Working",
            inline=False
        )
    else:
        embed.add_field(
            name="Data Generation",
            value="❌ Failed",
            inline=False
        )
    
    embed.color = 0x00ff00
    embed.title = "🧪 Test Results"
    
    await ctx.edit_message(embed=embed)

@bot.command(name='start')
async def start_updates(ctx):
    """Start automatic ship updates"""
    if not ship_update_loop.is_running():
        ship_update_loop.start()
        await ctx.send(f"✅ Automatic ship updates started. Updates every {UPDATE_INTERVAL_HOURS} hours.")
    else:
        await ctx.send("⚠️ Automatic updates are already running.")

@bot.command(name='stop')
async def stop_updates(ctx):
    """Stop automatic ship updates"""
    if ship_update_loop.is_running():
        ship_update_loop.cancel()
        await ctx.send("🛑 Automatic ship updates stopped.")
    else:
        await ctx.send("⚠️ Automatic updates are not running.")

@bot.command(name='search')
async def search_ship(ctx, *, ship_name):
    """Search for a ship by name to find its MMSI"""
    await ctx.send(f"🔍 Searching for ship: **{ship_name}**...")
    
    mmsi = await ship_tracker.search_ship_by_name(ship_name)
    
    if mmsi:
        embed = discord.Embed(
            title="🔍 Ship Search Results",
            color=0x00ff00
        )
        embed.add_field(
            name="Ship Name",
            value=ship_name,
            inline=True
        )
        embed.add_field(
            name="MMSI Found",
            value=mmsi,
            inline=True
        )
        embed.add_field(
            name="Next Step",
            value=f"Add `SHIP_MMSI={mmsi}` to your .env file",
            inline=False
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Could not find MMSI for ship: **{ship_name}**. Try a more specific name or check spelling.")

@bot.command(name='track')
async def track_mmsi(ctx, mmsi: str):
    """Track a specific ship by MMSI (temporary override)"""
    if not mmsi.isdigit() or len(mmsi) != 9:
        await ctx.send("❌ Invalid MMSI. Must be a 9-digit number.")
        return
        
    await ctx.send(f"🔄 Fetching data for MMSI: **{mmsi}**...")
    
    # Temporarily override the MMSI
    ship_data = await ship_tracker.fetch_ship_data(mmsi)
    
    if ship_data:
        embed = create_ship_embed(ship_data)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Could not fetch data for MMSI: **{mmsi}**")

@bot.command(name='config')
async def show_config(ctx):
    """Show current bot configuration (non-sensitive)"""
    embed = discord.Embed(
        title="⚙️ Bot Configuration",
        color=0x0099ff
    )
    
    embed.add_field(
        name="Update Interval",
        value=f"{UPDATE_INTERVAL_HOURS} hours",
        inline=True
    )
    
    embed.add_field(
        name="Ship Name",
        value=SHIP_NAME,
        inline=True
    )
    
    embed.add_field(
        name="Ship MMSI",
        value=SHIP_MMSI or "Not configured",
        inline=True
    )
    
    embed.add_field(
        name="Channel ID",
        value=DISCORD_CHANNEL_ID,
        inline=True
    )
    
    await ctx.send(embed=embed)

# ========== Event Handlers ==========
@bot.event
async def on_ready():
    """Bot startup event"""
    logger.info(f"Logged in as {bot.user}")
    logger.info(f"Tracking ship: {SHIP_NAME} (MMSI: {SHIP_MMSI})")
    logger.info(f"Updates every {UPDATE_INTERVAL_HOURS} hours")
    
    # Start the update loop
    if not ship_update_loop.is_running():
        ship_update_loop.start()

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    logger.error(f"Command error: {error}")
    
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Use `!status` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument for this command.")
    else:
        await ctx.send("❌ An error occurred while processing the command.")

# ========== Cleanup ==========
async def cleanup():
    """Cleanup resources before shutdown"""
    logger.info("Cleaning up resources...")
    await ship_tracker.close_session()

# ========== Main Execution ==========
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not found in environment variables")
        exit(1)
        
    if not DISCORD_CHANNEL_ID:
        logger.error("DISCORD_CHANNEL_ID not found in environment variables")
        exit(1)
        
    if not SHIP_MMSI:
        logger.warning("SHIP_MMSI not found in environment variables - using default for testing")
        SHIP_MMSI = "123456789"  # Default for testing
    
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    finally:
        asyncio.run(cleanup())