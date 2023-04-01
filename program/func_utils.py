from datetime import datetime, timedelta
from time import sleep
from func_messaging import send_message

def call_client(clientFunc, *arg, **kwargs):
  #close connection to test
  #client
  for i in range(0,2):
    try:
      retcode = clientFunc(*arg, **kwargs)

    except ConnectionError:
      print(f"Connection Error calling function {clientFunc}")
      sleep(0.5)
      continue
    except Exception as e:
      print(f"Error calling function {clientFunc}, got exception of type {type(e)} of: {e}.. retrying")
      sleep(0.5)
      continue
    else:
      return retcode
    
  # Couldn't connect after all retries
  print("Catastrophic failure: Couldn't connect after retries")
  send_message("Catastrophic failure: Couldn't connect after retries")
  exit(1)

# Format number
def format_number(curr_num, match_num):

  """
    Give current number an example of number with decimals desired
    Function will return the correctly formatted string
  """

  curr_num_string = f"{curr_num}"
  match_num_string = f"{match_num}"

  if "." in match_num_string:
    match_decimals = len(match_num_string.split(".")[1])
    curr_num_string = f"{curr_num:.{match_decimals}f}"
    curr_num_string = curr_num_string[:]
    return curr_num_string
  else:
    return f"{int(curr_num)}"


# Format time
def format_time(timestamp):
  return timestamp.replace(microsecond=0).isoformat()


# Get ISO Times
def get_ISO_times():

  # Get timestamps
  date_start_0 = datetime.now()
  date_start_1 = date_start_0 - timedelta(hours=100)
  date_start_2 = date_start_1 - timedelta(hours=100)
  date_start_3 = date_start_2 - timedelta(hours=100)
  date_start_4 = date_start_3 - timedelta(hours=100)

  # Format datetimes
  times_dict = {
    "range_1": {
      "from_iso": format_time(date_start_1),
      "to_iso": format_time(date_start_0),
    },
    "range_2": {
      "from_iso": format_time(date_start_2),
      "to_iso": format_time(date_start_1),
    },
    "range_3": {
      "from_iso": format_time(date_start_3),
      "to_iso": format_time(date_start_2),
    },
    "range_4": {
      "from_iso": format_time(date_start_4),
      "to_iso": format_time(date_start_3),
    },
  }

  # Return result
  return times_dict
