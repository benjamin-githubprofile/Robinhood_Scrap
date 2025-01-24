import requests
from bs4 import BeautifulSoup
import time

def get_stock_price(html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        price_element = soup.find(id='sdp-market-price-tooltip')
        
        if not price_element:
            print("No price element found with ID 'sdp-market-price-tooltip'")
            return None
            
        price_text = price_element.text.strip()
        if not price_text:
            print("Empty price text found")
            return None
            
        price_text = price_text.replace('$', '').replace(',', '')
            
        try:
            return float(price_text)
        except ValueError:
            print(f"Could not convert price text to number: {price_text}")
            return None
        
    except Exception as e:
        print(f"Error parsing price: {str(e)}")
        return None

def monitor_stock(ticker, interval=60):
    while True:
        price = get_stock_price(ticker)
        if price:
            print(f"{ticker}: ${price:.2f} at {time.strftime('%H:%M:%S')}")
        time.sleep(interval)

if __name__ == "__main__":
    try:
        print("Starting price check...")
        with open('AMD - $122.90 _ Robinhood.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            price_element = soup.find(id='sdp-market-price-tooltip')
            if price_element:
                print("\nFound price element:")
                print(price_element.prettify())
            
            price = get_stock_price(html_content)
            if price:
                print(f"\nParsed stock price: ${price:.2f}")
            else:
                print("\nFailed to parse stock price")
    except FileNotFoundError:
        print("HTML file not found. Please ensure 'AMD - $122.90 _ Robinhood.html' exists in the current directory.")
    except Exception as e:
        print(f"Error reading file: {str(e)}")