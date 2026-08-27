import os
import requests
import pandas as pd

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TWELVE_DATA_API_KEY = os.environ["TWELVE_DATA_API_KEY"]

SYMBOL = "XAU/USD"
INTERVAL = "30min"


# =========================
# GET PRICE DATA
# =========================

def get_data(interval, outputsize=250):
    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": SYMBOL,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_API_KEY
    }

    response = requests.get(url, params=params, timeout=20)
    data = response.json()

    if "values" not in data:
        raise Exception(f"Twelve Data error: {data}")

    df = pd.DataFrame(data["values"])

    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime")

    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(df[column])

    return df


# =========================
# INDICATORS
# =========================

def calculate_indicators(df):

    # EMA M30
    df["ema20"] = df["close"].ewm(
        span=20,
        adjust=False
    ).mean()

    df["ema50"] = df["close"].ewm(
        span=50,
        adjust=False
    ).mean()

    # RSI 14
    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss

    df["rsi"] = 100 - (100 / (1 + rs))

    return df


# =========================
# H1 TREND
# =========================

def get_h1_trend():

    df = get_data("1h", 250)

    df["ema200"] = df["close"].ewm(
        span=200,
        adjust=False
    ).mean()

    latest = df.iloc[-1]

    if latest["close"] > latest["ema200"]:
        return "BULLISH"

    elif latest["close"] < latest["ema200"]:
        return "BEARISH"

    return "NEUTRAL"


# =========================
# SIGNAL
# =========================

def generate_signal():

    df = get_data(INTERVAL, 250)
    df = calculate_indicators(df)

    h1_trend = get_h1_trend()

    latest = df.iloc[-1]

    price = latest["close"]
    ema20 = latest["ema20"]
    ema50 = latest["ema50"]
    rsi = latest["rsi"]

    buy = (
        h1_trend == "BULLISH"
        and ema20 > ema50
        and rsi > 50
        and price > ema20
    )

    sell = (
        h1_trend == "BEARISH"
        and ema20 < ema50
        and rsi < 50
        and price < ema20
    )

    if buy:
        signal = "BUY"

    elif sell:
        signal = "SELL"

    else:
        signal = "NO SIGNAL"

    return {
        "signal": signal,
        "time": latest["datetime"],
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "h1_trend": h1_trend
    }


# =========================
# TELEGRAM
# =========================

def send_telegram(message):

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        },
        timeout=20
    )

    response.raise_for_status()


# =========================
# MAIN
# =========================

result = generate_signal()

print(result)

message = (
    "📊 XAUUSD M30 SCANNER\n\n"
    f"Signal : {result['signal']}\n"
    f"Price  : {result['price']:.2f}\n\n"
    f"H1 Trend : {result['h1_trend']}\n"
    f"EMA 20   : {result['ema20']:.2f}\n"
    f"EMA 50   : {result['ema50']:.2f}\n"
    f"RSI 14   : {result['rsi']:.2f}\n\n"
    f"Time : {result['time']}\n\n"
    "⚠️ Signal only — manage your risk."
)

send_telegram(message)
