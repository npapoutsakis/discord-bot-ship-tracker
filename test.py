import time
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ShipData:
    """Data structure for ship information"""
    name: Optional[str] = None
    speed: Optional[str] = None
    course: Optional[str] = None
    status: Optional[str] = None
    ship_type: Optional[str] = None
    coordinates: Optional[Tuple[float, float]] = None
    timestamp: Optional[str] = None
    mmsi: Optional[str] = None

class MinimalShipTracker:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None

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

    
    def get_coordinates(self) -> Optional[Tuple[float, float]]:
        """Extract coordinates by double right-clicking and selecting the exact 'Get Coordinates' menu item"""
        try:
            logger.info("Attempting to get coordinates...")
            
            # First take a screenshot of the initial state
            self.driver.save_screenshot("initial_state.png")
            logger.info("Saved initial state screenshot")
            
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
            # time.sleep(2)
            
            # Take screenshot after first right-click
            self.driver.save_screenshot("after_first_right_click.png")
            logger.info("Saved after first right-click screenshot")
            
            # Second right-click
            logger.info("*** PERFORMING SECOND RIGHT-CLICK ***")
            actions = ActionChains(self.driver)
            actions.context_click().perform()
            # time.sleep(2)
            
            # Take screenshot after second right-click
            self.driver.save_screenshot("after_second_right_click.png")
            logger.info("Saved after second right-click screenshot")
            
            # Look specifically for the exact "Get Coordinates" element you provided
            # This is now the EXACT selector for the element you showed
            exact_selectors = [
                "//a[contains(@class, 'dropdown-item') and contains(@onclick, 'mySTmap_command.getCoordinates') and contains(text(), 'Get Coordinates')]",
                "//a[contains(@onclick, 'mySTmap_command.getCoordinates')]",
                "//a[contains(@class, 'dropdown-item') and contains(text(), 'Get Coordinates')]",
                # Fallback to more generic selectors
                "//a[contains(text(), 'Get Coordinates')]",
                "//a[contains(@class, 'dropdown-item')]"
            ]
            
            # Take screenshot of the context menu
            self.driver.save_screenshot("context_menu.png")
            logger.info("Saved context menu screenshot")
            
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
                            time.sleep(1)
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
            self.driver.save_screenshot("after_menu_interaction.png")
            logger.info("Saved after menu interaction screenshot")
            
            # Try to extract coordinates from Swal2 alert
            coordinates = None
            try:
                swal_title = self.driver.find_element(By.ID, "swal2-title")
                if swal_title.is_displayed() and "Coordinates" in swal_title.text:
                    logger.info("Found Swal2 alert with coordinates")
                    
                    # Take screenshot of coordinates dialog
                    self.driver.save_screenshot("coordinates_dialog.png")
                    logger.info("Saved coordinates dialog screenshot")
                    
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
                        logger.info(f"Extracted coordinates: {coordinates}")
                        
                        # Take final screenshot with coordinates
                        self.driver.save_screenshot("extracted_coordinates.png")
                        logger.info("Saved final screenshot with coordinates")
                        
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
            ship_data.coordinates = coordinates
            
            return ship_data
            
        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            return ship_data
        finally:
            if self.driver:
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
        
        logger.info(f"Data saved to: {filename}")


def main(mmsi):
    """Minimal example usage"""
    tracker = MinimalShipTracker(headless=True)
    
    # Extract data
    ship_data = tracker.extract_ship_data(mmsi)
    
    # Display results
    print(f"\n=== Ship Data for MMSI: {mmsi} ===")
    print(f"Name: {ship_data.name}")
    print(f"Type: {ship_data.ship_type}")
    print(f"Speed: {ship_data.speed}")
    print(f"Course: {ship_data.course}")
    print(f"Status: {ship_data.status}")
    print(f"Coordinates: {ship_data.coordinates}")
    print(f"Timestamp: {ship_data.timestamp}")
    
    # Save data
    tracker.save_data(ship_data)


if __name__ == "__main__":
    main(mmsi = "538010457")