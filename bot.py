import time
import oandapyV20
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.instruments as instruments
import pandas as pd
import numpy as np

# --- CONFIG ---
API_TOKEN = "7f014926e6a543bdef99b2a6388e737c-6c3750df280b051f44143f0ddad6897d"
ACCOUNT_ID = "101-001-39455957-001"
ENVIRONMENT = "practice"
INSTRUMENT = "EUR_USD"
UNITS = 10000
CANDLE_COUNT = 50
GRANULARITY = "M5"

client = oandapyV20.API(access_token=API_TOKEN, environment=ENVIRONMENT)

def get_candles():
    params = {"count": CANDLE_COUNT, "granularity": GRANULARITY}
    r = instruments.InstrumentsCandles(INSTRUMENT, params=params)
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

def place_order(units):
    data = {
        "order": {
            "type": "MARKET",
            "instrument": INSTRUMENT,
            "units": str(units),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT"
        }
    }
    r = orders.Orders(ACCOUNT_ID, data=data)
    client.request(r)
    print(f"Order placed: {units} units of {INSTRUMENT}")

def run():
    print("Bot started. Trading EUR/USD on 5-minute candles.")
    print(f"Account: {ACCOUNT_ID}")
    print("-" * 40)

    while True:
        try:
            closes = get_candles()
            current_rsi = rsi(closes)
            current_macd = macd(closes)

            print(f"RSI: {current_rsi:.2f} | MACD: {current_macd:.6f}")

            open_trades = get_open_trades()

            if current_rsi < 30 and current_macd > 0:
                if not open_trades:
                    print("Signal: BUY")
                    place_order(UNITS)
                elif open_trades[0]["currentUnits"].startswith("-"):
                    close_all_trades()
                    place_order(UNITS)

            elif current_rsi > 70 and current_macd < 0:
                if not open_trades:
                    print("Signal: SELL")
                    place_order(-UNITS)
                elif not open_trades[0]["currentUnits"].startswith("-"):
                    close_all_trades()
                    place_order(-UNITS)

            else:
                print("No signal — holding")

            time.sleep(30)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    run()
