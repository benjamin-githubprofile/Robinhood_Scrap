import os
import time
import logging
import requests
from decimal import Decimal
from dotenv import load_dotenv
from selenium import webdriver
import re
import datetime
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ----------------------------
# Configuration and Setup
# ----------------------------

# Initialize logging
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stock_bot.log"),
        logging.StreamHandler()
    ]
)

# Load environment variables from .env file
load_dotenv()

# Configuration Variables
ROBINHOOD_USERNAME = os.getenv("ROBINHOOD_USERNAME")
ROBINHOOD_PASSWORD = os.getenv("ROBINHOOD_PASSWORD")
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Validate Environment Variables
if not all([ROBINHOOD_USERNAME, ROBINHOOD_PASSWORD, CHROMEDRIVER_PATH, DISCORD_WEBHOOK_URL]):
    logging.error("Please set all required environment variables in the .env file.")
    raise EnvironmentError("Missing required environment variables.")

# ----------------------------
# Selenium WebDriver Setup
# ----------------------------

def setup_webdriver():
    """Set up the Selenium WebDriver with desired options."""
    chrome_options = Options()
    #chrome_options.add_argument("--headless")  # Run Chrome in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        service = Service(executable_path=CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.info("Selenium WebDriver initialized successfully.")
        return driver
    except Exception as e:
        logging.error(f"Failed to initialize Selenium WebDriver: {e}")
        raise e

# ----------------------------
# Robinhood Login and Navigation
# ----------------------------

def login_to_robinhood(driver):
    """Automate the login process to Robinhood."""
    try:
        driver.get("https://robinhood.com/login/")
        logging.info("Navigated to Robinhood login page.")
        time.sleep(3)  # Wait for the page to load

        # Enter username
        username_field = driver.find_element(By.NAME, "username")
        username_field.send_keys(ROBINHOOD_USERNAME)
        logging.debug("Entered username.")
        
        # Enter password
        password_field = driver.find_element(By.NAME, "password")
        password_field.send_keys(ROBINHOOD_PASSWORD)
        logging.debug("Entered password.")
        
        # Click "Remember me" checkbox
        try:
            remember_me = driver.find_element(By.XPATH, "//span[contains(text(), 'Keep me logged in for up to 30 days')]")
            remember_me.click()
            logging.debug("Clicked 'Remember me' checkbox.")
            time.sleep(1)  # Short wait after clicking
        except Exception as e:
            logging.debug(f"Could not find or click 'Remember me' checkbox: {e}")
        
        # Submit login form
        password_field.send_keys(Keys.RETURN)
        logging.info("Submitted login form.")
        time.sleep(5)  # Wait for potential MFA prompt or dashboard to load

        # Handle MFA with fixed wait time
        print("\nPlease complete the verification process in the browser.")
        print("You have 20 seconds to complete the verification...\n")
        time.sleep(20)  # Fixed wait time for MFA completion
        logging.info("Proceeding after 20 second wait...")

        # Navigate to investing page
        try:
            logging.info("Navigating to investing page...")
            driver.get("https://robinhood.com/account/investing")
            time.sleep(5)  # Wait for investing page to load
            return True
            
        except Exception as nav_error:
            logging.error(f"Error navigating to investing page: {nav_error}")
            return False

    except Exception as e:
        logging.error(f"An error occurred during login: {e}")
        return False

# ----------------------------
# Scraping Portfolio Data
# ----------------------------

def scrape_portfolio(driver):
    """Scrape portfolio data from Robinhood."""
    try:
        # Navigate to the portfolio page
        driver.get("https://robinhood.com/account/investing")
        logging.info("Navigated to Robinhood portfolio page.")
        time.sleep(15)  # Wait for page load
        
        # Get account data from preloaded JavaScript
        try:
            account_data = driver.execute_script("return window.preloadedUserData.brokebackAccounts.data.results[0];")
            if account_data:
                logging.info("Found account data")
                
                # Extract portfolio value
                total_value = Decimal(str(account_data.get('portfolio_cash', '0.0')))
                logging.info(f"Portfolio value: ${total_value}")
                
                # Get positions data
                positions_url = "https://api.robinhood.com/positions/?nonzero=true"
                driver.get(positions_url)
                positions_data = driver.execute_script("return JSON.parse(document.body.innerText);")
                
                holdings = []
                if positions_data and 'results' in positions_data:
                    for position in positions_data['results']:
                        try:
                            quantity = Decimal(str(position.get('quantity', '0')))
                            if quantity > 0:
                                # Get instrument data
                                instrument_url = position.get('instrument')
                                driver.get(instrument_url)
                                instrument_data = driver.execute_script("return JSON.parse(document.body.innerText);")
                                
                                ticker = instrument_data.get('symbol')
                                avg_price = Decimal(str(position.get('average_buy_price', '0.0')))
                                position_value = quantity * avg_price
                                
                                holdings.append({
                                    "Ticker": ticker,
                                    "Shares": quantity,
                                    "Average Price": f"${avg_price:.2f}",
                                    "Position Value": position_value
                                })
                                logging.info(f"Found holding: {ticker} - {quantity} shares at ${avg_price}")
                        except Exception as position_error:
                            logging.error(f"Error processing position: {position_error}")
                            continue
                
                # Calculate percentages
                if holdings:
                    for holding in holdings:
                        holding['Portfolio Percentage'] = (holding['Position Value'] / total_value * 100).quantize(Decimal('0.01'))
                    
                    logging.info(f"Successfully scraped {len(holdings)} holdings")
                    return holdings, total_value
                else:
                    logging.info("No holdings found in portfolio")
                    return [], total_value
                    
        except Exception as js_error:
            logging.error(f"Error extracting data from JavaScript: {js_error}")
            return None, None

    except Exception as e:
        logging.error(f"An error occurred while scraping portfolio: {e}")
        return None, None

# ----------------------------
# Discord Notification Function
# ----------------------------

def send_portfolio_to_discord(holdings, total_value):
    """Send the portfolio breakdown to Discord via webhook."""
    if not DISCORD_WEBHOOK_URL:
        logging.error("Discord webhook URL is not set.")
        return

    # Create Discord embed
    embed = {
        "title": "📊 Portfolio Breakdown",
        "color": 0x00ff00,  # Green color
        "fields": [
            {"name": "Total Portfolio Value", "value": f"${total_value:.2f}", "inline": False}
        ],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    # Add each holding to the embed
    for holding in holdings:
        field_value = (
            f"**Company:** {holding['Company']}\n"
            f"**Shares:** {holding['Shares']}\n"
            f"**Average Price:** {holding['Average Price']}\n"
            f"**Position Value:** ${holding['Position Value']:.2f}\n"
            f"**Portfolio %:** {holding['Portfolio Percentage']}%"
        )
        embed["fields"].append({
            "name": f"{holding['Ticker']}",
            "value": field_value,
            "inline": True
        })

    data = {
        "content": "Here is your current portfolio breakdown:",
        "embeds": [embed]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        if response.status_code == 204:
            logging.info("Portfolio details sent to Discord successfully.")
        else:
            logging.error(f"Failed to send message to Discord. Status Code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        logging.error(f"An error occurred while sending to Discord: {e}")

# ----------------------------
# Main Function
# ----------------------------

def main():
    """Main function to execute the portfolio retrieval and notification."""
    driver = setup_webdriver()
    
    try:
        # Log into Robinhood
        if not login_to_robinhood(driver):
            logging.error("Exiting due to login failure.")
            return

        # Scrape portfolio data
        holdings, total_value = scrape_portfolio(driver)
        if not holdings:
            logging.error("No holdings found. Exiting.")
            return

        # Send portfolio data to Discord
        send_portfolio_to_discord(holdings, total_value)

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

    finally:
        driver.quit()
        logging.info("Selenium WebDriver closed.")

# ----------------------------
# Entry Point
# ----------------------------

if __name__ == "__main__":
    main()
