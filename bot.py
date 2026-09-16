import os
import requests
import pandas as pd
import numpy as np

# ============================================================
# XAUUSD AI-STYLE V1.6.7
# CONFIDENCE CALIBRATION + HTF/LTF BIAS ENGINE
# ============================================================

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TWELVE_DATA_API_KEY = os.environ["TWELVE_DATA_API_KEY"]

SYMBOL = "XAU/USD"
BASE_URL = "https://api.twelvedata.com/time_series"


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        },
        timeout=20
    )

    response.raise_for_status()


# ============================================================
# DATA
# ============================================================

def get_data(interval, outputsize=250):

    params = {
        "symbol": SYMBOL,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_API_KEY,
        "format": "JSON"
    }

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    if "values" not in data:
        raise Exception(f"Twelve Data error: {data}")

    df = pd.DataFrame(data["values"])

    df["datetime"] = pd.to_datetime(
        df["datetime"]
    )

    for col in [
        "open",
        "high",
        "low",
        "close"
    ]:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = (
        df
        .sort_values("datetime")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# INDICATORS
# ============================================================

def add_indicators(df):

    df["ema20"] = df["close"].ewm(
        span=20,
        adjust=False
    ).mean()

    df["ema50"] = df["close"].ewm(
        span=50,
        adjust=False
    ).mean()

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

    rs = avg_gain / avg_loss.replace(
        0,
        np.nan
    )

    df["rsi"] = 100 - (
        100 / (1 + rs)
    )

    previous_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]

    tr2 = (
        df["high"] - previous_close
    ).abs()

    tr3 = (
        df["low"] - previous_close
    ).abs()

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    df["atr"] = tr.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    return df


# ============================================================
# TIMEFRAME
# ============================================================

def analyze_timeframe(df):

    row = df.iloc[-2]

    price = row["close"]
    ema20 = row["ema20"]
    ema50 = row["ema50"]

    if price > ema20 > ema50:
        return "BULLISH"

    if price < ema20 < ema50:
        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# SWINGS
# ============================================================

def find_swings(df, lookback=3):

    highs = []
    lows = []

    end = len(df) - 1

    for i in range(
        lookback,
        end - lookback
    ):

        high = df["high"].iloc[i]
        low = df["low"].iloc[i]

        left_high = df["high"].iloc[
            i - lookback:i
        ].max()

        right_high = df["high"].iloc[
            i + 1:i + 1 + lookback
        ].max()

        left_low = df["low"].iloc[
            i - lookback:i
        ].min()

        right_low = df["low"].iloc[
            i + 1:i + 1 + lookback
        ].min()

        if (
            high > left_high
            and high > right_high
        ):

            highs.append(
                (i, high)
            )

        if (
            low < left_low
            and low < right_low
        ):

            lows.append(
                (i, low)
            )

    return highs, lows


# ============================================================
# MARKET STRUCTURE
# ============================================================

def detect_market_structure(df):

    highs, lows = find_swings(df)

    if len(highs) < 2 or len(lows) < 2:

        return {
            "structure": "MIXED",
            "high_label": "N/A",
            "low_label": "N/A",
            "last_high": None,
            "last_low": None
        }

    previous_high = highs[-2][1]
    last_high = highs[-1][1]

    previous_low = lows[-2][1]
    last_low = lows[-1][1]

    high_label = (
        "HH"
        if last_high > previous_high
        else "LH"
    )

    low_label = (
        "HL"
        if last_low > previous_low
        else "LL"
    )

    if (
        high_label == "HH"
        and low_label == "HL"
    ):

        structure = "BULLISH"

    elif (
        high_label == "LH"
        and low_label == "LL"
    ):

        structure = "BEARISH"

    else:

        structure = "MIXED"

    return {
        "structure": structure,
        "high_label": high_label,
        "low_label": low_label,
        "last_high": last_high,
        "last_low": last_low
    }


# ============================================================
# BOS / CHOCH
# ============================================================

def detect_bos_choch(df, structure):

    row = df.iloc[-2]

    close = row["close"]

    last_high = structure["last_high"]
    last_low = structure["last_low"]

    bos = "NONE"
    choch = "NONE"

    if (
        last_high is not None
        and close > last_high
    ):

        if structure["structure"] == "BULLISH":
            bos = "BULLISH BOS"
        else:
            choch = "BULLISH CHoCH"

    elif (
        last_low is not None
        and close < last_low
    ):

        if structure["structure"] == "BEARISH":
            bos = "BEARISH BOS"
        else:
            choch = "BEARISH CHoCH"

    return bos, choch


# ============================================================
# CANDLE
# ============================================================

def candle_confirmation(df):

    row = df.iloc[-2]
    prev = df.iloc[-3]

    o = row["open"]
    h = row["high"]
    l = row["low"]
    c = row["close"]

    po = prev["open"]
    pc = prev["close"]

    body = abs(c - o)
    candle_range = h - l

    if candle_range <= 0:
        return "NONE"

    body_ratio = body / candle_range

    bullish_engulfing = (
        c > o
        and pc < po
        and c > po
        and o < pc
    )

    bearish_engulfing = (
        c < o
        and pc > po
        and c < po
        and o > pc
    )

    upper_wick = (
        h - max(o, c)
    )

    lower_wick = (
        min(o, c) - l
    )

    bullish_rejection = (
        lower_wick > body * 1.5
        and c > o
    )

    bearish_rejection = (
        upper_wick > body * 1.5
        and c < o
    )

    if bullish_engulfing:
        return "BULLISH ENGULFING"

    if bearish_engulfing:
        return "BEARISH ENGULFING"

    if bullish_rejection:
        return "BULLISH REJECTION"

    if bearish_rejection:
        return "BEARISH REJECTION"

    if body_ratio >= 0.65:

        if c > o:
            return "BULLISH MOMENTUM"

        if c < o:
            return "BEARISH MOMENTUM"

    return "NONE"


# ============================================================
# LIQUIDITY
# ============================================================

def detect_liquidity_sweep(df):

    row = df.iloc[-2]

    previous = df.iloc[-7:-2]

    prior_high = previous["high"].max()
    prior_low = previous["low"].min()

    bullish = (
        row["low"] < prior_low
        and row["close"] > prior_low
    )

    bearish = (
        row["high"] > prior_high
        and row["close"] < prior_high
    )

    if bullish:
        return "BULLISH LIQUIDITY SWEEP"

    if bearish:
        return "BEARISH LIQUIDITY SWEEP"

    return "NONE"


# ============================================================
# BREAKOUT
# ============================================================

def detect_breakout(df):

    row = df.iloc[-2]

    previous = df.iloc[-7:-2]

    previous_high = previous["high"].max()
    previous_low = previous["low"].min()

    if row["close"] > previous_high:
        return "BULLISH BREAKOUT"

    if row["close"] < previous_low:
        return "BEARISH BREAKOUT"

    return "NONE"


# ============================================================
# PULLBACK
# ============================================================

def detect_pullback(
    df,
    structure,
    atr
):

    row = df.iloc[-2]

    price = row["close"]
    ema20 = row["ema20"]

    if atr <= 0:
        return "NONE"

    distance = abs(
        price - ema20
    )

    if distance <= 0.60 * atr:

        if structure["structure"] == "BULLISH":
            return "BULLISH PULLBACK"

        if structure["structure"] == "BEARISH":
            return "BEARISH PULLBACK"

    return "NONE"


# ============================================================
# RETEST
# ============================================================

def detect_retest(df, structure):

    if len(df) < 8:
        return "NONE"

    recent = df.iloc[-7:-1]

    atr = recent["atr"].iloc[-1]

    if atr <= 0:
        return "NONE"

    tolerance = atr * 0.35

    last_high = structure["last_high"]
    last_low = structure["last_low"]

    # -------------------------
    # BULLISH RETEST
    # -------------------------

    if last_high is not None:

        for i in range(
            len(recent) - 1
        ):

            row1 = recent.iloc[i]
            row2 = recent.iloc[i + 1]

            breakout = (
                row1["close"] > last_high
            )

            retest = (
                abs(
                    row2["low"] - last_high
                ) <= tolerance
                and row2["close"] > last_high
            )

            if breakout and retest:
                return "BULLISH RETEST"

    # -------------------------
    # BEARISH RETEST
    # -------------------------

    if last_low is not None:

        for i in range(
            len(recent) - 1
        ):

            row1 = recent.iloc[i]
            row2 = recent.iloc[i + 1]

            breakout = (
                row1["close"] < last_low
            )

            retest = (
                abs(
                    row2["high"] - last_low
                ) <= tolerance
                and row2["close"] < last_low
            )

            if breakout and retest:
                return "BEARISH RETEST"

    return "NONE"


# ============================================================
# EMA STATE
# ============================================================

def detect_ema_state(row):

    atr = row["atr"]

    if atr <= 0:
        return "UNKNOWN"

    spread = abs(
        row["ema20"] - row["ema50"]
    )

    spread_atr = spread / atr

    if spread_atr <= 0.35:
        return "COMPRESSION"

    if spread_atr <= 0.60:
        return "TIGHT"

    return "EXPANDED"


# ============================================================
# EMA EXPANSION
# ============================================================

def detect_ema_expansion(df):

    current = df.iloc[-2]
    previous = df.iloc[-3]

    current_spread = abs(
        current["ema20"]
        - current["ema50"]
    )

    previous_spread = abs(
        previous["ema20"]
        - previous["ema50"]
    )

    atr = current["atr"]

    if atr <= 0:
        return "FLAT"

    increase = (
        current_spread
        - previous_spread
    ) / atr

    current_ratio = (
        current_spread / atr
    )

    if (
        increase > 0.03
        and current_ratio > 0.35
    ):

        return "EXPANDING"

    if increase > 0:
        return "EARLY EXPANSION"

    return "FLAT"


# ============================================================
# SMART LEVELS
# ============================================================

def smart_levels(df, atr):

    highs, lows = find_swings(df)

    price = df.iloc[-2]["close"]

    support_candidates = [
        value
        for _, value in lows
        if value < price
    ]

    resistance_candidates = [
        value
        for _, value in highs
        if value > price
    ]

    if support_candidates:

        support = max(
            support_candidates
        )

    else:

        support = price - 3 * atr

    if resistance_candidates:

        resistance = min(
            resistance_candidates
        )

    else:

        resistance = price + 3 * atr

    return support, resistance


# ============================================================
# S/R
# ============================================================

def detect_sr_proximity(
    price,
    support,
    resistance,
    atr
):

    if atr <= 0:

        return {
            "support_distance": 999,
            "resistance_distance": 999,
            "support_zone": False,
            "resistance_zone": False
        }

    support_distance = (
        abs(price - support) / atr
    )

    resistance_distance = (
        abs(resistance - price) / atr
    )

    return {
        "support_distance":
            support_distance,

        "resistance_distance":
            resistance_distance,

        "support_zone":
            support_distance <= 0.50,

        "resistance_zone":
            resistance_distance <= 0.50
    }


# ============================================================
# RANGE
# ============================================================

def detect_tight_range(
    support,
    resistance,
    atr
):

    if atr <= 0:
        return "UNKNOWN", 999

    width = resistance - support

    width_atr = width / atr

    if width_atr <= 0.50:
        return "TIGHT RANGE", width_atr

    if width_atr <= 0.90:
        return "NORMAL RANGE", width_atr

    return "EXPANDED RANGE", width_atr


# ============================================================
# MARKET PHASE V1.6.7
# ============================================================

def detect_market_phase(
    structure,
    h4,
    h1,
    bos,
    choch,
    breakout,
    candle,
    pullback,
    tight_range,
    price,
    ema20,
    atr
):

    if tight_range == "TIGHT RANGE":
        return "TIGHT RANGE"

    bullish_evidence = (
        choch == "BULLISH CHoCH"
        or breakout == "BULLISH BREAKOUT"
        or candle.startswith("BULLISH")
    )

    bearish_evidence = (
        choch == "BEARISH CHoCH"
        or breakout == "BEARISH BREAKOUT"
        or candle.startswith("BEARISH")
    )

    htf_bearish = (
        h4 == "BEARISH"
        and h1 == "BEARISH"
    )

    htf_bullish = (
        h4 == "BULLISH"
        and h1 == "BULLISH"
    )

    # --------------------------------------------------------
    # HTF/LTF TRANSITION
    # --------------------------------------------------------

    if htf_bearish and bullish_evidence:

        return (
            "BEARISH HTF / "
            "BULLISH LTF TRANSITION"
        )

    if htf_bullish and bearish_evidence:

        return (
            "BULLISH HTF / "
            "BEARISH LTF TRANSITION"
        )

    # --------------------------------------------------------
    # CONFIRMED CONTINUATION
    # --------------------------------------------------------

    if (
        structure == "BULLISH"
        and bos == "BULLISH BOS"
    ):

        return "BULLISH CONTINUATION"

    if (
        structure == "BEARISH"
        and bos == "BEARISH BOS"
    ):

        return "BEARISH CONTINUATION"

    # --------------------------------------------------------
    # REAL PULLBACK
    # --------------------------------------------------------

    if pullback == "BULLISH PULLBACK":

        return "BULLISH PULLBACK"

    if pullback == "BEARISH PULLBACK":

        return "BEARISH PULLBACK"

    # --------------------------------------------------------
    # EXTENSION
    # --------------------------------------------------------

    if atr > 0:

        distance = (
            abs(price - ema20) / atr
        )

        if (
            structure == "BEARISH"
            and price < ema20
            and distance > 0.60
        ):

            return "BEARISH TREND / EXTENSION"

        if (
            structure == "BULLISH"
            and price > ema20
            and distance > 0.60
        ):

            return "BULLISH TREND / EXTENSION"

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    if structure == "BULLISH":
        return "BULLISH TREND"

    if structure == "BEARISH":
        return "BEARISH TREND"

    return "RANGE / MIXED"


# ============================================================
# HTF BIAS
# ============================================================

def detect_htf_bias(h4, h1):

    if (
        h4 == "BULLISH"
        and h1 == "BULLISH"
    ):

        return "BULLISH"

    if (
        h4 == "BEARISH"
        and h1 == "BEARISH"
    ):

        return "BEARISH"

    if (
        h4 == "NEUTRAL"
        and h1 == "NEUTRAL"
    ):

        return "NEUTRAL"

    return "MIXED"


# ============================================================
# LTF BIAS
# ============================================================

def detect_ltf_bias(
    m30,
    m15,
    choch,
    breakout,
    candle
):

    bullish_evidence = (
        choch == "BULLISH CHoCH"
        or breakout == "BULLISH BREAKOUT"
        or candle.startswith("BULLISH")
    )

    bearish_evidence = (
        choch == "BEARISH CHoCH"
        or breakout == "BEARISH BREAKOUT"
        or candle.startswith("BEARISH")
    )

    if (
        m30 == "BULLISH"
        and m15 == "BULLISH"
    ):

        return "BULLISH"

    if (
        m30 == "BEARISH"
        and m15 == "BEARISH"
    ):

        return "BEARISH"

    if bullish_evidence and not bearish_evidence:

        return "BULLISH TRANSITION"

    if bearish_evidence and not bullish_evidence:

        return "BEARISH TRANSITION"

    if (
        m30 == "NEUTRAL"
        and m15 == "NEUTRAL"
    ):

        return "NEUTRAL"

    return "MIXED"


# ============================================================
# SIGNAL SCORE
# ============================================================

def calculate_score(
    h4,
    h1,
    m30,
    m15,
    structure,
    bos,
    choch,
    candle,
    liquidity,
    breakout,
    pullback,
    retest,
    rsi
):

    buy = 0
    sell = 0

    timeframe_weights = [
        (h4, 15),
        (h1, 20),
        (m30, 15),
        (m15, 10)
    ]

    for direction, weight in timeframe_weights:

        if direction == "BULLISH":
            buy += weight

        elif direction == "BEARISH":
            sell += weight

    # RSI
    if 50 <= rsi <= 70:
        buy += 10

    elif 30 <= rsi < 50:
        sell += 10

    # Structure
    if structure == "BULLISH":
        buy += 10

    elif structure == "BEARISH":
        sell += 10

    # BOS
    if bos == "BULLISH BOS":
        buy += 10

    elif bos == "BEARISH BOS":
        sell += 10

    # CHoCH
    if choch == "BULLISH CHoCH":
        buy += 8

    elif choch == "BEARISH CHoCH":
        sell += 8

    # Candle
    if candle.startswith("BULLISH"):
        buy += 5

    elif candle.startswith("BEARISH"):
        sell += 5

    # Liquidity
    if liquidity.startswith("BULLISH"):
        buy += 5

    elif liquidity.startswith("BEARISH"):
        sell += 5

    # Breakout
    if breakout == "BULLISH BREAKOUT":
        buy += 5

    elif breakout == "BEARISH BREAKOUT":
        sell += 5

    # Pullback
    if pullback == "BULLISH PULLBACK":
        buy += 3

    elif pullback == "BEARISH PULLBACK":
        sell += 3

    # Retest
    if retest == "BULLISH RETEST":
        buy += 7

    elif retest == "BEARISH RETEST":
        sell += 7

    return (
        min(buy, 100),
        min(sell, 100)
    )


# ============================================================
# CONFIDENCE LABEL
# ============================================================

def confidence_label(confidence):

    if confidence < 30:
        return "LOW EVIDENCE"

    if confidence < 45:
        return "WEAK"

    if confidence < 60:
        return "MODERATE"

    if confidence < 75:
        return "GOOD"

    if confidence < 90:
        return "HIGH"

    return "VERY HIGH"


# ============================================================
# CONFIDENCE ENGINE V1.6.7
# ============================================================

def calculate_confidence(
    buy_score,
    sell_score,
    h4,
    h1,
    m30,
    m15,
    structure,
    phase,
    bos,
    choch,
    breakout,
    candle,
    liquidity,
    retest,
    ema_state,
    ema_expansion,
    tight_range,
    range_width_atr,
    sr,
    rsi,
    htf_bias,
    ltf_bias
):

    dominant_score = max(
        buy_score,
        sell_score
    )

    confidence = 20.0

    # --------------------------------------------------------
    # BASE SIGNAL STRENGTH
    # --------------------------------------------------------

    confidence += dominant_score * 0.25

    # --------------------------------------------------------
    # HTF BIAS
    # --------------------------------------------------------

    if htf_bias in [
        "BULLISH",
        "BEARISH"
    ]:

        confidence += 8

    elif htf_bias == "MIXED":

        confidence -= 2

    # --------------------------------------------------------
    # MTF ALIGNMENT
    # --------------------------------------------------------

    directions = [
        h4,
        h1,
        m30,
        m15
    ]

    bullish_count = directions.count(
        "BULLISH"
    )

    bearish_count = directions.count(
        "BEARISH"
    )

    if bullish_count >= 3:
        confidence += 8

    elif bearish_count >= 3:
        confidence += 8

    # --------------------------------------------------------
    # LTF BIAS
    # --------------------------------------------------------

    if ltf_bias in [
        "BULLISH",
        "BEARISH"
    ]:

        confidence += 5

    elif "TRANSITION" in ltf_bias:

        confidence += 3

    elif ltf_bias == "MIXED":

        confidence -= 2

    # --------------------------------------------------------
    # STRUCTURE
    # --------------------------------------------------------

    if structure in [
        "BULLISH",
        "BEARISH"
    ]:

        confidence += 8

    else:

        confidence -= 4

    # --------------------------------------------------------
    # BOS / CHOCH
    # --------------------------------------------------------

    if bos != "NONE":

        confidence += 12

    elif choch != "NONE":

        confidence += 6

    # --------------------------------------------------------
    # BREAKOUT
    # --------------------------------------------------------

    if breakout != "NONE":

        confidence += 4

    # --------------------------------------------------------
    # CANDLE
    # --------------------------------------------------------

    if candle != "NONE":

        confidence += 3

    # --------------------------------------------------------
    # LIQUIDITY
    # --------------------------------------------------------

    if liquidity != "NONE":

        confidence += 4

    # --------------------------------------------------------
    # RETEST
    # --------------------------------------------------------

    if retest != "NONE":

        confidence += 7

    # --------------------------------------------------------
    # EMA STATE
    # --------------------------------------------------------

    if ema_state == "EXPANDED":

        confidence += 4

    elif ema_state == "TIGHT":

        confidence -= 2

    elif ema_state == "COMPRESSION":

        confidence -= 5

    # --------------------------------------------------------
    # EMA EXPANSION
    # --------------------------------------------------------

    if ema_expansion == "EXPANDING":

        confidence += 3

    elif ema_expansion == "EARLY EXPANSION":

        confidence += 2

    elif ema_expansion == "FLAT":

        confidence -= 2

    # --------------------------------------------------------
    # RANGE
    # --------------------------------------------------------

    if tight_range == "TIGHT RANGE":

        confidence -= 15

    elif tight_range == "NORMAL RANGE":

        confidence -= 3

    # --------------------------------------------------------
    # TRANSITION
    # --------------------------------------------------------

    if "TRANSITION" in phase:

        confidence -= 4

    # --------------------------------------------------------
    # S/R
    # --------------------------------------------------------

    if (
        sr["support_zone"]
        and sr["resistance_zone"]
    ):

        confidence -= 5

    elif (
        sr["support_zone"]
        or sr["resistance_zone"]
    ):

        confidence -= 3

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if 40 <= rsi <= 60:

        confidence += 2

    elif (
        rsi >= 75
        or rsi <= 25
    ):

        confidence -= 6

    # --------------------------------------------------------
    # VERY NARROW RANGE
    # --------------------------------------------------------

    if range_width_atr <= 0.30:

        confidence -= 4

    # --------------------------------------------------------
    # MINIMUM FLOOR
    # --------------------------------------------------------

    confidence = max(
        15,
        confidence
    )

    confidence = min(
        100,
        confidence
    )

    return int(
        round(confidence)
    )


# ============================================================
# ENTRY QUALITY
# ============================================================

def calculate_entry_quality(
    structure,
    phase,
    ema_state,
    ema_expansion,
    breakout,
    choch,
    bos,
    pullback,
    retest,
    sr,
    tight_range,
    candle,
    rsi
):

    quality = 100

    if tight_range == "TIGHT RANGE":
        quality -= 25

    if structure == "MIXED":
        quality -= 15

    if ema_state == "COMPRESSION":
        quality -= 15

    elif ema_state == "TIGHT":
        quality -= 7

    if ema_expansion == "FLAT":
        quality -= 5

    if breakout != "NONE":
        quality += 5

    if bos != "NONE":
        quality += 8

    if choch != "NONE":
        quality += 4

    if retest != "NONE":
        quality += 8

    if pullback != "NONE":
        quality += 3

    if candle != "NONE":
        quality += 3

    if (
        sr["support_zone"]
        and sr["resistance_zone"]
    ):

        quality -= 15

    else:

        if sr["support_zone"]:
            quality -= 10

        if sr["resistance_zone"]:
            quality -= 10

    if rsi >= 75 or rsi <= 25:
        quality -= 15

    return max(
        0,
        min(
            100,
            quality
        )
    )


# ============================================================
# CONFLICT FILTER
# ============================================================

def conflict_filter(
    h4,
    h1,
    choch,
    bos
):

    htf_bearish = (
        h4 == "BEARISH"
        and h1 == "BEARISH"
    )

    htf_bullish = (
        h4 == "BULLISH"
        and h1 == "BULLISH"
    )

    sell_blocked = False
    buy_blocked = False

    if (
        htf_bearish
        and choch == "BULLISH CHoCH"
        and bos != "BEARISH BOS"
    ):

        sell_blocked = True

    if (
        htf_bullish
        and choch == "BEARISH CHoCH"
        and bos != "BULLISH BOS"
    ):

        buy_blocked = True

    return buy_blocked, sell_blocked


# ============================================================
# TRIGGER ENGINE
# ============================================================

def build_trigger_engine(
    support,
    resistance,
    tight_range,
    phase,
    choch,
    breakout
):

    sell_trigger = (
        f"Break support {support:.2f}"
        "\n→ bearish BOS"
        "\n→ retest"
        "\n→ bearish confirmation"
    )

    buy_trigger = (
        f"Break resistance {resistance:.2f}"
        "\n→ bullish BOS"
        "\n→ retest"
        "\n→ bullish confirmation"
    )

    if tight_range == "TIGHT RANGE":

        return (
            "🔴 SELL WATCH\n"
            + sell_trigger
            + "\n\n"
            "🟢 BUY WATCH\n"
            + buy_trigger
        )

    if (
        phase
        == "BEARISH HTF / BULLISH LTF TRANSITION"
    ):

        return (
            "🟢 BUY WATCH\n"
            + buy_trigger
            + "\n\n"
            "🔴 SELL INVALIDATION\n"
            + sell_trigger
        )

    if (
        phase
        == "BULLISH HTF / BEARISH LTF TRANSITION"
    ):

        return (
            "🔴 SELL WATCH\n"
            + sell_trigger
            + "\n\n"
            "🟢 BUY INVALIDATION\n"
            + buy_trigger
        )

    if phase == "BEARISH TREND / EXTENSION":

        return (
            "🔴 SELL CONTINUATION WATCH\n"
            + "Wait pullback toward EMA20 / resistance"
            + "\n→ bearish rejection"
            + "\n→ continuation confirmation"
            + "\n\n"
            "🟢 BUY INVALIDATION\n"
            + buy_trigger
        )

    if phase == "BULLISH TREND / EXTENSION":

        return (
            "🟢 BUY CONTINUATION WATCH\n"
            + "Wait pullback toward EMA20 / support"
            + "\n→ bullish rejection"
            + "\n→ continuation confirmation"
            + "\n\n"
            "🔴 SELL INVALIDATION\n"
            + sell_trigger
        )

    return (
        "🔴 SELL WATCH\n"
        + sell_trigger
        + "\n\n"
        "🟢 BUY WATCH\n"
        + buy_trigger
    )


# ============================================================
# TRADE PLAN
# ============================================================

def trade_plan(
    direction,
    price,
    atr
):

    if direction == "BUY":

        sl = price - 1.5 * atr
        tp1 = price + 2.25 * atr
        tp2 = price + 3.75 * atr

    else:

        sl = price + 1.5 * atr
        tp1 = price - 2.25 * atr
        tp2 = price - 3.75 * atr

    return sl, tp1, tp2


# ============================================================
# MAIN
# ============================================================

def analyze():

    timeframes = {
        "H4": "4h",
        "H1": "1h",
        "M30": "30min",
        "M15": "15min"
    }

    datasets = {}

    for name, interval in timeframes.items():

        df = get_data(interval)

        df = add_indicators(df)

        datasets[name] = df

    # --------------------------------------------------------
    # MTF
    # --------------------------------------------------------

    h4 = analyze_timeframe(
        datasets["H4"]
    )

    h1 = analyze_timeframe(
        datasets["H1"]
    )

    m30 = analyze_timeframe(
        datasets["M30"]
    )

    m15 = analyze_timeframe(
        datasets["M15"]
    )

    # --------------------------------------------------------
    # M30 ENGINE
    # --------------------------------------------------------

    df = datasets["M30"]

    row = df.iloc[-2]

    price = row["close"]
    ema20 = row["ema20"]
    ema50 = row["ema50"]
    rsi = row["rsi"]
    atr = row["atr"]

    structure = detect_market_structure(
        df
    )

    bos, choch = detect_bos_choch(
        df,
        structure
    )

    candle = candle_confirmation(
        df
    )

    liquidity = detect_liquidity_sweep(
        df
    )

    breakout = detect_breakout(
        df
    )

    pullback = detect_pullback(
        df,
        structure,
        atr
    )

    retest = detect_retest(
        df,
        structure
    )

    ema_state = detect_ema_state(
        row
    )

    ema_expansion = detect_ema_expansion(
        df
    )

    support, resistance = smart_levels(
        df,
        atr
    )

    sr = detect_sr_proximity(
        price,
        support,
        resistance,
        atr
    )

    tight_range, range_width_atr = (
        detect_tight_range(
            support,
            resistance,
            atr
        )
    )

    # --------------------------------------------------------
    # BIAS
    # --------------------------------------------------------

    htf_bias = detect_htf_bias(
        h4,
        h1
    )

    ltf_bias = detect_ltf_bias(
        m30,
        m15,
        choch,
        breakout,
        candle
    )

    # --------------------------------------------------------
    # MARKET PHASE
    # --------------------------------------------------------

    phase = detect_market_phase(
        structure["structure"],
        h4,
        h1,
        bos,
        choch,
        breakout,
        candle,
        pullback,
        tight_range,
        price,
        ema20,
        atr
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    buy_score, sell_score = calculate_score(
        h4,
        h1,
        m30,
        m15,
        structure["structure"],
        bos,
        choch,
        candle,
        liquidity,
        breakout,
        pullback,
        retest,
        rsi
    )

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    confidence = calculate_confidence(
        buy_score,
        sell_score,
        h4,
        h1,
        m30,
        m15,
        structure["structure"],
        phase,
        bos,
        choch,
        breakout,
        candle,
        liquidity,
        retest,
        ema_state,
        ema_expansion,
        tight_range,
        range_width_atr,
        sr,
        rsi,
        htf_bias,
        ltf_bias
    )

    confidence_text = confidence_label(
        confidence
    )

    # --------------------------------------------------------
    # ENTRY QUALITY
    # --------------------------------------------------------

    quality = calculate_entry_quality(
        structure["structure"],
        phase,
        ema_state,
        ema_expansion,
        breakout,
        choch,
        bos,
        pullback,
        retest,
        sr,
        tight_range,
        candle,
        rsi
    )

    # --------------------------------------------------------
    # CONFLICT
    # --------------------------------------------------------

    buy_blocked, sell_blocked = (
        conflict_filter(
            h4,
            h1,
            choch,
            bos
        )
    )

    # ========================================================
    # DECISION
    # ========================================================

    decision = "WAIT"

    if tight_range == "TIGHT RANGE":

        decision = "WAIT"

    else:

        adjusted_buy = buy_score
        adjusted_sell = sell_score

        if buy_blocked:

            adjusted_buy = min(
                adjusted_buy,
                40
            )

        if sell_blocked:

            adjusted_sell = min(
                adjusted_sell,
                40
            )

        if (
            adjusted_buy >= 70
            and adjusted_buy > adjusted_sell
            and not sr["resistance_zone"]
            and quality >= 60
        ):

            decision = "BUY"

        elif (
            adjusted_sell >= 70
            and adjusted_sell > adjusted_buy
            and not sr["support_zone"]
            and quality >= 60
        ):

            decision = "SELL"

    # --------------------------------------------------------
    # WAIT CAP
    # --------------------------------------------------------

    if decision == "WAIT":

        confidence = min(
            confidence,
            69
        )

        confidence_text = confidence_label(
            confidence
        )

    # ========================================================
    # REASONS
    # ========================================================

    reasons = []

    def add_reason(text):

        if text not in reasons:
            reasons.append(text)

    if structure["structure"] == "MIXED":

        add_reason(
            "Market structure mixed"
        )

    if htf_bias in [
        "BULLISH",
        "BEARISH"
    ]:

        add_reason(
            f"HTF bias {htf_bias}"
        )

    if ltf_bias not in [
        "NEUTRAL"
    ]:

        add_reason(
            f"LTF bias {ltf_bias}"
        )

    if ema_state == "COMPRESSION":

        add_reason(
            "EMA20/EMA50 compression"
        )

    elif ema_state == "TIGHT":

        add_reason(
            "EMA20/EMA50 tight"
        )

    elif ema_state == "EXPANDED":

        add_reason(
            "EMA20/EMA50 expanded"
        )

    if ema_expansion == "FLAT":

        add_reason(
            "EMA expansion flat"
        )

    elif ema_expansion == "EXPANDING":

        add_reason(
            "EMA expansion expanding"
        )

    if tight_range == "TIGHT RANGE":

        add_reason(
            f"Tight range "
            f"{range_width_atr:.2f} ATR"
        )

    if candle != "NONE":

        add_reason(candle)

    if choch != "NONE":

        add_reason(choch)

    if bos != "NONE":

        add_reason(bos)

    if breakout != "NONE":

        add_reason(breakout)

    if pullback != "NONE":

        add_reason(pullback)

    if retest != "NONE":

        add_reason(retest)

    if liquidity != "NONE":

        add_reason(liquidity)

    if "TRANSITION" in phase:

        add_reason(
            "HTF/LTF directional transition"
        )

    if (
        "EXTENSION" in phase
    ):

        add_reason(
            "Price extended from EMA20"
        )

    if (
        sr["support_zone"]
        and sr["resistance_zone"]
    ):

        add_reason(
            "Price trapped between S/R"
        )

    elif sr["support_zone"]:

        add_reason(
            "Price close to support"
        )

    elif sr["resistance_zone"]:

        add_reason(
            "Price close to resistance"
        )

    # ========================================================
    # TRIGGER
    # ========================================================

    next_trigger = build_trigger_engine(
        support,
        resistance,
        tight_range,
        phase,
        choch,
        breakout
    )

    # ========================================================
    # TRADE PLAN
    # ========================================================

    plan = ""

    if decision in [
        "BUY",
        "SELL"
    ]:

        sl, tp1, tp2 = trade_plan(
            decision,
            price,
            atr
        )

        plan = (
            "\n\n💰 TRADE PLAN"
            f"\nEntry : {price:.2f}"
            f"\nSL    : {sl:.2f}"
            f"\nTP1   : {tp1:.2f}"
            f"\nTP2   : {tp2:.2f}"
            "\nRR    : 1:1.5 / 1:2.5"
        )

    # ========================================================
    # MESSAGE
    # ========================================================

    icon = (
        "🟢"
        if decision == "BUY"
        else "🔴"
        if decision == "SELL"
        else "⚪"
    )

    message = (
        "🤖 XAUUSD AI-STYLE V1.6.7\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"{icon} {decision}\n\n"

        "📊 SIGNAL SCORE\n"
        f"BUY  : {buy_score}/100\n"
        f"SELL : {sell_score}/100\n\n"

        f"🧠 CONFIDENCE : "
        f"{confidence}/100\n"
        f"📌 CONFIDENCE STATE : "
        f"{confidence_text}\n"
        f"🎯 ENTRY QUALITY : "
        f"{quality}/100\n\n"

        "📈 MULTI-TIMEFRAME\n"
        f"H4  : {h4}\n"
        f"H1  : {h1}\n"
        f"M30 : {m30}\n"
        f"M15 : {m15}\n\n"

        "🧭 MARKET BIAS\n"
        f"HTF BIAS : {htf_bias}\n"
        f"LTF BIAS : {ltf_bias}\n\n"

        "🏗 MARKET STRUCTURE\n"
        f"Structure : "
        f"{structure['structure']}\n"
        f"High : {structure['high_label']}\n"
        f"Low  : {structure['low_label']}\n\n"

        "🧭 MARKET PHASE\n"
        f"{phase}\n\n"

        "📊 STRUCTURE EVENT\n"
        f"BOS       : {bos}\n"
        f"CHoCH     : {choch}\n"
        f"Liquidity : {liquidity}\n"
        f"Breakout  : {breakout}\n"
        f"Candle    : {candle}\n"
        f"Pullback  : {pullback}\n"
        f"Retest    : {retest}\n\n"

        "📐 EMA ENGINE\n"
        f"EMA20 : {ema20:.2f}\n"
        f"EMA50 : {ema50:.2f}\n"
        f"EMA Spread : "
        f"{abs(ema20 - ema50) / atr:.2f} ATR\n"
        f"Price → EMA20 : "
        f"{abs(price - ema20) / atr:.2f} ATR\n"
        f"EMA State : {ema_state}\n"
        f"EMA Expansion : "
        f"{ema_expansion}\n\n"

        "📦 MARKET RANGE\n"
        f"Range State : {tight_range}\n"
        f"Range Width : "
        f"{range_width_atr:.2f} ATR\n\n"

        f"💰 Price : {price:.2f}\n"
        f"RSI : {rsi:.2f}\n"
        f"ATR : {atr:.2f}\n\n"

        f"🟢 Support : {support:.2f}\n"
        f"🔴 Resistance : "
        f"{resistance:.2f}\n"
        f"Support Distance : "
        f"{sr['support_distance']:.2f} ATR\n"
        f"Resistance Distance : "
        f"{sr['resistance_distance']:.2f} ATR\n\n"
    )

    # ========================================================
    # BLOCK STATUS
    # ========================================================

    if tight_range == "TIGHT RANGE":

        message += (
            "⚠️ ENTRY BLOCKED\n"
            "Market berada dalam "
            "tight range.\n"
            "Tunggu breakout + BOS + "
            "retest.\n\n"
        )

    else:

        if sell_blocked:

            message += (
                "⚠️ SELL BLOCKED\n"
                "Bullish CHoCH melawan "
                "HTF bearish.\n\n"
            )

        if buy_blocked:

            message += (
                "⚠️ BUY BLOCKED\n"
                "Bearish CHoCH melawan "
                "HTF bullish.\n\n"
            )

        if sr["support_zone"]:

            message += (
                "⚠️ SELL ZONE BLOCKED\n"
                "Price terlalu dekat "
                "support.\n\n"
            )

        if sr["resistance_zone"]:

            message += (
                "⚠️ BUY ZONE BLOCKED\n"
                "Price terlalu dekat "
                "resistance.\n\n"
            )

    # ========================================================
    # REASONS
    # ========================================================

    if reasons:

        message += (
            "🧠 MARKET REASONS\n"
        )

        for reason in reasons[:12]:

            message += (
                f"• {reason}\n"
            )

        message += "\n"

    # ========================================================
    # TRIGGER
    # ========================================================

    message += (
        "🎯 NEXT TRIGGER\n"
        f"{next_trigger}"
        f"{plan}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📊 FINAL SCORE\n"
        f"BUY {buy_score} / "
        f"SELL {sell_score}"
    )

    return message


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        message = analyze()

        send_telegram(message)

        print(message)

    except Exception as e:

        error_message = (
            "❌ XAUUSD BOT ERROR\n\n"
            f"{type(e).__name__}: {e}"
        )

        print(error_message)

        send_telegram(
            error_message
        )