from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
from dotenv import load_dotenv

load_dotenv()

CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH")
DISCORD_CHANNEL_URL = os.getenv("DISCORD_CHANNEL_URL")

def setup_discord_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-usb-discovery")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--log-level=3")  
    chrome_options.add_argument("--disable-logging")
    
    service = Service(executable_path=CHROMEDRIVER_PATH)
    return webdriver.Chrome(service=service, options=chrome_options)

def login_to_discord(driver):
    try:
        print("Opening Discord login page...")
        driver.get("https://discord.com/login")
        time.sleep(2)
        
        email = os.getenv("DISCORD_EMAIL")
        password = os.getenv("DISCORD_PASSWORD")
        
        if not email or not password:
            print("Error: Discord credentials not found in .env file")
            return False
            
        print("Autofilling email...")
        email_field = driver.find_element(By.NAME, "email")
        email_field.send_keys(email)
        time.sleep(1)
        
        print("Autofilling password...")
        password_field = driver.find_element(By.NAME, "password")
        password_field.send_keys(password)
        
        print("\nCredentials autofilled. Please complete the login process manually and press Enter when ready...")
        input()
        
        print("\nNavigating to Discord channel...")
        driver.get(DISCORD_CHANNEL_URL)
        time.sleep(3)

        print("Successfully navigated to channel")
        return True

    except Exception as e:
        print(f"Error in Discord login process: {str(e)}")
        return False

def get_latest_messages(driver, last_timestamp):
    try:
        # Get all messages
        messages = driver.find_elements(By.CSS_SELECTOR, "li[id^='chat-messages-']")
        if not messages:
            return []
            
        # Process all messages and return new ones
        new_messages = []
        for message in messages:
            try:
                # Get timestamp for comparison
                timestamp = message.find_element(
                    By.CSS_SELECTOR, 
                    "time[id^='message-timestamp-']"
                ).get_attribute('datetime')
                
                if last_timestamp and timestamp <= last_timestamp:
                    continue
                
                username_element = message.find_element(
                    By.CSS_SELECTOR, 
                    "span.username_f9f2ca"
                )
                
                if username_element.text == "Hulinuli":
                    message_content_div = message.find_element(
                        By.CSS_SELECTOR,
                        "div[class*='messageContent']"
                    )
                    spans = message_content_div.find_elements(By.CSS_SELECTOR, "span")
                    
                    full_message = ''.join(span.text for span in spans)
                    new_messages.append((full_message, timestamp))
                    
            except Exception as e:
                continue
        
        return new_messages

    except Exception as e:
        print(f"Error getting messages: {str(e)}")
        return []

def test_discord_login():
    print("\n=== Starting Discord Monitor Test ===")
    
    if not all([CHROMEDRIVER_PATH, DISCORD_CHANNEL_URL]):
        print("\nError: Missing environment variables!")
        print("Please ensure these variables are set in your .env file:")
        print("- CHROMEDRIVER_PATH")
        print("- DISCORD_CHANNEL_URL")
        return
    
    try:
        print("\nSetting up Chrome driver...")
        discord_driver = setup_discord_driver()
        
        if login_to_discord(discord_driver):
            print("\nChecking latest message...")
            initial_messages = get_latest_messages(discord_driver, None)
            last_timestamp = initial_messages[-1][1] if initial_messages else None
            
            if initial_messages:
                print(f"Latest message from Hulinuli: {initial_messages[-1][0]}")
            else:
                print("No recent messages from Hulinuli found")
            
            print("\nStarting continuous monitoring...")
            print("Monitoring channel for new messages from Hulinuli (Press Ctrl+C to stop)")
            
            while True:
                try:
                    new_messages = get_latest_messages(discord_driver, last_timestamp)
                    for message, timestamp in new_messages:
                        print(f"\nNew message from Hulinuli: {message}")
                        last_timestamp = timestamp
                    
                    time.sleep(1)  
                    
                except KeyboardInterrupt:
                    print("\n\nMonitoring interrupted by user.")
                    break
            
            print("\nTest completed successfully!")
            
        else:
            print("\nFailed to complete Discord process!")
            
    except Exception as e:
        print(f"\nError during test: {str(e)}")
        
    finally:
        print("\nCleaning up...")
        if 'discord_driver' in locals():
            discord_driver.quit()
        print("=== Test Complete ===")

if __name__ == "__main__":
    test_discord_login()
