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
import random
from typing import Dict, Optional, List

# Load environment variables
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
SHIP_MMSI = os.getenv("SHIP_MMSI")
SHIP_NAME = os.getenv("SHIP_NAME", "Unknown Vessel")
UPDATE_INTERVAL_HOURS = int(os.getenv("UPDATE_INTERVAL_HOURS", "48"))

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

# Global variables
last_update = None
next_update = None
cached_ship_data = None

class EnhancedVesselFinderScraper:
    """Enhanced VesselFinder scraper with multiple strategies and fallbacks"""
    
    def __init__(self):
        self.session = None
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]
        
    async def get_session(self):
        """Get or create aiohttp session with rotating user agents"""
        if self.session is None or self.session.closed:
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
                'DNT': '1'
            }
            
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=5,
                ttl_dns_cache=300,
                use_dns_cache=True,
            )
            
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=45, connect=15),
                headers=headers,
                connector=connector
            )
        return self.session
        
    async def close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def fetch_ship_data(self, mmsi: str) -> Optional[Dict]:
        """Main method to fetch ship data with multiple strategies"""
        try:
            # Try multiple VesselFinder strategies
            strategies = [
                self._fetch_vessel_details_page,
                self._fetch_vessel_search_page,
                self._fetch_vessel_api_endpoint,
                self._fetch_vessel_mobile_page
            ]
            
            for strategy in strategies:
                try:
                    logger.info(f"Trying strategy: {strategy.__name__}")
                    data = await strategy(mmsi)
                    if data and self._validate_ship_data(data):
                        logger.info(f"Successfully fetched data using {strategy.__name__}")
                        return data
                except Exception as e:
                    logger.warning(f"Strategy {strategy.__name__} failed: {e}")
                    continue
                    
            # If all strategies fail, try fallback sources
            logger.info("All VesselFinder strategies failed, trying fallback sources")
            return await self._fetch_fallback_sources(mmsi)
            
        except Exception as e:
            logger.error(f"Error in fetch_ship_data: {e}")
            return None
            
    async def _fetch_vessel_details_page(self, mmsi: str) -> Optional[Dict]:
        """Strategy 1: Scrape main vessel details page"""
        session = await self.get_session()
        
        try:
            url = f"https://www.vesselfinder.com/vessels/details/{mmsi}"
            logger.info(f"Fetching VesselFinder details page: {url}")
            
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    logger.warning(f"VesselFinder details page returned status {response.status}")
                    return None
                    
                html = await response.text()
                return await self._parse_vessel_details_html(html, mmsi)
                
        except Exception as e:
            logger.error(f"Error fetching vessel details page: {e}")
            return None
            
    async def _fetch_vessel_search_page(self, mmsi: str) -> Optional[Dict]:
        """Strategy 2: Use search page to find vessel"""
        session = await self.get_session()
        
        try:
            # First search for the vessel
            search_url = f"https://www.vesselfinder.com/vessels?name={mmsi}"
            logger.info(f"Searching VesselFinder: {search_url}")
            
            async with session.get(search_url, allow_redirects=True) as response:
                if response.status != 200:
                    return None
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for vessel link in search results
                vessel_links = soup.find_all('a', href=re.compile(r'/vessels/'))
                
                for link in vessel_links:
                    if mmsi in link.get('href', ''):
                        detail_url = f"https://www.vesselfinder.com{link['href']}"
                        logger.info(f"Found vessel link: {detail_url}")
                        
                        # Fetch the detail page
                        async with session.get(detail_url, allow_redirects=True) as detail_response:
                            if detail_response.status == 200:
                                detail_html = await detail_response.text()
                                return await self._parse_vessel_details_html(detail_html, mmsi)
                                
            return None
            
        except Exception as e:
            logger.error(f"Error with search page strategy: {e}")
            return None
            
    async def _fetch_vessel_api_endpoint(self, mmsi: str) -> Optional[Dict]:
        """Strategy 3: Try to find and use API endpoints"""
        session = await self.get_session()
        
        try:
            # Try potential API endpoints
            api_urls = [
                f"https://www.vesselfinder.com/api/pub/vessel/{mmsi}",
                f"https://www.vesselfinder.com/api/vessel/{mmsi}",
                f"https://api.vesselfinder.com/vessel/{mmsi}",
                f"https://www.vesselfinder.com/clickhandler?mmsi={mmsi}"
            ]
            
            for api_url in api_urls:
                try:
                    logger.info(f"Trying API endpoint: {api_url}")
                    async with session.get(api_url, allow_redirects=True) as response:
                        if response.status == 200:
                            content_type = response.headers.get('content-type', '')
                            
                            if 'json' in content_type:
                                data = await response.json()
                                parsed_data = await self._parse_api_response(data, mmsi)
                                if parsed_data:
                                    return parsed_data
                            else:
                                # Might be HTML disguised as API
                                html = await response.text()
                                if html and len(html) > 100:
                                    return await self._parse_vessel_details_html(html, mmsi)
                                    
                except Exception as e:
                    logger.warning(f"API endpoint {api_url} failed: {e}")
                    continue
                    
            return None
            
        except Exception as e:
            logger.error(f"Error with API endpoint strategy: {e}")
            return None
            
    async def _fetch_vessel_mobile_page(self, mmsi: str) -> Optional[Dict]:
        """Strategy 4: Try mobile version of the site"""
        session = await self.get_session()
        
        try:
            # Update headers for mobile
            mobile_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            
            urls_to_try = [
                f"https://m.vesselfinder.com/vessels/{mmsi}",
                f"https://mobile.vesselfinder.com/vessels/{mmsi}",
                f"https://www.vesselfinder.com/vessels/{mmsi}?mobile=1"
            ]
            
            for url in urls_to_try:
                try:
                    logger.info(f"Trying mobile URL: {url}")
                    async with session.get(url, headers=mobile_headers, allow_redirects=True) as response:
                        if response.status == 200:
                            html = await response.text()
                            data = await self._parse_vessel_details_html(html, mmsi)
                            if data:
                                return data
                except Exception as e:
                    logger.warning(f"Mobile URL {url} failed: {e}")
                    continue
                    
            return None
            
        except Exception as e:
            logger.error(f"Error with mobile page strategy: {e}")
            return None
            
    async def _parse_vessel_details_html(self, html: str, mmsi: str) -> Optional[Dict]:
        """Parse vessel details from HTML content"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            ship_data = {'mmsi': mmsi}
            
            # Extract ship name - try multiple selectors
            name_selectors = [
                'h1.vessel-name',
                'h1',
                '.vessel-name',
                'title',
                '[data-label="Vessel Name"]',
                '.ship-name'
            ]
            
            for selector in name_selectors:
                try:
                    element = soup.select_one(selector)
                    if element:
                        name_text = element.get_text().strip()
                        # Clean up the name
                        name_text = re.sub(r'\s*-\s*VesselFinder.*', '', name_text)
                        name_text = re.sub(r'\s*\|\s*.*', '', name_text)
                        if name_text and len(name_text) > 2:
                            ship_data['name'] = name_text
                            break
                except:
                    continue
                    
            # Extract coordinates with multiple patterns
            page_text = soup.get_text()
            
            # Try different coordinate patterns
            coord_patterns = [
                r'Position[:\s]*(-?\d+\.?\d*)[°\s]*([NS]?)[\s,/-]+(-?\d+\.?\d*)[°\s]*([EW]?)',
                r'Latitude[:\s]*(-?\d+\.?\d*)[°\s]*([NS]?)[\s,]*Longitude[:\s]*(-?\d+\.?\d*)[°\s]*([EW]?)',
                r'(-?\d+\.\d{3,})[°\s]*([NS]?)[\s,/-]+(-?\d+\.\d{3,})[°\s]*([EW]?)',
                r'lat[:\s]*(-?\d+\.?\d*)[°\s]*([NS]?)[\s,]*lon[:\s]*(-?\d+\.?\d*)[°\s]*([EW]?)',
                r'"lat"[:\s]*(-?\d+\.?\d*).*?"lon"[:\s]*(-?\d+\.?\d*)'
            ]
            
            for pattern in coord_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    try:
                        if len(match.groups()) >= 4:
                            lat = float(match.group(1))
                            lat_dir = match.group(2)
                            lon = float(match.group(3))
                            lon_dir = match.group(4)
                            
                            if lat_dir == 'S':
                                lat = -lat
                            if lon_dir == 'W':
                                lon = -lon
                        else:
                            # Simple lat/lon pattern
                            lat = float(match.group(1))
                            lon = float(match.group(2))
                            
                        ship_data['latitude'] = lat
                        ship_data['longitude'] = lon
                        break
                    except:
                        continue
                        
            # Extract other vessel information
            info_patterns = {
                'speed': [
                    r'Speed[:\s]*(\d+\.?\d*)\s*(?:kn|knots?|kt)',
                    r'SOG[:\s]*(\d+\.?\d*)',
                    r'"speed"[:\s]*(\d+\.?\d*)'
                ],
                'course': [
                    r'Course[:\s]*(\d+\.?\d*)[°\s]*',
                    r'COG[:\s]*(\d+\.?\d*)',
                    r'"course"[:\s]*(\d+\.?\d*)'
                ],
                'heading': [
                    r'Heading[:\s]*(\d+\.?\d*)[°\s]*',
                    r'HDG[:\s]*(\d+\.?\d*)',
                    r'"heading"[:\s]*(\d+\.?\d*)'
                ],
                'destination': [
                    r'Destination[:\s]*([A-Z\s,.-]+?)(?:\n|$|\|)',
                    r'ETA[:\s]*([A-Z\s,.-]+?)(?:\n|$|\|)',
                    r'"destination"[:\s]*"([^"]+)"'
                ],
                'draught': [
                    r'Draught[:\s]*(\d+\.?\d*)\s*m',
                    r'Draft[:\s]*(\d+\.?\d*)\s*m'
                ]
            }
            
            for field, patterns in info_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        try:
                            value = match.group(1).strip()
                            if field in ['speed', 'course', 'heading', 'draught']:
                                ship_data[field] = float(value)
                            else:
                                ship_data[field] = value
                            break
                        except:
                            continue
                            
            # Look for status information
            status_patterns = [
                r'Status[:\s]*([^<\n]+)',
                r'Navigation Status[:\s]*([^<\n]+)',
                r'Nav Status[:\s]*([^<\n]+)'
            ]
            
            for pattern in status_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    status = match.group(1).strip()
                    if len(status) > 3:
                        ship_data['status'] = status
                        break
                        
            # Look for vessel type
            type_patterns = [
                r'Vessel Type[:\s]*([^<\n]+)',
                r'Ship Type[:\s]*([^<\n]+)',
                r'Type[:\s]*([^<\n]+)'
            ]
            
            for pattern in type_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    vessel_type = match.group(1).strip()
                    if len(vessel_type) > 3:
                        ship_data['vessel_type'] = vessel_type
                        break
                        
            # Add metadata
            ship_data['last_update'] = datetime.utcnow().isoformat()
            ship_data['source'] = 'VesselFinder (Enhanced Scraper)'
            
            # Set default name if not found
            if 'name' not in ship_data:
                ship_data['name'] = SHIP_NAME
                
            # Set default status if not found
            if 'status' not in ship_data:
                ship_data['status'] = 'Unknown'
                
            logger.info(f"Parsed ship data: {ship_data}")
            return ship_data if ship_data.get('latitude') is not None else None
            
        except Exception as e:
            logger.error(f"Error parsing vessel HTML: {e}")
            return None
            
    async def _parse_api_response(self, data: Dict, mmsi: str) -> Optional[Dict]:
        """Parse API response data"""
        try:
            ship_data = {'mmsi': mmsi}
            
            # Map common API fields
            field_mappings = {
                'name': ['name', 'shipName', 'vesselName', 'ship_name'],
                'latitude': ['lat', 'latitude', 'position_lat', 'lat_dd'],
                'longitude': ['lon', 'longitude', 'position_lon', 'lon_dd'],
                'speed': ['speed', 'sog', 'speed_over_ground'],
                'course': ['course', 'cog', 'course_over_ground'],
                'heading': ['heading', 'hdg', 'true_heading'],
                'status': ['status', 'navstat', 'navigation_status'],
                'destination': ['destination', 'dest', 'eta_destination'],
                'vessel_type': ['type', 'ship_type', 'vessel_type']
            }
            
            for field, possible_keys in field_mappings.items():
                for key in possible_keys:
                    if key in data and data[key] is not None:
                        ship_data[field] = data[key]
                        break
                        
            # Add metadata
            ship_data['last_update'] = datetime.utcnow().isoformat()
            ship_data['source'] = 'VesselFinder (API)'
            
            return ship_data if ship_data.get('latitude') is not None else None
            
        except Exception as e:
            logger.error(f"Error parsing API response: {e}")
            return None
            
    async def _fetch_fallback_sources(self, mmsi: str) -> Optional[Dict]:
        """Fallback to other maritime tracking sources"""
        try:
            # Try MarineTraffic as fallback
            mt_data = await self._fetch_marinetraffic_fallback(mmsi)
            if mt_data:
                return mt_data
                
            # Try MyShipTracking as fallback
            mst_data = await self._fetch_myshiptracking_fallback(mmsi)
            if mst_data:
                return mst_data
                
            return None
            
        except Exception as e:
            logger.error(f"Error with fallback sources: {e}")
            return None
            
    async def _fetch_marinetraffic_fallback(self, mmsi: str) -> Optional[Dict]:
        """Fallback to MarineTraffic"""
        session = await self.get_session()
        
        try:
            url = f"https://www.marinetraffic.com/en/ais/details/ships/mmsi:{mmsi}"
            async with session.get(url, allow_redirects=True) as response:
                if response.status == 200:
                    html = await response.text()
                    return await self._parse_marinetraffic_html(html, mmsi)
            return None
        except Exception as e:
            logger.error(f"MarineTraffic fallback failed: {e}")
            return None
            
    async def _parse_marinetraffic_html(self, html: str, mmsi: str) -> Optional[Dict]:
        """Parse MarineTraffic HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            ship_data = {'mmsi': mmsi}
            
            # Similar parsing logic as VesselFinder but adapted for MarineTraffic
            page_text = soup.get_text()
            
            # Extract coordinates
            coord_match = re.search(r'(-?\d+\.?\d*)[°\s]*([NS]?)[\s,]+(-?\d+\.?\d*)[°\s]*([EW]?)', page_text)
            if coord_match:
                lat = float(coord_match.group(1))
                lon = float(coord_match.group(3))
                
                if coord_match.group(2) == 'S':
                    lat = -lat
                if coord_match.group(4) == 'W':
                    lon = -lon
                    
                ship_data['latitude'] = lat
                ship_data['longitude'] = lon
                
            # Extract other data
            speed_match = re.search(r'(\d+\.?\d*)\s*kn', page_text, re.IGNORECASE)
            if speed_match:
                ship_data['speed'] = float(speed_match.group(1))
                
            ship_data['last_update'] = datetime.utcnow().isoformat()
            ship_data['source'] = 'MarineTraffic (Fallback)'
            ship_data['name'] = SHIP_NAME
            
            return ship_data if ship_data.get('latitude') is not None else None
            
        except Exception as e:
            logger.error(f"Error parsing MarineTraffic HTML: {e}")
            return None
            
    async def _fetch_myshiptracking_fallback(self, mmsi: str) -> Optional[Dict]:
        """Fallback to MyShipTracking"""
        session = await self.get_session()
        
        try:
            url = f"https://www.myshiptracking.com/vessels/mmsi-{mmsi}"
            async with session.get(url, allow_redirects=True) as response:
                if response.status == 200:
                    html = await response.text()
                    return await self._parse_myshiptracking_html(html, mmsi)
            return None
        except Exception as e:
            logger.error(f"MyShipTracking fallback failed: {e}")
            return None
            
    async def _parse_myshiptracking_html(self, html: str, mmsi: str) -> Optional[Dict]:
        """Parse MyShipTracking HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            ship_data = {'mmsi': mmsi}
            
            page_text = soup.get_text()
            
            # Extract coordinates
            lat_match = re.search(r'Latitude[:\s]*(-?\d+\.?\d*)', page_text, re.IGNORECASE)
            lon_match = re.search(r'Longitude[:\s]*(-?\d+\.?\d*)', page_text, re.IGNORECASE)
            
            if lat_match and lon_match:
                ship_data['latitude'] = float(lat_match.group(1))
                ship_data['longitude'] = float(lon_match.group(1))
                
            ship_data['last_update'] = datetime.utcnow().isoformat()
            ship_data['source'] = 'MyShipTracking (Fallback)'
            ship_data['name'] = SHIP_NAME
            
            return ship_data if ship_data.get('latitude') is not None else None
            
        except Exception as e:
            logger.error(f"Error parsing MyShipTracking HTML: {e}")
            return None
            
    def _validate_ship_data(self, data: Dict) -> bool:
        """Validate ship data quality"""
        if not data:
            return False
            
        # Must have coordinates
        if 'latitude' not in data or 'longitude' not in data:
            return False
            
        # Validate coordinate ranges
        lat = data['latitude']
        lon = data['longitude']
        
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return False
            
        # Check for obviously fake coordinates (0,0)
        if lat == 0 and lon == 0:
            return False
            
        return True
        
    async def search_ship_by_name(self, ship_name: str) -> Optional[str]:
        """Search for a ship by name to find its MMSI"""
        session = await self.get_session()
        
        try:
            # Try VesselFinder search
            search_url = f"https://www.vesselfinder.com/vessels?name={urllib.parse.quote(ship_name)}"
            
            async with session.get(search_url, allow_redirects=True) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Look for MMSI in search results
                    mmsi_pattern = r'MMSI[:\s]*(\d{9})'
                    mmsi_match = re.search(mmsi_pattern, html, re.IGNORECASE)
                    
                    if mmsi_match:
                        return mmsi_match.group(1)
                        
            return None
            
        except Exception as e:
            logger.error(f"Error searching for ship by name: {e}")
            return None
            
    async def generate_mock_data(self, mmsi: str) -> Dict:
        """Generate mock data for testing"""
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
            'source': 'Mock Data (Testing) - WORLD SAVING MODE'
        }

# Initialize the enhanced scraper
ship_tracker = EnhancedVesselFinderScraper()

# Rest of your Discord bot code remains the same...
def create_ship_embed(ship_data):
    """Create a Discord embed with ship information"""
    if not ship_data:
        embed = discord.Embed(
            title="❌ Ship Data Unavailable",
            description="Unable to fetch current ship information - THE MACHINES ARE FAILING!",
            color=0xff0000
        )
        return embed
        
    # Create main embed with world-saving theme
    embed = discord.Embed(
        title=f"🚢 {ship_data['name']} - WORLD SAVING VESSEL",
        description=f"MMSI: {ship_data['mmsi']} | Status: OPERATIONAL",
        color=0x00ff00,  # Green for world-saving success
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
    
    embed.set_footer(
        text="Location data retrieved via VesselFinder - Saving the World, One Ping at a Time 🌍",
        icon_url="https://emojicdn.elk.sh/🛰️"
    )
    
    return embed

# Periodic update task
@tasks.loop(hours=UPDATE_INTERVAL_HOURS)
async def update_ship_status():
    global last_update, cached_ship_data

    try:
        logger.info("Fetching ship data to update Discord...")
        ship_data = await ship_tracker.fetch_ship_data(SHIP_MMSI)
        
        if ship_data:
            cached_ship_data = ship_data
            last_update = datetime.utcnow()
            channel = bot.get_channel(DISCORD_CHANNEL_ID)
            if channel:
                embed = create_ship_embed(ship_data)
                await channel.send(embed=embed)
            else:
                logger.error("Could not find the target Discord channel.")
        else:
            logger.warning("Ship data fetch returned None.")

    except Exception as e:
        logger.error(f"Error in update_ship_status: {e}")
        traceback.print_exc()

# Event hook when bot is ready
@bot.event
async def on_ready():
    logger.info(f"Bot connected as {bot.user}")
    if not update_ship_status.is_running():
        update_ship_status.start()

# Manual command to trigger ship update
@bot.command(name='ship')
async def manual_ship_update(ctx):
    """Manually fetch and display ship info"""
    await ctx.send("🌍 Initiating manual world-saving vessel location update...")
    ship_data = await ship_tracker.fetch_ship_data(SHIP_MMSI)
    embed = create_ship_embed(ship_data)
    await ctx.send(embed=embed)

# Run the bot
if __name__ == '__main__':
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")