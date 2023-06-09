from func_private import place_market_order, check_order_status
from datetime import datetime, timedelta
from func_messaging import send_message
import time

from pprint import pprint

from func_utils import call_client


# Class: Agent for managing opening and checking trades
class BotAgent:

  """
    Primary function of BotAgent handles opening and checking order status
  """

  # Initialize class
  def __init__(
    self,
    client,
    market_1,
    market_2,
    base_side,
    base_size,
    base_price,
    quote_side,
    quote_size,
    quote_price,
    accept_failsafe_base_price,
    z_score,
    half_life,
    hedge_ratio,
    spread_mean,
    spread_std,
  ):

    # Initialize class variables
    self.client = client
    self.market_1 = market_1
    self.market_2 = market_2
    self.base_side = base_side
    self.base_size = base_size
    self.base_price = base_price
    self.quote_side = quote_side
    self.quote_size = quote_size
    self.quote_price = quote_price
    self.accept_failsafe_base_price = accept_failsafe_base_price
    self.z_score = z_score
    self.half_life = half_life
    self.hedge_ratio = hedge_ratio
    self.spread_mean = spread_mean
    self.spread_std = spread_std

    # Initialze output variable
    # Pair status options are FAILED, LIVE, CLOSE, ERROR
    self.order_dict = {
      "market_1": market_1,
      "market_2": market_2,
      "hedge_ratio": hedge_ratio,
      "z_score": z_score,
      "half_life": half_life,
      "spread_mean": spread_mean,
      "spread_std": spread_std,
      "order_id_m1": "",
      "order_m1_size": base_size,
      "order_m1_side": base_side,
      "order_time_m1": "",
      "order_id_m2": "",
      "order_m2_size": quote_size,
      "order_m2_side": quote_side,
      "order_time_m2": "",
      "pair_status": "",
      "comments": "",
    }

  # Check order status by id
  def check_order_status_by_id(self, order_id):

    # Allow time to process
    time.sleep(2)

    # Check order status
    order_status = check_order_status(self.client, order_id)

    # Guard: If order cancelled move onto next Pair
    if order_status == "CANCELED":
      print(f"{self.market_1} vs {self.market_2} - Order cancelled...", flush=True)
      self.order_dict["pair_status"] = "FAILED"
      return "failed"

    # Guard: If order not filled wait until order expiration
    if order_status != "FILLED":
      time.sleep(15)
      order_status = check_order_status(self.client, order_id)

      # Guard: If order cancelled move onto next Pair
      if order_status == "CANCELED":
        print(f"{self.market_1} vs {self.market_2} - Order cancelled...", flush=True)
        self.order_dict["pair_status"] = "FAILED"
        return "failed"

      # Guard: If not filled, cancel order
      if order_status != "FILLED":
        call_client(self.client.private.cancel_order, order_id=order_id)
        self.order_dict["pair_status"] = "ERROR"
        print(f"{self.market_1} vs {self.market_2} - Order error...", flush=True)
        return "error"

    # Return live
    return "live"

  # Open trades
  def open_trades(self):

    # Print status
    #print("---")
    #print(f"{self.market_1}: Placing first order...")
    #print(f"Side: {self.base_side}, Size: {self.base_size}, Price: {self.base_price}")
    #print("---")

    # Place Base Order
    try:
      base_order = place_market_order(
        self.client,
        market=self.market_1,
        side=self.base_side,
        size=self.base_size,
        price=self.base_price,
        reduce_only=False
      )

      # Store the order id
      self.order_dict["order_id_m1"] = base_order["order"]["id"]
      self.order_dict["order_time_m1"] = datetime.now().isoformat()
    except Exception as e:
      print(f"Error placing first order: Market: {self.market_1}, Side: {self.base_side}, Size: {self.base_size}, price: {self.base_price}, Error: {e}", flush=True)
      #send_message(f"Error placing first order: Market: {self.market_1}, Side: {self.base_side}, Size: {self.base_size}, price: {self.base_price}, Error: {e}")
      self.order_dict["pair_status"] = "ERROR"
      self.order_dict["comments"] = f"Market 1 {self.market_1}: , {e}"
      return self.order_dict

    # Ensure order is live before processing
    order_status_m1 = self.check_order_status_by_id(self.order_dict["order_id_m1"])

    # Guard: Aborder if order failed
    if order_status_m1 != "live":

      self.order_dict["pair_status"] = "ERROR"
      self.order_dict["comments"] = f"{self.market_1} failed to fill"
      return self.order_dict

    # Print status - opening second order
    #print("---")
    #print(f"{self.market_2}: Placing second order...")
    #print(f"Side: {self.quote_side}, Size: {self.quote_size}, Price: {self.quote_price}")
    #print("---")

    # Place Quote Order
    try:
      order_status_m2 = "attempting"
      quote_order = place_market_order(
        self.client,
        market=self.market_2,
        side=self.quote_side,
        size=self.quote_size,
        price=self.quote_price,
        reduce_only=False
      )

      # Store the order id
      self.order_dict["order_id_m2"] = quote_order["order"]["id"]
      self.order_dict["order_time_m2"] = datetime.now().isoformat()


      # Ensure order is live before processing
      order_status_m2 = self.check_order_status_by_id(self.order_dict["order_id_m2"])

      if order_status_m2 == "live":
        self.order_dict["pair_status"] = "LIVE"
        return self.order_dict

    # Guard: Aborder if order failed
      else:
        raise Exception("Did not get live status from second trade")
        #self.order_dict["pair_status"] = "ERROR"
        #self.order_dict["comments"] = f"{self.market_1} failed to fill"

    except Exception as e:
      print(f"Error placing second order: Market: {self.market_2}, Side: {self.quote_side}, Size: {self.quote_size}, price: {self.quote_price}, Error: {e}", flush=True)
      #send_message(f"Error placing second order: Market: {self.market_2}, Side: {self.quote_side}, Size: {self.quote_size}, price: {self.quote_price}, Error: {e}")
      self.order_dict["pair_status"] = "ERROR"
      self.order_dict["comments"] = f"Market 2 {self.market_2}: , {e}"

      # Close order 1:
      try:
        print(f"Could not place second order, return status: {order_status_m2}, attempting to close first order", flush=True)
        close_order = place_market_order(
          self.client,
          market=self.market_1,
          side=self.quote_side,
          size=self.base_size,
          price=self.accept_failsafe_base_price,
          reduce_only=True
        )

        # Ensure order is live before proceeding
        time.sleep(2)
        order_status_close_order = check_order_status(self.client, close_order["order"]["id"])
        if order_status_close_order != "FILLED":
          print("ABORT PROGRAM", flush=True)
          print("Unexpected Error", flush=True)
          print(order_status_close_order, flush=True)

          # Send Message
          send_message("Failed to execute. Code red. Error code: 100")

          # ABORT
          exit(1)
        else:
          self.order_dict["pair_status"] = "ERROR"
          return self.order_dict
      except Exception as e:
        print(f"Error reversing first order: Market: {self.market_1}, Side: {self.base_side}, Size: {self.base_size}, price: {self.base_price}, Error: {e}", flush=True)
        #send_message(f"Error placing second order: Market: {self.market_1}, Side: {self.base_side}, Size: {self.base_size}, price: {self.base_price}, Error: {e}")
        self.order_dict["pair_status"] = "ERROR"
        self.order_dict["comments"] = f"Close Market 1 {self.market_1}: , {e}"
        print("ABORT PROGRAM", flush=True)
        print("Unexpected Error", flush=True)
        print(order_status_close_order, flush=True)

        # Send Message
        send_message("Failed to execute. Code red. Error code: 101")

        # ABORT
        exit(1)

    # Return success result
    else:
      self.order_dict["pair_status"] = "LIVE"
      return self.order_dict
      