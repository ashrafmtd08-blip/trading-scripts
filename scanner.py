import yfinance as yf

# Fetch XAUUSD - last 5 days, 1 hour candles
gold = yf.download("GC=F", period="5d", interval="1h", auto_adjust=True)
df = gold.copy()

# Flatten column names
df.columns = [col[0] for col in df.columns]

print("=== XAUUSD FVG Scanner ===")
print(f"Total candles loaded: {len(df)}")
print("")

# FVG Detection
# Bullish FVG: candle[i-1] high is below candle[i+1] low — gap left unfilled
# Bearish FVG: candle[i-1] low is above candle[i+1] high — gap left unfilled

fvgs = []

for i in range(1, len(df) - 1):
    prev  = df.iloc[i - 1]
    curr  = df.iloc[i]
    nxt   = df.iloc[i + 1]
    time  = df.index[i]

    # Bullish FVG
    if prev["High"] < nxt["Low"]:
        fvgs.append({
            "time"  : time,
            "type"  : "Bullish FVG",
            "top"   : round(nxt["Low"], 2),
            "bottom": round(prev["High"], 2),
            "size"  : round(nxt["Low"] - prev["High"], 2)
        })

    # Bearish FVG
    if prev["Low"] > nxt["High"]:
        fvgs.append({
            "time"  : time,
            "type"  : "Bearish FVG",
            "top"   : round(prev["Low"], 2),
            "bottom": round(nxt["High"], 2),
            "size"  : round(prev["Low"] - nxt["High"], 2)
        })

# Print results
if fvgs:
    print(f"Found {len(fvgs)} FVGs:\n")
    for fvg in fvgs:
        print(f"  {fvg['type']} | {fvg['time']} | Top: {fvg['top']} | Bottom: {fvg['bottom']} | Size: {fvg['size']} pts")
else:
    print("No FVGs found in this period.")