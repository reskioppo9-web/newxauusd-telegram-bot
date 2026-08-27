import os
import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TWELVE_DATA_API_KEY = os.environ["TWELVE_DATA_API_KEY"]


def get_gold_price():
    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": "XAU/USD",
        "interval": "30min",
        "outputsize": 2,
        "apikey": TWELVE_DATA_API_KEY
    }

    response = requests.get(url, params=params)
    data = response.json()

    if "values" not in data:
        raise Exception(f"Data error: {data}")

    latest = data["values"][0]

    return {
        "time": latest["datetime"],
        "open": latest["open"],
        "high": latest["high"],
        "low": latest["low"],
        "close": latest["close"]
    }


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
    )

    print(response.text)


gold = get_gold_price()

message = (
    "🟡 XAUUSD M30\n\n"
    f"Time  : {gold['time']}\n"
    f"Open  : {gold['open']}\n"
    f"High  : {gold['high']}\n"
    f"Low   : {gold['low']}\n"
    f"Close : {gold['close']}\n\n"
    "📡 Data berhasil diterima."
)

send_telegram(message)
