import yfinance as yf

# Fetch XAUUSD data - last 5 days, 1 hour candles
gold = yf.download("GC=F", period="5d", interval="1h")

# Print the last 10 candles
print("=== XAUUSD - Last 10 candles ===")
print(gold.tail(10))
