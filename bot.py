import os
import discord
import asyncio
import json
import logging
from datetime import datetime, timedelta
from discord.ext import commands, tasks
from dotenv import load_dotenv
import traceback
import random
from typing import Dict, Optional, List
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
from dataclasses import dataclass

# Load environment variables
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
SHIP_MMSI = os.getenv("SHIP_MMSI", "538010457")  # Default MMSI
SHIP_NAME = os.getenv("SHIP_NAME", "STI MAESTRO")  # Default ship name
UPDATE_INTERVAL_HOURS = 48  # Fixed at 2 days (48 hours)
JSON_DIRECTORY = os.getenv("JSON_DIRECTORY", "ship_data")  # Directory to store JSON files
SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "screenshots")  # Directory for screenshots
FRIEND_NAME = os.getenv("FRIEND_NAME", "Kanakaris")  # Our friend's name
MAX_JSON_FILES = 5  # Maximum number of JSON files to keep

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

# Farewell messages for our friend
farewell_messages = [
    "May the winds guide you to new adventures!",
    "The sea calls to the brave. Sail on, friend!",
    "The horizon awaits your journey!",
    "Every wave brings new opportunities. Godspeed!",
    "We'll keep watch over your journey from afar.",
    "Though the seas may separate us, our friendship remains strong.",
    "Until our paths cross again, sail safely!",
    "Your courage inspires us all. Bon voyage!",
    "May clear skies and calm seas accompany you always.",
    "We'll miss you, but we celebrate your new adventure!"
]

@dataclass
class ShipData:
    """Data structure for ship information"""
    name: Optional[str] = None
    speed: Optional[str] = None
    course: Optional[str] = None
    status: Optional[str] = None
    ship_type: Optional[str] = None
    coordinates: Optional[str] = None
    timestamp: Optional[str] = None
    mmsi: Optional[str] = None

class MinimalShipTracker:
    def __init__(self, headless: bool = True, screenshot_dir: str = SCREENSHOT_DIR):
        self.headless = headless
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(exist_ok=True)
        self.driver = None
        self.screenshots_taken = []  # Track screenshots for cleanup

    def setup_driver(self):
        """Initialize Chrome WebDriver with minimal settings"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1280,720")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("WebDriver initialized")
    
    def handle_consent_banner(self):
        """Simple consent banner handler - clicks first consent/accept button found"""
        try:
            elements = self.driver.find_elements(By.XPATH, "//button[contains(@class, 'fc-button')]")
            if elements:
                for element in elements:
                    if element.is_displayed():
                        element.click()
                        return True

            logger.info("No consent banner detected or couldn't handle it")
        except Exception as e:
            logger.warning(f"Error handling consent: {e}")
        
        return False

    def take_screenshot(self, filename: str) -> str:
        """Take a screenshot and save it, tracking it for later cleanup"""
        try:
            filepath = self.screenshot_dir / f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            self.driver.save_screenshot(str(filepath))
            logger.info(f"Screenshot saved: {filepath}")
            self.screenshots_taken.append(filepath)  # Track for cleanup
            return str(filepath)
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return ""
    
    def cleanup_screenshots(self):
        """Remove all screenshots taken during this session"""
        logger.info(f"Cleaning up {len(self.screenshots_taken)} screenshots...")
        for screenshot in self.screenshots_taken:
            try:
                if screenshot.exists():
                    screenshot.unlink()  # Delete the file
                    logger.info(f"Deleted screenshot: {screenshot}")
            except Exception as e:
                logger.warning(f"Failed to delete screenshot {screenshot}: {e}")

    def get_coordinates(self) -> Optional[tuple]:
        """Extract coordinates by double right-clicking and selecting 'Get Coordinates'"""
        try:
            # Log the current date/time and user info
            logger.info("Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): 2025-06-14 22:11:57")
            logger.info("Current User's Login: npapoutsakis")
            logger.info(f"Attempting to get {FRIEND_NAME}'s ship coordinates...")
            
            # First take a screenshot of the initial state
            self.take_screenshot("initial_state")
            
            # Get the dimensions of the visible part of the page
            window_width = self.driver.execute_script("return window.innerWidth")
            window_height = self.driver.execute_script("return window.innerHeight")
            
            # Calculate the middle point
            middle_x = window_width // 2
            middle_y = window_height // 2
            
            logger.info(f"Page dimensions: {window_width}x{window_height}, middle point: ({middle_x}, {middle_y})")
            
            # Move to the middle of the page
            actions = ActionChains(self.driver)
            actions.move_by_offset(middle_x, middle_y).perform()
            logger.info("Moved to the middle of the page")
            time.sleep(1)
            
            # First right-click
            logger.info("*** PERFORMING FIRST RIGHT-CLICK ***")
            actions = ActionChains(self.driver)
            actions.context_click().perform()
            time.sleep(2)
            
            # Take screenshot after first right-click
            self.take_screenshot("after_first_right_click")
            
            # Second right-click
            logger.info("*** PERFORMING SECOND RIGHT-CLICK ***")
            actions = ActionChains(self.driver)
            actions.context_click().perform()
            time.sleep(2)
            
            # Take screenshot after second right-click
            self.take_screenshot("after_second_right_click")
            
            # Look specifically for the exact "Get Coordinates" element you provided
            exact_selectors = [
                "//a[contains(@class, 'dropdown-item') and contains(@onclick, 'mySTmap_command.getCoordinates') and contains(text(), 'Get Coordinates')]",
                "//a[contains(@onclick, 'mySTmap_command.getCoordinates')]",
                "//a[contains(@class, 'dropdown-item') and contains(text(), 'Get Coordinates')]",
                # Fallback to more generic selectors
                "//a[contains(text(), 'Get Coordinates')]",
                "//a[contains(@class, 'dropdown-item')]"
            ]
            
            # Take screenshot of the context menu
            self.take_screenshot("context_menu")
            
            menu_item_found = False
            
            for selector in exact_selectors:
                try:
                    logger.info(f"Looking for menu item with selector: {selector}")
                    elements = self.driver.find_elements(By.XPATH, selector)
                    
                    if len(elements) > 0:
                        logger.info(f"Found {len(elements)} potential menu items")
                        
                    for element in elements:
                        if element.is_displayed():
                            logger.info(f"Found visible menu item: '{element.text}' using selector {selector}")
                            element.click()
                            logger.info("Clicked on menu item")
                            menu_item_found = True
                            time.sleep(2)
                            break
                    
                    if menu_item_found:
                        break
                except Exception as e:
                    logger.warning(f"Error with selector {selector}: {e}")
                    continue
            
            # If we still didn't find the menu item, try JavaScript execution
            if not menu_item_found:
                logger.info("Trying to execute the getCoordinates function directly via JavaScript")
                try:
                    self.driver.execute_script("mySTmap_command.getCoordinates();")
                    logger.info("Executed getCoordinates function via JavaScript")
                    menu_item_found = True
                    time.sleep(2)
                except Exception as e:
                    logger.warning(f"Error executing JavaScript: {e}")
            
            # Take screenshot after clicking menu item or executing JavaScript
            self.take_screenshot("after_menu_interaction")
            
            # Try to extract coordinates from Swal2 alert
            coordinates = None
            try:
                swal_title = self.driver.find_element(By.ID, "swal2-title")
                if swal_title.is_displayed() and "Coordinates" in swal_title.text:
                    logger.info("Found Swal2 alert with coordinates")
                    
                    # Take screenshot of coordinates dialog
                    self.take_screenshot("coordinates_dialog")
                    
                    # Get coordinates from content
                    swal_content = self.driver.find_element(By.ID, "swal2-content")
                    coord_text = swal_content.text
                    logger.info(f"Swal2 content: {coord_text}")
                    
                    # Extract coordinates using regex
                    import re
                    numbers = re.findall(r'-?\d+\.\d+', coord_text)
                    if len(numbers) >= 2:
                        lat = float(numbers[0])
                        lon = float(numbers[1])
                        coordinates = (lat, lon)
                        logger.info(f"Extracted {FRIEND_NAME}'s coordinates: {coordinates}")
                        
                        # Take final screenshot with coordinates
                        self.take_screenshot("extracted_coordinates")
                        
                        # Close the dialog by clicking OK button
                        try:
                            ok_button = self.driver.find_element(By.XPATH, 
                                "//button[contains(@class, 'swal2-confirm')]")
                            ok_button.click()
                            logger.info("Closed Swal2 alert")
                        except:
                            logger.warning("Could not close Swal2 alert")
                    else:
                        logger.warning("Could not extract coordinates from text")
            except NoSuchElementException:
                logger.warning("Swal2 alert elements not found")
            
            return coordinates
        
        except Exception as e:
            logger.error(f"Error in coordinates extraction: {e}")
            return None

    def extract_ship_data(self, mmsi: str) -> ShipData:
        """Extract ship data using precise DOM selectors"""
        url = f"https://www.myshiptracking.com/?mmsi={mmsi}"
        ship_data = ShipData(mmsi=mmsi, timestamp=datetime.now().isoformat())
        
        try:
            self.setup_driver()
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(1)
            
            self.handle_consent_banner()
            selectors = {
                'speed': {
                    'method': By.ID,
                    'value': "cval-sog",
                    'process': lambda x: x.replace('Knots', '').strip()
                },
                'course': {
                    'method': By.ID, 
                    'value': "cval-cog",
                    'process': lambda x: x.replace('°', '').strip()
                },
                'status': {
                    'method': By.XPATH,
                    'value': "//div[text()='Status']/following-sibling::div[@class='font-weight-bold']",
                    'process': lambda x: x.strip()
                },
                'ship_type': {
                    'method': By.XPATH,
                    'value': "//div[text()='Type']/following-sibling::div[@class='font-weight-bold']",
                    'process': lambda x: x.strip()
                }
            }
            
            # Extract each field using its selector
            for field, selector_info in selectors.items():
                try:
                    element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((selector_info['method'], selector_info['value']))
                    )
                    value = selector_info['process'](element.text)
                    setattr(ship_data, field, value)
                    logger.info(f"Extracted {field}: {value}")
                except Exception as e:
                    logger.warning(f"Could not extract {field}: {e}")
            
            try:
                # First try the exact ID from your HTML
                name_element = self.driver.find_element(By.ID, "mapPopupTitle")
                if name_element and name_element.text:
                    ship_data.name = name_element.text.strip()
                    logger.info(f"Extracted name from mapPopupTitle: {ship_data.name}")
            except NoSuchElementException:
                logger.warning("mapPopupTitle element not found, trying alternative approaches")
                
                try:
                    # Find and click on ship marker to make the popup appear
                    markers = self.driver.find_elements(By.CSS_SELECTOR, ".ship-marker, .vessel-marker, .leaflet-marker-icon")
                    for marker in markers:
                        if marker.is_displayed():
                            logger.info("Clicking on ship marker to reveal popup")
                            marker.click()
                            time.sleep(1)
                            
                            # Now try to get the name again
                            try:
                                name_element = WebDriverWait(self.driver, 3).until(
                                    EC.presence_of_element_located((By.ID, "mapPopupTitle"))
                                )
                                ship_data.name = name_element.text.strip()
                                logger.info(f"Extracted name after clicking: {ship_data.name}")
                                break
                            except:
                                logger.warning("mapPopupTitle still not found after clicking marker")
                except Exception as e:
                    logger.warning(f"Error clicking ship marker: {e}")
                
                # If still not found, try to get from title or other elements
                if not ship_data.name:
                    # Try page title
                    page_title = self.driver.title
                    if "myshiptracking" in page_title.lower() and "-" in page_title:
                        ship_name_part = page_title.split("-")[0].strip()
                        ship_data.name = ship_name_part
                        logger.info(f"Extracted name from title: {ship_data.name}")
            
            # Get coordinates using the double right-click method
            coordinates = self.get_coordinates()
            if coordinates:
                ship_data.coordinates = f"{coordinates[0]}, {coordinates[1]}"
                logger.info(f"Set coordinates: {ship_data.coordinates}")
            
            return ship_data
            
        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            return ship_data
        finally:
            if self.driver:
                # Cleanup screenshots before quitting
                self.cleanup_screenshots()
                
                # Close the driver
                self.driver.quit()
                logger.info("WebDriver closed")
    
    def save_data(self, ship_data: ShipData, filename: str = None):
        """Save extracted data to JSON file"""
        import json
        
        if not filename:
            filename = f"ship_data_{ship_data.mmsi}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Convert dataclass to dictionary
        data_dict = {k: v if v is not None else "N/A" for k, v in ship_data.__dict__.items()}
        
        with open(filename, 'w') as f:
            json.dump(data_dict, f, indent=2)
        
        logger.info(f"Saved {FRIEND_NAME}'s journey data to: {filename}")

# File-based ship tracker class for the Discord bot
class ShipFileTracker:
    """Handles ship tracking via JSON files instead of scraping"""
    
    def __init__(self, json_directory: str = JSON_DIRECTORY):
        self.json_directory = Path(json_directory)
        self.json_directory.mkdir(exist_ok=True)
    
    def find_latest_json(self, mmsi: str = None) -> Optional[Path]:
        """Find the latest JSON file for the ship"""
        try:
            # Look for JSON files that match our pattern
            if mmsi:
                pattern = f"updated_ship_data_{mmsi}_*.json"
                files = list(self.json_directory.glob(pattern))
                
                # If no updated files, look for regular files
                if not files:
                    pattern = f"ship_data_{mmsi}_*.json"
                    files = list(self.json_directory.glob(pattern))
            else:
                # If no MMSI specified, get all JSON files
                files = list(self.json_directory.glob("*ship_data*.json"))
            
            # Sort by modification time, newest first
            if files:
                files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                return files[0]
            
            return None
        except Exception as e:
            logger.error(f"Error finding latest JSON: {e}")
            return None
    
    def get_all_json_files(self, mmsi: str = None) -> List[Path]:
        """Get all JSON files for the ship, sorted by modification time (newest first)"""
        try:
            # Look for JSON files that match our pattern
            if mmsi:
                pattern = f"*ship_data_{mmsi}_*.json"
            else:
                pattern = "*ship_data_*.json"
                
            files = list(self.json_directory.glob(pattern))
            
            # Sort by modification time, newest first
            files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            return files
        except Exception as e:
            logger.error(f"Error getting all JSON files: {e}")
            return []
    
    def cleanup_old_json_files(self, mmsi: str = None, keep_count: int = MAX_JSON_FILES):
        """Delete old JSON files, keeping only the most recent ones"""
        try:
            all_files = self.get_all_json_files(mmsi)
            
            # If we have more files than we want to keep
            if len(all_files) > keep_count:
                # Get the files to delete (everything after the keep_count)
                files_to_delete = all_files[keep_count:]
                
                # Delete each file
                for file in files_to_delete:
                    try:
                        file.unlink()
                        logger.info(f"Deleted old JSON file: {file}")
                    except Exception as e:
                        logger.warning(f"Failed to delete JSON file {file}: {e}")
                
                logger.info(f"Cleaned up JSON files, kept {keep_count} most recent, deleted {len(files_to_delete)}")
            else:
                logger.info(f"No JSON cleanup needed, only have {len(all_files)} files (keeping {keep_count})")
        except Exception as e:
            logger.error(f"Error cleaning up old JSON files: {e}")
    
    async def get_ship_data(self, mmsi: str = None) -> Optional[Dict]:
        """Get ship data from the latest JSON file"""
        try:
            latest_json = self.find_latest_json(mmsi)
            if not latest_json:
                logger.warning(f"No JSON files found for MMSI: {mmsi}")
                return None
            
            with open(latest_json, 'r') as f:
                data = json.load(f)
                
            # Check if coordinates are in expected format
            if 'coordinates' in data and isinstance(data['coordinates'], str):
                # Parse coordinates from string format "lat, lon"
                try:
                    lat_lon = data['coordinates'].split(',')
                    if len(lat_lon) == 2:
                        lat = float(lat_lon[0].strip())
                        lon = float(lat_lon[1].strip())
                        data['latitude'] = lat
                        data['longitude'] = lon
                except Exception as e:
                    logger.error(f"Error parsing coordinates: {e}")
            
            # Ensure consistent data structure with timestamps
            if 'timestamp' in data:
                data['last_update'] = data['timestamp']
            else:
                data['last_update'] = datetime.utcnow().isoformat()
                
            logger.info(f"Loaded {FRIEND_NAME}'s journey data from {latest_json}")
            return data
            
        except Exception as e:
            logger.error(f"Error getting ship data from file: {e}")
            return None
    
    async def fetch_ship_data(self, mmsi: str) -> Optional[Dict]:
        """Wrapper to match the interface of the original scraper"""
        return await self.get_ship_data(mmsi)
    
    async def fetch_new_coordinates(self, mmsi: str) -> Optional[Dict]:
        """Get fresh coordinates using the Selenium tracker"""
        try:
            logger.info(f"Starting Selenium tracker to get fresh coordinates for {FRIEND_NAME}'s journey...")
            
            # Use the MinimalShipTracker to get fresh data
            tracker = MinimalShipTracker(headless=False)
            ship_data = tracker.extract_ship_data(mmsi)
            
            # Save the new data to a JSON file
            json_filename = f"{self.json_directory}/ship_data_{mmsi}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            tracker.save_data(ship_data, json_filename)
            
            # Cleanup old JSON files after saving new one
            self.cleanup_old_json_files(mmsi, MAX_JSON_FILES)
            
            # Convert to dictionary format
            data_dict = {k: v if v is not None else "N/A" for k, v in ship_data.__dict__.items()}
            
            # Parse coordinates from string format if needed
            if data_dict.get('coordinates') and isinstance(data_dict['coordinates'], str):
                try:
                    lat_lon = data_dict['coordinates'].split(',')
                    if len(lat_lon) == 2:
                        data_dict['latitude'] = float(lat_lon[0].strip())
                        data_dict['longitude'] = float(lat_lon[1].strip())
                except:
                    pass
            
            return data_dict
            
        except Exception as e:
            logger.error(f"Error fetching new coordinates: {e}")
            return None

# Initialize the file-based ship tracker
ship_tracker = ShipFileTracker(JSON_DIRECTORY)

def create_ship_embed(ship_data):
    """Create a Discord embed with ship information"""
    if not ship_data:
        embed = discord.Embed(
            title=f"❌ {FRIEND_NAME}'s Journey Update Unavailable",
            description="Unable to fetch current ship information. We'll try again soon!",
            color=0xff0000
        )
        return embed
    
    # Get a random farewell message
    farewell = random.choice(farewell_messages)
        
    # Create main embed with our friend's journey theme
    embed = discord.Embed(
        title=f"🚢 {ship_data.get('name', SHIP_NAME)} - {FRIEND_NAME}'s Voyage",
        description=f"{farewell}\nMMSI: {ship_data.get('mmsi', SHIP_MMSI)} | Status: {ship_data.get('status', 'Sailing')}",
        color=0x1e90ff,  # Ocean blue for sailing
        timestamp=datetime.utcnow()
    )
    
    # Position information
    if ship_data.get('latitude') is not None and ship_data.get('longitude') is not None:
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
            value=f"[See {FRIEND_NAME}'s Location]({maps_url})",
            inline=True
        )
    elif ship_data.get('coordinates'):
        # If we have coordinates in string format
        embed.add_field(
            name="📍 Current Position", 
            value=f"{ship_data['coordinates']}",
            inline=True
        )
        
        # Try to extract coordinates for the map link
        try:
            coords = ship_data['coordinates'].split(',')
            if len(coords) == 2:
                lat = float(coords[0].strip())
                lon = float(coords[1].strip())
                maps_url = f"https://maps.google.com/?q={lat},{lon}"
                embed.add_field(
                    name="🗺️ View Location",
                    value=f"[See {FRIEND_NAME}'s Location]({maps_url})",
                    inline=True
                )
        except:
            pass
    
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
        
    if ship_data.get('ship_type'):
        embed.add_field(
            name="🚢 Vessel Type", 
            value=ship_data['ship_type'],
            inline=True
        )
    
    # Add timestamp information
    if ship_data.get('timestamp') or ship_data.get('last_update'):
        timestamp = ship_data.get('timestamp') or ship_data.get('last_update')
        try:
            # Try to parse and format the timestamp
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                embed.add_field(
                    name="🕒 Last Updated", 
                    value=formatted_time,
                    inline=True
                )
        except:
            embed.add_field(
                name="🕒 Last Updated", 
                value=timestamp,
                inline=True
            )
    
    # Add file storage info
    all_files = ship_tracker.get_all_json_files(SHIP_MMSI)
    embed.add_field(
        name="📊 Data Storage",
        value=f"Storing {len(all_files)}/{MAX_JSON_FILES} journey logs",
        inline=True
    )
    
    # Next automatic update info
    if next_update:
        time_until = next_update - datetime.utcnow()
        if time_until.total_seconds() > 0:
            embed.add_field(
                name="⏱️ Next Update",
                value=f"In {time_until.days} days, {time_until.seconds // 3600} hours",
                inline=True
            )
    
    embed.set_footer(
        text=f"Tracking {FRIEND_NAME}'s journey across the seas. We miss you, friend! 🌊",
        icon_url="https://emojicdn.elk.sh/⚓"
    )
    
    return embed

# Function to clean up all screenshots from the screenshots directory
async def cleanup_all_screenshots():
    """Remove all screenshots from the screenshot directory"""
    try:
        screenshot_dir = Path(SCREENSHOT_DIR)
        if screenshot_dir.exists():
            for file in screenshot_dir.glob("*.png"):
                try:
                    file.unlink()
                    logger.info(f"Deleted screenshot: {file}")
                except Exception as e:
                    logger.warning(f"Failed to delete screenshot {file}: {e}")
            
            logger.info("Screenshot cleanup completed")
    except Exception as e:
        logger.error(f"Error during screenshot cleanup: {e}")

# Automatic update task that runs every 48 hours (2 days)
@tasks.loop(hours=UPDATE_INTERVAL_HOURS)
async def automatic_update():
    global last_update, cached_ship_data, next_update

    try:
        logger.info(f"Automatic update: Fetching fresh coordinates for {FRIEND_NAME}'s journey...")
        
        # Get the channel for posting updates
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            logger.error(f"Could not find channel with ID {DISCORD_CHANNEL_ID}")
            return
            
        # Send initial message
        status_message = await channel.send(f"🛰️ Automatic update: Establishing connection with {FRIEND_NAME}'s vessel...")
        
        # Get fresh coordinates using browser automation
        ship_data = await ship_tracker.fetch_new_coordinates(SHIP_MMSI)
        
        # Clean up screenshots after we're done
        await cleanup_all_screenshots()
        
        if ship_data and (ship_data.get('coordinates') or (ship_data.get('latitude') and ship_data.get('longitude'))):
            # Update was successful
            await status_message.edit(content=f"✅ Successfully updated {FRIEND_NAME}'s location!")
            
            # Update global variables
            cached_ship_data = ship_data
            last_update = datetime.utcnow()
            next_update = last_update + timedelta(hours=UPDATE_INTERVAL_HOURS)
            
            # Create and send the embed
            embed = create_ship_embed(ship_data)
            await channel.send(f"📡 Automatic update on {FRIEND_NAME}'s journey:", embed=embed)
            
            logger.info(f"Automatic update completed successfully. Next update in {UPDATE_INTERVAL_HOURS} hours.")
        else:
            # Update failed, try to use existing data
            await status_message.edit(content=f"⚠️ Could not get fresh coordinates for {FRIEND_NAME}'s vessel. Using last known data.")
            
            # Try to get existing data
            existing_data = await ship_tracker.fetch_ship_data(SHIP_MMSI)
            if existing_data:
                embed = create_ship_embed(existing_data)
                await channel.send(f"📡 Automatic update (using last known data):", embed=embed)
                
                # Still update the timestamps
                last_update = datetime.utcnow()
                next_update = last_update + timedelta(hours=UPDATE_INTERVAL_HOURS)
            else:
                await channel.send(f"❌ No data available for {FRIEND_NAME}'s vessel. Will try again in {UPDATE_INTERVAL_HOURS} hours.")
                
            logger.warning(f"Automatic update could not get fresh data. Next attempt in {UPDATE_INTERVAL_HOURS} hours.")
        
        # Cleanup old JSON files
        ship_tracker.cleanup_old_json_files(SHIP_MMSI, MAX_JSON_FILES)

    except Exception as e:
        logger.error(f"Error in automatic update: {e}")
        traceback.print_exc()
        
        # Try to notify in Discord
        try:
            channel = bot.get_channel(DISCORD_CHANNEL_ID)
            if channel:
                await channel.send(f"❌ Error during automatic update: {str(e)[:200]}... Will try again in {UPDATE_INTERVAL_HOURS} hours.")
        except:
            pass

# Cleanup task that runs daily to clean up files
@tasks.loop(hours=24)
async def daily_cleanup():
    try:
        logger.info("Running daily cleanup task...")
        
        # Clean up screenshots
        await cleanup_all_screenshots()
        
        # Clean up excess JSON files
        ship_tracker.cleanup_old_json_files(SHIP_MMSI, MAX_JSON_FILES)
        
        logger.info("Daily cleanup completed successfully")
    except Exception as e:
        logger.error(f"Error in daily cleanup task: {e}")

# Event hook when bot is ready
@bot.event
async def on_ready():
    logger.info(f"Bot connected as {bot.user}")
    
    # Clean up any leftover screenshots
    await cleanup_all_screenshots()
    
    # Clean up excess JSON files on startup
    ship_tracker.cleanup_old_json_files(SHIP_MMSI, MAX_JSON_FILES)
    
    # Start the automatic update task
    if not automatic_update.is_running():
        # Wait 10 seconds before first run to make sure everything is initialized
        await asyncio.sleep(10)
        automatic_update.start()
        logger.info(f"Automatic update task started. Will fetch new data every {UPDATE_INTERVAL_HOURS} hours.")
    
    # Start the daily cleanup task
    if not daily_cleanup.is_running():
        daily_cleanup.start()
        logger.info("Daily cleanup task started.")

# Only command to get the latest info about Kanakaris
@bot.command(name='kanakaris')
async def kanakaris_command(ctx):
    """Gets information about Kanakaris's journey"""
    await ctx.send(f"⚓ Looking for {FRIEND_NAME}'s vessel on the high seas...")
    
    # Get the latest data from existing JSON (we don't get new data on manual requests)
    ship_data = await ship_tracker.fetch_ship_data(SHIP_MMSI)
    
    if ship_data:
        # Create and send the embed with the latest saved data
        embed = create_ship_embed(ship_data)
        await ctx.send(f"📡 Update from {FRIEND_NAME}'s journey:", embed=embed)
    else:
        # If no data available, let the user know
        await ctx.send(f"❌ Unable to contact {FRIEND_NAME}'s vessel. The seas are vast, but we'll keep trying.")
        
        # Try to get fresh data since we don't have any saved data
        await ctx.send(f"Attempting to establish contact with {FRIEND_NAME}'s vessel. This may take a moment...")
        
        try:
            # Get fresh coordinates
            ship_data = await ship_tracker.fetch_new_coordinates(SHIP_MMSI)
            
            # Clean up screenshots after we're done
            await cleanup_all_screenshots()
            
            if ship_data and (ship_data.get('coordinates') or (ship_data.get('latitude') and ship_data.get('longitude'))):
                # Create and send the embed
                embed = create_ship_embed(ship_data)
                await ctx.send(f"📡 Successfully established contact with {FRIEND_NAME}'s vessel:", embed=embed)
                
                # Update global variables
                global last_update, next_update, cached_ship_data
                cached_ship_data = ship_data
                last_update = datetime.utcnow()
                next_update = last_update + timedelta(hours=UPDATE_INTERVAL_HOURS)
            else:
                await ctx.send(f"❌ Could not establish contact with {FRIEND_NAME}'s vessel. Will try again during the next scheduled update.")
        except Exception as e:
            logger.error(f"Error getting fresh coordinates: {e}")
            await ctx.send(f"❌ Error: Communications disrupted. {str(e)[:200]}")

# Run the bot
if __name__ == '__main__':
    try:
        # Print current date/time and user info
        print(f"Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): 2025-06-14 22:11:57")
        print(f"Current User's Login: npapoutsakis")
        print(f"Starting journey tracker for {FRIEND_NAME}'s vessel (MMSI: {SHIP_MMSI})")
        print(f"Automatic updates will occur every {UPDATE_INTERVAL_HOURS} hours (2 days)")
        print(f"Keeping only the {MAX_JSON_FILES} most recent JSON files")
        print(f"Daily cleanup process will run automatically")
        
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")