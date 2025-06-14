"""
    Professional Ship Tracking Data Extractor
    Automates data collection from myshiptracking.com with consent handling and OCR processing
"""

import time
import re
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ship_tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ShipData:
    """Data structure for ship information"""
    name: Optional[str] = None
    speed: Optional[str] = None
    course: Optional[str] = None
    status: Optional[str] = None
    coordinates: Optional[Tuple[float, float]] = None
    timestamp: Optional[str] = None
    mmsi: Optional[str] = None


class ShipTrackingExtractor:
    """Professional ship tracking data extractor with automated consent handling"""
    
    def __init__(self, headless: bool = False, screenshot_dir: str = "screenshots"):
        self.headless = headless
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(exist_ok=True)
        self.driver = None
        self.wait = None
        
    def setup_driver(self) -> None:
        """Initialize Chrome WebDriver with optimal settings"""
        try:
            chrome_options = Options()
            
            # Performance and stability options
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            # chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # User agent to appear more legitimate
            # chrome_options.add_argument(
            #     "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            #     "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            # )
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.wait = WebDriverWait(self.driver, 20)
            logger.info("WebDriver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise
    
    def debug_consent_elements(self) -> None:
        """Debug method to identify consent-related elements on the page"""
        try:
            logger.info("=== DEBUGGING CONSENT ELEMENTS ===")
            
            # Get page source for analysis
            page_source = self.driver.page_source.lower()
            
            # Check for consent-related keywords in page source
            consent_keywords = ['consent', 'cookie', 'privacy', 'gdpr', 'agree', 'accept', 'personal data']
            found_keywords = [keyword for keyword in consent_keywords if keyword in page_source]
            logger.info(f"Found consent keywords in page: {found_keywords}")
            
            # Find all button elements
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            logger.info(f"Found {len(buttons)} button elements")
            
            for i, button in enumerate(buttons[:20]):  # Limit to first 20 buttons
                try:
                    if button.is_displayed():
                        text = button.text.strip()
                        classes = button.get_attribute('class')
                        onclick = button.get_attribute('onclick')
                        button_id = button.get_attribute('id')
                        
                        logger.info(f"Button {i+1}: text='{text}', class='{classes}', id='{button_id}', onclick='{onclick}'")
                        
                        # Check if this might be a consent button
                        if any(keyword in text.lower() for keyword in ['agree', 'accept', 'ok', 'consent', 'continue']):
                            logger.info(f"  -> POTENTIAL CONSENT BUTTON!")
                except Exception as e:
                    logger.debug(f"Error analyzing button {i+1}: {e}")
            
            # Find all input elements
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"Found {len(inputs)} input elements")
            
            for i, inp in enumerate(inputs[:10]):  # Limit to first 10 inputs
                try:
                    if inp.is_displayed() and inp.get_attribute('type') in ['button', 'submit']:
                        value = inp.get_attribute('value')
                        classes = inp.get_attribute('class')
                        inp_id = inp.get_attribute('id')
                        
                        logger.info(f"Input {i+1}: value='{value}', class='{classes}', id='{inp_id}'")
                        
                        if value and any(keyword in value.lower() for keyword in ['agree', 'accept', 'ok', 'consent']):
                            logger.info(f"  -> POTENTIAL CONSENT INPUT!")
                except Exception as e:
                    logger.debug(f"Error analyzing input {i+1}: {e}")
            
            # Look for divs/spans with onclick or role=button
            clickable_divs = self.driver.find_elements(By.XPATH, "//div[@onclick or @role='button'] | //span[@onclick or @role='button']")
            logger.info(f"Found {len(clickable_divs)} clickable div/span elements")
            
            for i, div in enumerate(clickable_divs[:10]):
                try:
                    if div.is_displayed():
                        text = div.text.strip()
                        classes = div.get_attribute('class')
                        role = div.get_attribute('role')
                        
                        logger.info(f"Clickable div/span {i+1}: text='{text}', class='{classes}', role='{role}'")
                        
                        if any(keyword in text.lower() for keyword in ['agree', 'accept', 'ok', 'consent']):
                            logger.info(f"  -> POTENTIAL CONSENT DIV/SPAN!")
                except Exception as e:
                    logger.debug(f"Error analyzing clickable div/span {i+1}: {e}")
                    
            logger.info("=== END CONSENT DEBUGGING ===")
            
        except Exception as e:
            logger.error(f"Error in debug_consent_elements: {e}")

    def handle_consent_banner(self) -> bool:
        """Handle the consent banner with specific focus on fc-dialog-container"""
        try:
            logger.info("Waiting for fc-dialog-container consent popup...")
            
            # Wait for the page to load
            time.sleep(5)
            
            # Take a screenshot to see what's on the page
            self.take_screenshot("before_consent")
            
            # First, specifically target the fc-dialog-container
            try:
                logger.info("Looking for fc-dialog-container...")
                
                # Wait for the fc-dialog-container to appear
                dialog_container = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "fc-dialog-container"))
                )
                
                logger.info("Found fc-dialog-container!")
                
                # Look for buttons within the fc-dialog-container
                fc_consent_selectors = [
                    # Within fc-dialog-container, look for consent buttons
                    "//div[contains(@class, 'fc-dialog-container')]//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
                    "//div[contains(@class, 'fc-dialog-container')]//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
                    "//div[contains(@class, 'fc-dialog-container')]//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent')]",
                    "//div[contains(@class, 'fc-dialog-container')]//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'allow')]",
                    "//div[contains(@class, 'fc-dialog-container')]//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ok')]",
                    
                    # Look for specific fc-button classes
                    "//div[contains(@class, 'fc-dialog-container')]//button[contains(@class, 'fc-button')]",
                    "//div[contains(@class, 'fc-dialog-container')]//button[contains(@class, 'fc-cta-consent')]",
                    "//div[contains(@class, 'fc-dialog-container')]//button[contains(@class, 'fc-primary-button')]",
                    
                    # Look for any button in the dialog
                    "//div[contains(@class, 'fc-dialog-container')]//button",
                    
                    # Look for input buttons
                    "//div[contains(@class, 'fc-dialog-container')]//input[@type='button']",
                    "//div[contains(@class, 'fc-dialog-container')]//input[@type='submit']",
                    
                    # Look for clickable divs/spans within dialog
                    "//div[contains(@class, 'fc-dialog-container')]//*[@onclick or @role='button']"
                ]
                
                for i, selector in enumerate(fc_consent_selectors):
                    try:
                        logger.info(f"Trying fc-dialog selector {i+1}: {selector}")
                        
                        elements = self.driver.find_elements(By.XPATH, selector)
                        
                        for element in elements:
                            if element.is_displayed():
                                # Get element info for logging
                                text = element.text.strip()
                                classes = element.get_attribute('class')
                                tag_name = element.tag_name
                                
                                logger.info(f"Found clickable element: {tag_name}, text='{text}', class='{classes}'")
                                
                                # Scroll to element
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                                time.sleep(1)
                                
                                # Try different click methods
                                click_success = False
                                try:
                                    element.click()
                                    click_success = True
                                    logger.info("Clicked with regular click()")
                                except:
                                    try:
                                        self.driver.execute_script("arguments[0].click();", element)
                                        click_success = True
                                        logger.info("Clicked with JavaScript click()")
                                    except:
                                        try:
                                            ActionChains(self.driver).move_to_element(element).click().perform()
                                            click_success = True
                                            logger.info("Clicked with ActionChains")
                                        except:
                                            logger.warning("All click methods failed for this element")
                                
                                if click_success:
                                    logger.info("Successfully clicked consent button in fc-dialog-container!")
                                    time.sleep(3)
                                    self.take_screenshot("after_fc_consent")
                                    
                                    # Verify dialog is gone
                                    try:
                                        WebDriverWait(self.driver, 5).until(
                                            EC.invisibility_of_element_located((By.CLASS_NAME, "fc-dialog-container"))
                                        )
                                        logger.info("fc-dialog-container disappeared - consent handled successfully!")
                                        return True
                                    except:
                                        logger.info("Dialog still visible, but click was successful")
                                        return True
                                
                        if not elements:
                            logger.debug(f"No elements found for selector: {selector}")
                            
                    except Exception as e:
                        logger.debug(f"fc-dialog selector {i+1} failed: {e}")
                        continue
                
            except TimeoutException:
                logger.info("fc-dialog-container not found, trying fallback selectors...")
            
            # Fallback to general consent selectors
            general_consent_selectors = [
                # Text-based selectors (case insensitive)
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ok')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'allow')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent')]",
                
                # Input buttons
                "//input[@type='button' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
                "//input[@type='submit' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
                
                # Class-based selectors
                "//*[contains(@class, 'consent-agree')]",
                "//*[contains(@class, 'cookie-accept')]",
                "//*[contains(@class, 'gdpr-accept')]",
                "//*[contains(@class, 'privacy-accept')]"
            ]
            
            # Try general selectors as fallback
            for i, selector in enumerate(general_consent_selectors):
                try:
                    logger.info(f"Trying general selector {i+1}/{len(general_consent_selectors)}: {selector}")
                    
                    element = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    
                    # Scroll to element if needed
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(1)
                    
                    # Try multiple click methods
                    try:
                        element.click()
                        logger.info(f"General consent clicked successfully - selector: {selector}")
                    except:
                        try:
                            self.driver.execute_script("arguments[0].click();", element)
                            logger.info(f"General consent clicked with JS - selector: {selector}")
                        except:
                            ActionChains(self.driver).move_to_element(element).click().perform()
                            logger.info(f"General consent clicked with ActionChains - selector: {selector}")
                    
                    time.sleep(3)
                    self.take_screenshot("after_general_consent")
                    return True
                    
                except TimeoutException:
                    continue
                except Exception as e:
                    logger.debug(f"General selector {i+1} failed: {e}")
                    continue
            
            # Final fallback: look for any clickable element with consent-related text
            try:
                logger.info("Trying fallback approach - searching for any consent-related clickable elements")
                
                # Get all potentially clickable elements
                clickable_elements = self.driver.find_elements(By.XPATH, 
                    "//button | //input[@type='button'] | //input[@type='submit'] | "
                    "//*[@onclick] | //*[@role='button'] | //a[contains(@href, '#')]"
                )
                
                for element in clickable_elements:
                    try:
                        if element.is_displayed():
                            text = element.text.lower()
                            value = element.get_attribute('value')
                            if value:
                                text += " " + value.lower()
                            
                            # Check if element contains consent-related keywords
                            consent_keywords = ['agree', 'accept', 'consent', 'ok', 'allow', 'continue']
                            if any(keyword in text for keyword in consent_keywords):
                                logger.info(f"Found potential consent element with text: '{text}'")
                                
                                # Try to click it
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                                time.sleep(1)
                                self.driver.execute_script("arguments[0].click();", element)
                                logger.info("Consent handled with fallback approach")
                                time.sleep(3)
                                self.take_screenshot("after_consent_fallback")
                                return True
                    except:
                        continue
                        
            except Exception as e:
                logger.error(f"Fallback approach failed: {e}")
            
            # Ultimate fallback: check if consent banner is blocking and try to dismiss
            try:
                # Look for overlay or modal elements
                overlays = self.driver.find_elements(By.XPATH, 
                    "//*[contains(@class, 'overlay') or contains(@class, 'modal') or "
                    "contains(@class, 'popup') or contains(@class, 'dialog')]"
                )
                
                for overlay in overlays:
                    if overlay.is_displayed():
                        # Try to find close button or click outside
                        close_buttons = overlay.find_elements(By.XPATH, 
                            ".//button | .//input[@type='button'] | .//*[@role='button']"
                        )
                        if close_buttons:
                            for btn in close_buttons:
                                try:
                                    btn.click()
                                    logger.info("Dismissed overlay/modal")
                                    time.sleep(2)
                                    return True
                                except:
                                    continue
            except:
                pass
            
            logger.warning("Could not find or handle consent banner")
            self.take_screenshot("consent_not_found")
            return False
            
        except Exception as e:
            logger.error(f"Error handling consent banner: {e}")
            self.take_screenshot("consent_error")
            return False
    
    def take_screenshot(self, filename: str) -> str:
        """Take a screenshot and save it"""
        try:
            filepath = self.screenshot_dir / f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            self.driver.save_screenshot(str(filepath))
            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            raise
    
    def extract_text_from_image(self, image_path: str) -> str:
        """Extract text from image using OCR with preprocessing"""
        try:
            # Read image
            image = cv2.imread(image_path)
            
            # Preprocessing for better OCR
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Noise removal
            denoised = cv2.medianBlur(gray, 3)
            
            # Thresholding
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # OCR configuration
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,°:- '
            
            text = pytesseract.image_to_string(thresh, config=custom_config)
            logger.info("OCR text extraction completed")
            return text
            
        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return ""
    
    def parse_ship_data(self, ocr_text: str, mmsi: str) -> ShipData:
        """Parse ship data from OCR text using regex patterns"""
        ship_data = ShipData(mmsi=mmsi, timestamp=datetime.now().isoformat())
        
        try:
            # Patterns for different data fields
            patterns = {
                'name': [
                    r'Name[:\s]+([A-Z\s]+)',
                    r'Vessel[:\s]+([A-Z\s]+)',
                    r'Ship[:\s]+([A-Z\s]+)'
                ],
                'speed': [
                    r'Speed[:\s]+([\d.]+)\s*(?:kn|knots?)',
                    r'SOG[:\s]+([\d.]+)',
                    r'Speed\s*(?:over\s*ground)?[:\s]+([\d.]+)'
                ],
                'course': [
                    r'Course[:\s]+([\d.]+)\s*(?:°|deg)',
                    r'COG[:\s]+([\d.]+)',
                    r'Heading[:\s]+([\d.]+)'
                ],
                'status': [
                    r'Status[:\s]+([A-Za-z\s]+)',
                    r'Navigation[:\s]+Status[:\s]+([A-Za-z\s]+)',
                    r'Condition[:\s]+([A-Za-z\s]+)'
                ]
            }
            
            for field, field_patterns in patterns.items():
                for pattern in field_patterns:
                    match = re.search(pattern, ocr_text, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip()
                        setattr(ship_data, field, value)
                        logger.info(f"Extracted {field}: {value}")
                        break
            
        except Exception as e:
            logger.error(f"Error parsing ship data: {e}")
        
        return ship_data
    
    def get_ship_coordinates(self) -> Optional[Tuple[float, float]]:
        """Extract coordinates by right-clicking on the ship twice"""
        try:
            logger.info("Attempting to extract coordinates...")
            
            # Look for ship icon or marker on the map
            ship_selectors = [
                "//div[contains(@class, 'ship')]",
                "//div[contains(@class, 'vessel')]",
                "//div[contains(@class, 'marker')]",
                "//*[contains(@title, 'MMSI')]"
            ]
            
            ship_element = None
            for selector in ship_selectors:
                try:
                    ship_element = self.driver.find_element(By.XPATH, selector)
                    if ship_element.is_displayed():
                        break
                except NoSuchElementException:
                    continue
            
            if not ship_element:
                logger.warning("Could not find ship element on map")
                return None
            
            # Perform double right-click
            actions = ActionChains(self.driver)
            actions.context_click(ship_element).perform()
            time.sleep(1)
            actions.context_click(ship_element).perform()
            time.sleep(2)
            
            # Try to extract coordinates from context menu or popup
            coord_patterns = [
                r'(\d+\.?\d*)[°\s]*[NS][,\s]+(\d+\.?\d*)[°\s]*[EW]',
                r'Lat[:\s]+(-?\d+\.?\d*)[,\s]+Lon[:\s]+(-?\d+\.?\d*)',
                r'Position[:\s]+(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)'
            ]
            
            page_source = self.driver.page_source
            for pattern in coord_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    lat, lon = float(match.group(1)), float(match.group(2))
                    logger.info(f"Extracted coordinates: {lat}, {lon}")
                    return (lat, lon)
            
            # Take screenshot after right-click for manual inspection
            self.take_screenshot("after_rightclick")
            
        except Exception as e:
            logger.error(f"Error extracting coordinates: {e}")
        
        return None
    
    def extract_ship_data(self, mmsi: str) -> ShipData:
        """Main method to extract all ship data"""
        url = f"https://www.myshiptracking.com/?mmsi={mmsi}"
        
        try:
            logger.info(f"Starting data extraction for MMSI: {mmsi}")
            self.setup_driver()
            
            # Navigate to URL
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)
            time.sleep(5)
            
            # Handle consent banner
            consent_handled = self.handle_consent_banner()
            if not consent_handled:
                logger.warning("Consent banner not handled - running debug analysis")
                self.debug_consent_elements()
                # Try one more time after debugging
                time.sleep(2)
                self.handle_consent_banner()
            
            time.sleep(3)
            
            # Take initial screenshot
            initial_screenshot = self.take_screenshot("initial_page")
            
            # Extract text using OCR
            ocr_text = self.extract_text_from_image(initial_screenshot)
            
            # Parse ship data
            ship_data = self.parse_ship_data(ocr_text, mmsi)
            
            # Extract coordinates
            coordinates = self.get_ship_coordinates()
            ship_data.coordinates = coordinates
            
            # Take final screenshot
            self.take_screenshot("final_page")
            
            logger.info("Data extraction completed successfully")
            return ship_data
            
        except Exception as e:
            logger.error(f"Error during data extraction: {e}")
            raise
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver closed")
    
    def save_data(self, ship_data: ShipData, filename: str = None) -> None:
        """Save extracted data to JSON file"""
        import json
        
        if not filename:
            filename = f"ship_data_{ship_data.mmsi}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data_dict = {
            'mmsi': ship_data.mmsi,
            'name': ship_data.name,
            'speed': ship_data.speed,
            'course': ship_data.course,
            'status': ship_data.status,
            'coordinates': ship_data.coordinates,
            'timestamp': ship_data.timestamp
        }
        
        with open(filename, 'w') as f:
            json.dump(data_dict, f, indent=2)
        
        logger.info(f"Data saved to: {filename}")


def main():
    """Example usage"""
    extractor = ShipTrackingExtractor(headless=False)  # Set to True for headless mode
    
    try:
        # Extract data for the specified MMSI
        mmsi = "538010457"
        ship_data = extractor.extract_ship_data(mmsi)
        
        # Display results
        print(f"\n=== Ship Data for MMSI: {mmsi} ===")
        print(f"Name: {ship_data.name}")
        print(f"Speed: {ship_data.speed}")
        print(f"Course: {ship_data.course}")
        print(f"Status: {ship_data.status}")
        print(f"Coordinates: {ship_data.coordinates}")
        print(f"Timestamp: {ship_data.timestamp}")
        
        # Save data
        extractor.save_data(ship_data)
        
    except Exception as e:
        logger.error(f"Application error: {e}")


if __name__ == "__main__":
    main()