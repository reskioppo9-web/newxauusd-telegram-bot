import os
import requests
import pandas as pd

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TWELVE_DATA_API_KEY = os.environ["TWELVE_DATA_API_KEY"]

SYMBOL = "XAU/USD"


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

    df = df.sort_values("datetime").reset_index(drop=True)

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col])

    return df


def calculate_rsi(df, length=14):
    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / length,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / length,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def calculate_atr(df, length=14):
    previous_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]
    tr2 = abs(df["high"] - previous_close)
    tr3 = abs(df["low"] - previous_close)

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    return true_range.ewm(
        alpha=1 / length,
        adjust=False
    ).mean()


def get_h1_trend():
    df = get_data("1h", 250)

    df["ema200"] = df["close"].ewm(
        span=200,
        adjust=False
    ).mean()

    # Candle terakhir H1 yang sudah CLOSE
    latest = df.iloc[-2]

    if latest["close"] > latest["ema200"]:
        return "BULLISH"

    if latest["close"] < latest["ema200"]:
        return "BEARISH"

    return "NEUTRAL"


def generate_signal():

    df = get_data("30min", 250)

    df["ema20"] = df["close"].ewm(
        span=20,
        adjust=False
    ).mean()

    df["ema50"] = df["close"].ewm(
        span=50,
        adjust=False
    ).mean()

    df["rsi"] = calculate_rsi(df)
    df["atr"] = calculate_atr(df)

    # Gunakan candle M30 yang SUDAH CLOSE
    latest = df.iloc[-2]

    price = latest["close"]
    ema20 = latest["ema20"]
    ema50 = latest["ema50"]
    rsi = latest["rsi"]
    atr = latest["atr"]

    h1_trend = get_h1_trend()

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

        entry = price
        sl = entry - (1.5 * atr)
        tp1 = entry + (1.0 * atr)
        tp2 = entry + (2.0 * atr)

    elif sell:
        signal = "SELL"

        entry = price
        sl = entry + (1.5 * atr)
        tp1 = entry - (1.0 * atr)
        tp2 = entry - (2.0 * atr)

    else:
        signal = "NO SIGNAL"

        entry = price
        sl = None
        tp1 = None
        tp2 = None

    return {
        "signal": signal,
        "time": latest["datetime"],
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "atr": atr,
        "h1_trend": h1_trend,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2
    }


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


result = generate_signal()

print(result)

if result["signal"] == "NO SIGNAL":

    message = (
        "📊 XAUUSD M30 SCANNER\n\n"
        "⚪ NO SIGNAL\n\n"
        f"H1 Trend : {result['h1_trend']}\n"
        f"Price    : {result['price']:.2f}\n"
        f"EMA 20   : {result['ema20']:.2f}\n"
        f"EMA 50   : {result['ema50']:.2f}\n"
        f"RSI 14   : {result['rsi']:.2f}\n"
        f"ATR 14   : {result['atr']:.2f}\n\n"
        f"Candle   : {result['time']}\n"
    )

else:

    emoji = "🟢" if result["signal"] == "BUY" else "🔴"

    message = (
        f"{emoji} XAUUSD {result['signal']} SIGNAL\n\n"
        f"⏱ TF       : M30\n"
        f"📍 Entry    : {result['entry']:.2f}\n"
        f"🛑 SL       : {result['sl']:.2f}\n"
        f"🎯 TP1      : {result['tp1']:.2f}\n"
        f"🎯 TP2      : {result['tp2']:.2f}\n\n"
        f"H1 Trend   : {result['h1_trend']}\n"
        f"RSI 14     : {result['rsi']:.2f}\n"
        f"ATR 14     : {result['atr']:.2f}\n\n"
        f"⏱ Candle   : {result['time']}\n\n"
        "⚠️ Signal only — manage your risk."
    )

send_telegram(message)
