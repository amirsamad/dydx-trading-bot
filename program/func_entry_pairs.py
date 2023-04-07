import datetime
from constants import ZSCORE_THRESH, USD_PER_TRADE, USD_MIN_COLLATERAL
from func_utils import format_number
from func_public import get_candles_recent
from func_public import get_candles_latest
from func_cointegration import calculate_zscore
from func_private import is_open_positions
from func_bot_agent import BotAgent
import pandas as pd
import json

from pprint import pprint

from func_utils import call_client
from func_utils import get_average_price


# Open positions
def open_positions(client):

  """
    Manage finding triggers for trade entry
    Store trades for managing later on on exit function
  """

  # Load cointegrated pairs
  df = pd.read_csv("cointegrated_pairs.csv")

  # Get markets from referencing of min order size, tick size etc
  markets = call_client(client.public.get_markets).data

  # Initialize container for BotAgent results
  bot_agents = []

  # Opening JSON file
  try:
    open_positions_file = open("bot_agents.json")
    open_positions_dict = json.load(open_positions_file)
    for p in open_positions_dict:
      bot_agents.append(p)
  except:
    bot_agents = []
  
  # Find ZScore triggers
  for index, row in df.iterrows():

    # Extract variables
    base_market = row["base_market"]
    quote_market = row["quote_market"]
    hedge_ratio = row["hedge_ratio"]
    half_life = row["half_life"]
    spread_mean = row["spread_mean"]
    spread_std = row["spread_std"]


    # Get prices
    price_1 = get_candles_latest(client, base_market)
    price_2 = get_candles_latest(client, quote_market)
    #series_1 = get_candles_recent(client, base_market)
    #series_2 = get_candles_recent(client, quote_market)

    # Get ZScore
    if True:
      spread = price_1 - (hedge_ratio * price_2)
      z_score = (spread - spread_mean) / spread_std

    #if len(series_1) > 0 and len(series_1) == len(series_2):
    #  spread = series_1 - (hedge_ratio * series_2)
    #  z_score = calculate_zscore(spread).values.tolist()[-1]

      #if z_score > 0: z_score = 1.8
      #else: z_score = -1.8
      ###
      # THIS IS WHERE WE WANT TO SIMULATE TRADES - AMIR
      ###
      #if base_market == "SNX-USD" and quote_market == "XTZ-USD":
      #  print(f"establishing debug trade for {base_market} and {quote_market}")
      #  # negative to buy base market 1
      #  z_score = 1.6
      #else:
      #  z_score = 0.5

      # Establish if potential trade
      if abs(z_score) >= ZSCORE_THRESH:

        # Ensure like-for-like not already open (diversify trading)
        is_base_open = is_open_positions(client, base_market)
        is_quote_open = is_open_positions(client, quote_market)

        # Place trade
        if not is_base_open and not is_quote_open:

          # Determine side
          base_side = "BUY" if z_score < 0 else "SELL"
          quote_side = "BUY" if z_score > 0 else "SELL"

          # Get acceptable price in string format with correct number of decimals
          base_price = series_1[-1]
          quote_price = series_2[-1]
          accept_base_price = float(base_price) * 1.01 if z_score < 0 else float(base_price) * 0.99
          accept_quote_price = float(quote_price) * 1.01 if z_score > 0 else float(quote_price) * 0.99
          failsafe_base_price = float(base_price) * 0.05 if z_score < 0 else float(base_price) * 1.7
          base_tick_size = markets["markets"][base_market]["tickSize"]
          quote_tick_size = markets["markets"][quote_market]["tickSize"]

          # Format prices
          accept_base_price = format_number(accept_base_price, base_tick_size)
          accept_quote_price = format_number(accept_quote_price, quote_tick_size)
          accept_failsafe_base_price = format_number(failsafe_base_price, base_tick_size)

          # Get size
          base_quantity = 1 / base_price * USD_PER_TRADE
          quote_quantity = 1 / quote_price * USD_PER_TRADE
          base_step_size = markets["markets"][base_market]["stepSize"]
          quote_step_size = markets["markets"][quote_market]["stepSize"]

          # Format sizes
          # Amir - fixed this for step sizes > 1
          base_size = format_number(base_quantity, base_step_size) if float(base_step_size) <= 1 else str(round(base_quantity, -(int(int(base_step_size)/10))))
          quote_size = format_number(quote_quantity, quote_step_size) if float(quote_step_size) <= 1 else str(round(quote_quantity, -(int(int(quote_step_size)/10))))

          # Ensure size
          base_min_order_size = markets["markets"][base_market]["minOrderSize"]
          quote_min_order_size = markets["markets"][quote_market]["minOrderSize"]
          check_base = float(base_quantity) > float(base_min_order_size)
          check_quote = float(quote_quantity) > float(quote_min_order_size)

          # If checks pass, place trades
          if check_base and check_quote:

            # Check account balance
            account = call_client(client.private.get_account)
            free_collateral = float(account.data["account"]["freeCollateral"])
            #print(f"Balance: {free_collateral} and minimum at {USD_MIN_COLLATERAL}")

            # Guard: Ensure collateral
            if free_collateral < USD_MIN_COLLATERAL:
              break

            # Create Bot Agent
            bot_agent = BotAgent(
              client,
              market_1=base_market,
              market_2=quote_market,
              base_side=base_side,
              base_size=base_size,
              base_price=accept_base_price,
              quote_side=quote_side,
              quote_size=quote_size,
              quote_price=accept_quote_price,
              accept_failsafe_base_price=accept_failsafe_base_price,
              z_score=z_score,
              half_life=half_life,
              hedge_ratio=hedge_ratio,
              spread_mean=spread_mean,
              spread_std=spread_std
            )

            # Open Trades
            bot_open_dict = bot_agent.open_trades()
            #pprint("Result from opening trade: ", bot_open_dict)

            # Guard: Handle failure
            if bot_open_dict["pair_status"] == "ERROR":
              #print("Error trying to open trade")
              continue

            # Handle success in opening trades
            if bot_open_dict["pair_status"] == "LIVE":

              # Check new account balance
              account = call_client(client.private.get_account)
              free_collateral_after = float(account.data["account"]["freeCollateral"])

              # Get actual price of trade vs. requested price
              
              hedge_ratio = bot_open_dict["hedge_ratio"]
              z_score = bot_open_dict["z_score"]
              half_life = bot_open_dict["half_life"]
              spread_mean = bot_open_dict["spread_mean"]
              spread_std = bot_open_dict["spread_std"]

              market_1 = bot_open_dict["market_1"]
              order_id_m1 = bot_open_dict["order_id_m1"]
              order_m1_size = bot_open_dict["order_m1_size"]
              order_m1_side = bot_open_dict["order_m1_side"]
              order_time_m1 = bot_open_dict["order_time_m1"]
              fill_1 = call_client(client.private.get_fills, market=market_1)
              actual_price_m1 = get_average_price(fill_1, market_1, order_id_m1, order_m1_size)
              

              market_2 = bot_open_dict["market_2"]
              order_id_m2 = bot_open_dict["order_id_m2"]
              order_m2_size = bot_open_dict["order_m2_size"]
              order_m2_side = bot_open_dict["order_m2_side"]
              order_time_m2 = bot_open_dict["order_time_m2"]
              fill_2 = call_client(client.private.get_fills, market=market_2)
              actual_price_m2 = get_average_price(fill_2, market_2, order_id_m2, order_m2_size)

              print(f"[{datetime.datetime.now():%H:%M:%S %d-%m-%y}] OPEN {market_1}/{market_2}, {order_m1_side} {market_1}:{actual_price_m1} ({base_price}, {accept_base_price}), {order_m2_side} {market_2}:{actual_price_m2} ({quote_price}, {accept_quote_price}) Zscore: {round(z_score, 2)}, hlife: {round(half_life, 1)}, hratio: {round(hedge_ratio, 3)}, mean: {round(spread_mean, 2)}, stdev: {round(spread_std, 2)}, amount: {round(free_collateral,2) - round(free_collateral_after,2)}", flush=True)
              #print(f"[{datetime.datetime.now():%H:%M:%S %d-%m-%y}] OPEN --- {order_m1_side} {order_m1_size} units of {market_1} at {actual_price_m1} ({base_price}, {accept_base_price}) ", flush=True)
              #print(f"[{datetime.datetime.now():%H:%M:%S %d-%m-%y}] OPEN --- {order_m2_side} {order_m2_size} units of {market_2} at {actual_price_m2} ({quote_price}, {accept_quote_price}) ", flush=True)

              # Append to list of bot agents
              bot_agents.append(bot_open_dict)
              del(bot_open_dict)

              # Confirm live status in print
              #print("Trade status: Live") 
              #print("---")

  # Save agents
  #print(f"Success: Manage open trades checked")
  if len(bot_agents) > 0:
    with open("bot_agents.json", "w") as f:
      json.dump(bot_agents, f)
