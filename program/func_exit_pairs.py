import datetime
from constants import CLOSE_AT_ZSCORE_CROSS
from func_utils import format_number
from func_utils import call_client
from func_public import get_candles_recent
from func_public import get_candles_latest
from func_cointegration import calculate_zscore
from func_private import place_market_order
from func_connections import connect_dydx
import json
import time

from pprint import pprint

from func_utils import get_average_price
from func_messaging import send_message



# Manage trade exits
def manage_trade_exits(client):

  """
    Manage exiting open positions
    Based upon criteria set in constants
  """

  # Initialize saving output
  save_output = []

  # Opening JSON file
  try:
    open_positions_file = open("bot_agents.json")
    open_positions_dict = json.load(open_positions_file)
  except:
    return "complete"

  # Guard: Exit if no open positions in file
  if len(open_positions_dict) < 1:
    return "complete"

  # Get all open positions per trading platform
  #exchange_pos = client.private.get_positions(status="OPEN")
  exchange_pos = call_client(client.private.get_positions, status="OPEN")
  all_exc_pos = exchange_pos.data["positions"]
  markets_live = []
  for p in all_exc_pos:
    markets_live.append(p["market"])

  # Protect API
  time.sleep(0.5)

  # Check all saved positions match order record
  # Exit trade according to any exit trade rules
  for position in open_positions_dict:

    # Initialize is_close trigger
    is_close = False

    # Extract position matching information from file - market 1
    position_market_m1 = position["market_1"]
    position_size_m1 = position["order_m1_size"]
    position_side_m1 = position["order_m1_side"]

    # Extract position matching information from file - market 2
    position_market_m2 = position["market_2"]
    position_size_m2 = position["order_m2_size"]
    position_side_m2 = position["order_m2_side"]

    # Protect API
    time.sleep(0.5)

    # Get order info m1 per exchange
    #order_m1 = client.private.get_order_by_id(position["order_id_m1"])
    order_m1 = call_client(client.private.get_order_by_id, position["order_id_m1"])
    order_market_m1 = order_m1.data["order"]["market"]
    order_size_m1 = order_m1.data["order"]["size"]
    order_side_m1 = order_m1.data["order"]["side"]
    order_price_m1 = order_m1.data["order"]["price"]

    # Protect API
    time.sleep(0.5)

    # Get order info m2 per exchange
    #order_m2 = client.private.get_order_by_id(position["order_id_m2"])
    order_m2 = call_client(client.private.get_order_by_id, position["order_id_m2"])
    order_market_m2 = order_m2.data["order"]["market"]
    order_size_m2 = order_m2.data["order"]["size"]
    order_side_m2 = order_m2.data["order"]["side"]
    order_price_m2 = order_m2.data["order"]["price"]


    # Perform matching checks
    check_m1 = position_market_m1 == order_market_m1 and float(position_size_m1) == float(order_size_m1) and position_side_m1 == order_side_m1
    check_m2 = position_market_m2 == order_market_m2 and float(position_size_m2) == float(order_size_m2) and position_side_m2 == order_side_m2
    check_live = position_market_m1 in markets_live and position_market_m2 in markets_live

    # Guard: If not all match exit with error
    if not check_m1 or not check_m2 or not check_live:
      if not check_m1: print("check_m1")
      if not check_m2:
        print("check_m2")
        print(position_market_m2)
        print(order_market_m2)
        print(position_size_m2)
        print(order_size_m2)
        print(position_side_m2)
        print(order_side_m2)
      if not check_live: print("check_live")
      print(f"Warning: Not all open positions match exchange records for {position_market_m1} and {position_market_m2}", flush=True)
      continue

    # Get prices
    price_1 = get_candles_latest(client, position_market_m1)
    price_2 = get_candles_latest(client, position_market_m2)
    #series_1 = get_candles_recent(client, position_market_m1)
    #time.sleep(0.2)
    #series_2 = get_candles_recent(client, position_market_m2)
    #time.sleep(0.2)

    # Get markets for reference of tick size
    markets = call_client(client.public.get_markets).data

    # Protect API
    time.sleep(0.2)

    # Trigger close based on Z-Score
    if CLOSE_AT_ZSCORE_CROSS:

      # Initialize z_scores\
      half_life = position["half_life"]
      hedge_ratio = position["hedge_ratio"]
      z_score_traded = position["z_score"]
      spread_mean = position["spread_mean"]
      spread_std = position["spread_std"]
      #if len(series_1) > 0 and len(series_1) == len(series_2):
        #spread = series_1 - (hedge_ratio * series_2)

      spread = price_1 - (hedge_ratio * price_2)
      z_score_current = (spread - spread_mean) / spread_std
      #z_score_current = calculate_zscore(spread).values.tolist()[-1]

      
      #if position_market_m1 == "XTZ-USD" and position_market_m2 == "NEAR-USD":
      #  is_close = True

      # Determine trigger
      z_score_level_check = abs(z_score_current) >= abs(z_score_traded)
      if z_score_level_check:
        z_score_cross_check = (z_score_current < 0 and z_score_traded > 0) or (z_score_current > 0 and z_score_traded < 0)

        # Close trade
        if z_score_cross_check:

          # Initiate close trigger
          is_close = True

    ###
    # Add any other close logic you want here
    # Trigger is_close
    ###

    # Close positions if triggered
    if is_close:
      account = call_client(client.private.get_account)
      free_collateral = float(account.data["account"]["freeCollateral"])

      # Determine side - m1
      side_m1 = "SELL"
      if position_side_m1 == "SELL":
        side_m1 = "BUY"

      # Determine side - m2
      side_m2 = "SELL"
      if position_side_m2 == "SELL":
        side_m2 = "BUY"

      # Get and format Price
      #price_m1 = float(series_1[-1])
      #price_m2 = float(series_2[-1])
      price_m1 = price_1
      price_m2 = price_2
      accept_price_m1 = price_m1 * 1.05 if side_m1 == "BUY" else price_m1 * 0.95
      accept_price_m2 = price_m2 * 1.05 if side_m2 == "BUY" else price_m2 * 0.95
      tick_size_m1 = markets["markets"][position_market_m1]["tickSize"]
      tick_size_m2 = markets["markets"][position_market_m2]["tickSize"]
      accept_price_m1 = format_number(accept_price_m1, tick_size_m1)
      accept_price_m2 = format_number(accept_price_m2, tick_size_m2)

      # Close positions
      try:

        # Close position for market 1
        #print(">>> Closing market 1 <<<")
        #print(f"Closing position for {position_market_m1}")

        close_order_m1 = place_market_order(
          client,
          market=position_market_m1,
          side=side_m1,
          size=position_size_m1,
          price=accept_price_m1,
          reduce_only=True,
        )

        order_id_m1 = close_order_m1["order"]["id"]
        #print(close_order_m1["order"]["id"])
        #print(">>> Closing <<<")

        # Protect API
        time.sleep(1)

        # Close position for market 2
        #print(">>> Closing market 2 <<<")
        #print(f"Closing position for {position_market_m2}")

        close_order_m2 = place_market_order(
          client,
          market=position_market_m2,
          side=side_m2,
          size=position_size_m2,
          price=accept_price_m2,
          reduce_only=True,
        )

        order_id_m2 = close_order_m2["order"]["id"]
        #print(close_order_m2["order"]["id"])
        #print(">>> Closing <<<")

      except Exception as e:
        print(f"Exit failed for {position_market_m1} with {position_market_m2}", flush=True)
        save_output.append(position)
      else:
        # Successfully closed positions
        # Check new account balance
        account = call_client(client.private.get_account)
        free_collateral_after = float(account.data["account"]["freeCollateral"])

        # Get actual price of trade vs. requested price
        
        fill_1 = call_client(client.private.get_fills, market=position_market_m1)
        actual_price_m1 = get_average_price(fill_1, position_market_m1, order_id_m1, position_size_m1)
        

        #market_2 = bot_open_dict["market_2"]
        #order_id_m2 = bot_open_dict["order_id_m2"]
        #order_m2_size = bot_open_dict["order_m2_size"]
        #order_m2_side = bot_open_dict["order_m2_side"]
        #order_time_m2 = bot_open_dict["order_time_m2"]
        fill_2 = call_client(client.private.get_fills, market=position_market_m2)
        actual_price_m2 = get_average_price(fill_2, position_market_m2, order_id_m2, position_size_m2)

        try:
          print(f"[{datetime.datetime.now():%H:%M:%S %d-%m-%y}] CLOSE {position_market_m1}/{position_market_m2}, {position_side_m2} {position_market_m1} at {actual_price_m1} ({order_price_m1}), {position_side_m1} {position_market_m2} at {actual_price_m2} ({order_price_m2}) New Zscore: {round(float(z_score_current), 2)} ({round(float(z_score_traded), 2)}), hlife: {round(float(half_life), 1)}, hratio: {round(float(hedge_ratio), 3)}, mean: {round(spread_mean, 2)}, stdev: {round(spread_std, 2)}, amount: {round(free_collateral_after - free_collateral,2)}", flush=True)
          send_message(f"CLOSE {position_market_m1}/{position_market_m2}, {position_side_m2} {position_market_m1} at {actual_price_m1} ({order_price_m1}), {position_side_m1} {position_market_m2} at {actual_price_m2} ({order_price_m2}) New Zscore: {round(float(z_score_current), 2)} ({round(float(z_score_traded), 2)}), amount: {round(free_collateral_after - free_collateral,2)}")
          #print(f"[{datetime.datetime.now():%H:%M:%S %d-%m-%y}] CLOSE --- {position_side_m1} {position_size_m1} units of {position_market_m1} at {actual_price_m1} ({order_price_m1})", flush=True)
          #print(f"[{datetime.datetime.now():%H:%M:%S %d-%m-%y}] CLOSE --- {position_side_m2} {position_size_m2} units of {position_market_m2} at {actual_price_m2} ({order_price_m2})", flush=True)

          #send_message(f"CLOSE --- {position_side_m1} {position_size_m1} units of {position_market_m1} at {actual_price_m1} ({order_price_m1})")
          #send_message(f"CLOSE --- {position_side_m2} {position_size_m2} units of {position_market_m2} at {actual_price_m2} ({order_price_m2})")
        except Exception as e:
          print(f"got exception of type {type(e)} of: {e}", flush=True)


    # Keep record if items and save
    else:
      save_output.append(position)

  # Save remaining items
  #print(f"{len(save_output)} Items remaining. Saving file...")
  with open("bot_agents.json", "w") as f:
    json.dump(save_output, f)
