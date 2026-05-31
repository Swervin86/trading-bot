import time
import os
import oandapyV20
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.pricing as pricing
import pandas as pd
import numpy as np

# --- CONFIG ---
API_TOKEN = os.environ.get("OANDA_TOKEN", "")
ACCOUNT_ID = "101-001-39455957-001"
ENVIRONMENT = "practice"
INSTRUMENTS = ["EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF"]
UNITS = 10000
CANDLE_COUNT = 50
GRANULARITY = "M1"
STOP_LOSS_PIPS = 15
TAKE_PROFIT_PIPS = 30
PIP = 0.0001
JPY_PIP = 0.01  # JPY pairs use a different pip size

client = oandapyV20.API(access_token=API_TOKEN, environment=ENVIRONMENT)

def get_current_price(instrument):
    params = {"instruments": instrument}
    r = pricing.PricingInfo(ACCOUNT_ID, params=params)
    client.request(r)
    price = r.response["prices"][0]
    bid = float(price["bids"][0]["price"])
    ask = float(price["asks"][0]["price"])
    return bid, ask

def get_candles(instrument):
    params = {"count": CANDLE_COUNT, "granularity": GRANULARITY}
    r = instruments.InstrumentsCandles(instrument, params=params)
    client.request(r)
    candles = r.response["candles"]
    closes = [float(c["mid"]["c"]) for c in candles if c["complete"]]
    return closes

def rsi(prices, period=14):
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(prices):
    prices = np.array(prices)
    ema12 = pd.Series(prices).ewm(span=12).mean().iloc[-1]
    ema26 = pd.Series(prices).ewm(span=26).mean().iloc[-1]
    return ema12 - ema26

def get_open_trades():
    r = trades.OpenTrades(ACCOUNT_ID)
    client.request(r)
    return r.response.get("trades", [])

def close_all_trades():
    open_trades = get_open_trades()
    for trade in open_trades:
        r = trades.TradeClose(ACCOUNT_ID, trade["id"])
        client.request(r)
        print(f"Closed trade {trade['id']}")

def place_order(instrument, units):
    bid, ask = get_current_price(instrument)
    pip = JPY_PIP if "JPY" in instrument else PIP
    if units > 0:  # BUY
        entry = ask
        sl = round(entry - STOP_LOSS_PIPS * pip, 5)
        tp = round(entry + TAKE_PROFIT_PIPS * pip, 5)
    else:  # SELL
        entry = bid
        sl = round(entry + STOP_LOSS_PIPS * pip, 5)
        tp = round(entry - TAKE_PROFIT_PIPS * pip, 5)

    data = {
        "order": {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(units),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
            "stopLossOnFill": {"price": str(sl)},
            "takeProfitOnFill": {"price": str(tp)}
        }
    }
    r = orders.Orders(ACCOUNT_ID, data=data)
    client.request(r)
    print(f"[{instrument}] Order placed: {units} units | SL: {sl} | TP: {tp}")

def trade_instrument(instrument):
    closes = get_candles(instrument)
    current_rsi = rsi(closes)
    current_macd = macd(closes)

    print(f"[{instrument}] RSI: {current_rsi:.2f} | MACD: {current_macd:.6f}")

    open_trades = get_open_trades()
    instrument_trades = [t for t in open_trades if t["instrument"] == instrument]

    if current_rsi < 30 and current_macd > 0:
        if not instrument_trades:
            print(f"[{instrument}] Signal: BUY")
            place_order(instrument, UNITS)
        elif instrument_trades[0]["currentUnits"].startswith("-"):
            close_all_trades()
            place_order(instrument, UNITS)

    elif current_rsi > 70 and current_macd < 0:
        if not instrument_trades:
            print(f"[{instrument}] Signal: SELL")
            place_order(instrument, -UNITS)
        elif not instrument_trades[0]["currentUnits"].startswith("-"):
            close_all_trades()
            place_order(instrument, -UNITS)

    else:
        print(f"[{instrument}] No signal — holding")

def run():
    if not API_TOKEN:
        print("ERROR: OANDA_TOKEN environment variable not set.")
        return

    print(f"Bot started. Trading {', '.join(INSTRUMENTS)} on 1-minute candles.")
    print(f"Account: {ACCOUNT_ID}")
    print(f"Stop loss: {STOP_LOSS_PIPS} pips | Take profit: {TAKE_PROFIT_PIPS} pips")
    print("-" * 40)

    while True:
        try:
            for instrument in INSTRUMENTS:
                trade_instrument(instrument)
            time.sleep(60)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    run()
