from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import logging
import time
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
from tools.stock_price_checker import get_stock_price

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

load_dotenv()

CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH")
ROBINHOOD_USERNAME = os.getenv("ROBINHOOD_USERNAME")
ROBINHOOD_PASSWORD = os.getenv("ROBINHOOD_PASSWORD")

def setup_webdriver():
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

def fetch_industry_data(symbols):
    industry_data = {}
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            industry_data[symbol] = {
                "Sector": info.get("sector", "Unknown"),
                "Industry": info.get("industry", "Unknown"),
            }
        except Exception as e:
            logging.error(f"Error fetching data for {symbol}: {e}")
            industry_data[symbol] = {"Sector": "Unknown", "Industry": "Unknown"}
    return industry_data

def parse_and_analyze_stocks(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    stock_rows = soup.find_all("a", class_="css-1byi2su", href=lambda x: x and "/stocks/" in x)

    stock_data = []
    symbols = []
    print(f"Found {len(stock_rows)} potential stock rows.")  

    for row in stock_rows:
        try:
            name = row.find("span", class_="_2jKxrvkjD73sLQEfH5NTgT")
            symbol = row.find("span", class_="_2-4BkMtIykh6hAhu1CkOAi")
            shares = row.find_all("div", class_="_1bZB-iudENk38jTXhs7BIB")[2]
            price = row.find("span", class_="_1aY3uEJAcFViGgVc3SRz4d")
            avg_cost = row.find_all("span", class_="_2gJfY0FDaI4PWOsRbu1PPj")[0]
            total_return = row.find("div", class_="Ue-PUFBPXUbpP5zhTrFKT web-app-emotion-cache-q82x4k").find_all("span")[-1]
            equity = row.find("span", class_="atrP1y1y_C9ULHV4BSwFj")

            def clean_float(value):
                return float(value.replace(",", "").replace("$", "")) if value else 0.0

            symbols.append(symbol.text if symbol else "Unknown")

            stock_data.append({
                "Name": name.text if name else "Unknown",
                "Symbol": symbol.text if symbol else "Unknown",
                "Shares": float(shares.text.replace(",", "")) if shares and shares.text else 0.0,
                "Price": clean_float(price.text) if price else 0.0,
                "Average Cost": clean_float(avg_cost.text) if avg_cost else 0.0,
                "Total Return": clean_float(total_return.text) if total_return else 0.0,
                "Equity": clean_float(equity.text) if equity else 0.0,
            })
        except Exception as e:
            logging.error(f"Error parsing row: {e}")
            continue

    df = pd.DataFrame(stock_data)

    if df.empty:
        print("No stock data was parsed. Verify the HTML structure and class names.")
        return

    print("\nOriginal Stock Data:")
    print(df)

    industry_data = fetch_industry_data(symbols)

    def map_to_broad_sector(industry):
        sector_mapping = {
            "Banks - Diversified": "Financial Services",
            "Drug Manufacturers - General": "Healthcare",
            "Internet Retail": "Consumer Cyclical",
            "Semiconductors": "Technology",
            "Software - Infrastructure": "Technology",
            "Fund": "Fund",
        }
        return sector_mapping.get(industry, "Fund")

    df["Sector"] = df["Symbol"].apply(lambda x: industry_data.get(x, {}).get("Sector", "Fund"))
    df["Industry"] = df["Symbol"].apply(lambda x: industry_data.get(x, {}).get("Industry", "Fund"))

    df["Broad Sector"] = df["Industry"].apply(map_to_broad_sector)

    cash = float(input("\nEnter total cash available for investment（2 decimals）: "))
    cash_row = {
        "Symbol": "CASH",
        "Sector": "Cash",
        "Industry": "Cash",
        "Broad Sector": "Cash",
        "Shares": 0.0,
        "Price": 1.0, 
        "Average Cost": 1.0,
        "Total Return": 0.0,
        "Equity": cash,
    }

    df = pd.concat([df, pd.DataFrame([cash_row])], ignore_index=True)

    total_equity = df["Equity"].sum()
    df["Equity %"] = (df["Equity"] / total_equity * 100).round(2)

    print("\nCurrent Portfolio Distribution:")
    print(df[["Symbol", "Sector", "Industry", "Equity", "Equity %"]])

    sector_allocation = df.groupby("Broad Sector")["Equity"].sum().reset_index()
    sector_allocation["Equity %"] = (sector_allocation["Equity"] / total_equity * 100).round(2)

    target_allocation = {
        "Financial Services": 20,
        "Healthcare": 15,
        "Consumer Cyclical": 15,
        "Technology": 25,
        "Fund": 25,
    }

    sector_allocation["Target %"] = sector_allocation["Broad Sector"].map(target_allocation)
    sector_allocation["Rebalance %"] = (
        sector_allocation["Target %"] - sector_allocation["Equity %"]
    ).round(2)

    print("\nRebalancing Suggestions (Broad Sector):")
    print(sector_allocation[["Broad Sector", "Equity %", "Target %", "Rebalance %"]])

    return df

def get_stock_price_from_driver(driver, ticker):
    try:
        driver.get(f"https://robinhood.com/stocks/{ticker.upper()}")
        time.sleep(2)
        html_content = driver.page_source
        return get_stock_price(html_content)
    except Exception as e:
        print(f"Error fetching price for {ticker}: {str(e)}")
        return None

def interactive_price_check(driver):
    while True:
        print("\nOptions:")
        print("1. Enter a ticker symbol to check its real-time price")
        print("2. Type 'Exit' to quit")
        
        user_input = input("\nWhat would you like to do? ").strip().upper()
        
        if user_input == 'EXIT':
            print("Shutting down...")
            driver.quit()
            break
        
        if user_input:
            price = get_stock_price_from_driver(driver, user_input)
            if price:
                print(f"\nCurrent {user_input} price: ${price:.2f}")
            else:
                print(f"Could not fetch price for {user_input}")


def login_and_get_html():
    driver = setup_webdriver()
    try:
        driver.get("https://robinhood.com/login/")
        time.sleep(3)

        driver.find_element("name", "username").send_keys(ROBINHOOD_USERNAME)
        driver.find_element("name", "password").send_keys(ROBINHOOD_PASSWORD)
        driver.find_element("name", "password").send_keys("\n") 
        input("Press Enter once you have completed login and any necessary MFA...") 

        driver.get("https://robinhood.com/account/investing")
        time.sleep(5) 
        investing_html = driver.page_source
        
        return investing_html, amd_html, driver  
    except Exception as e:
        driver.quit()
        raise e

if __name__ == "__main__":
    if not all([CHROMEDRIVER_PATH, ROBINHOOD_USERNAME, ROBINHOOD_PASSWORD]):
        logging.error("Ensure all required environment variables are set.")
    else:
        try:
            investing_html, amd_html, driver = login_and_get_html()
            parse_and_analyze_stocks(investing_html)
            interactive_price_check(driver)
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            if 'driver' in locals():
                driver.quit() 