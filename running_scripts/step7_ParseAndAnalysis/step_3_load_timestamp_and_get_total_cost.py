import json
import os
import pickle
from datetime import datetime

INSTANCE_TYPE = 'm5.xlarge'
ON_DEMAND_COST_PER_HOUR = 0.17
RUNNING_HOURS = 10
NUMBER_OF_INSTANCES = 40

from directory_selector import select_subdirectory, load_data
import logging
from my_logger import LoggerSetup

logger = LoggerSetup.setup_logger()
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)


def load_distributions(file_path: str) -> dict:
    """Load and return distributions from a pickle file."""
    try:
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        logging.error(f"No such file: '{file_path}'")
        return {}
    except pickle.UnpicklingError:
        logging.error("Could not unpickle file")
        return {}


def load_all_spot_price_histories(selected_dir_path, directory_name="spot_price_history"):
    """
    Load all spot price histories from the specified directory.

    Parameters:
        directory_name (str): The directory where the spot price history data is saved.

    Returns:
        dict: A dictionary where keys are availability zones and values are spot price history data.
    """
    all_spot_price_histories = {}
    time_format = "%Y-%m-%dT%H:%M:%S%z"

    if selected_dir_path is None:
        logging.warning("No directory selected.")
        return all_spot_price_histories

    spot_price_history_dir = os.path.join(selected_dir_path, 'spot_price_history')
    logger.debug(spot_price_history_dir)
    try:
        for filename in os.listdir(spot_price_history_dir):
            logger.debug(filename)
            # Extract the availability zone from the filename using string slicing or regex
            az = filename.split('_')[0]

            filepath = os.path.join(selected_dir_path, directory_name, filename)

            try:
                with open(filepath, 'r') as file:
                    spot_price_history = json.load(file)

                    # Convert timestamps to datetime objects
                    for entry in spot_price_history:
                        # entry["Timestamp"] = datetime.strptime(entry["Timestamp"], time_format)
                        entry["Timestamp"] = datetime.fromisoformat(entry["Timestamp"])

                    # Add to the dictionary
                    all_spot_price_histories[az] = spot_price_history

                    # Add to the dictionary
                    # all_spot_price_histories[az] = spot_price_history

                    logging.info(f"Data loaded successfully from {filepath}")

            except json.JSONDecodeError:
                logging.info(f"Failed to decode JSON data from file: '{filepath}'")
            except FileNotFoundError:
                logging.info(f"No such file: '{filepath}'")

    except FileNotFoundError:
        logging.info(f"No such directory: '{directory_name}'")

    return all_spot_price_histories


def calculate_cost(instance, spot_price_history):
    # Filter out any price entries that are after the instance's end time
    relevant_prices = [entry for entry in spot_price_history if entry["Timestamp"] <= instance.end_time]
    # logger.debug(f"Relevant prices:{relevant_prices}")
    # Sort the price entries by timestamp
    relevant_prices = sorted(relevant_prices, key=lambda x: x["Timestamp"])
    # logger.debug(f"Relevant prices:{str(relevant_prices)}")

    # Sort the price entries by timestamp
    total_cost = 0.0

    # Find the first price entry that is before the instance's start time
    applicable_price_entry = next(
        (
            entry
            for entry in relevant_prices[::-1]
            if entry["Timestamp"] <= instance.start_time
        ),
        None,
    )
    # If no applicable price entry was found, we might not be able to calculate the cost
    if applicable_price_entry is None:
        logging.info(f"No applicable price entry found for instance starting at {instance.start_time}")
        return None

    # Iterate through the price entries
    current_time = instance.start_time
    for entry in relevant_prices:
        # If the price entry is after the current time, calculate the cost
        if entry["Timestamp"] > instance.start_time:
            duration = entry["Timestamp"] - current_time
            cost_per_second = float(applicable_price_entry["SpotPrice"]) / 3600
            cost_for_duration = duration.total_seconds() * cost_per_second
            total_cost += cost_for_duration
            current_time = entry["Timestamp"]

        # Update the applicable price entry for the next iteration
        applicable_price_entry = entry

    # Add the cost from the last price change to the instance's end time
    duration = instance.end_time - current_time
    cost_per_second = float(applicable_price_entry["SpotPrice"]) / 3600
    cost_for_duration = duration.total_seconds() * cost_per_second
    total_cost += cost_for_duration

    return total_cost


def save_results_to_file(distributions, total_cost, directory_path, filename="results.txt"):
    """
    Save distributions (excluding instance data) and total cost to a text file.

    Parameters:
        distributions (dict): The loaded distributions data.
        total_cost (float): The total cost calculated.
        directory_path (str): The path to the directory where the results should be saved.
        filename (str): The name of the file to save results. Default is 'results.txt'.
    """
    # Construct the full path to the file
    full_path = os.path.join(directory_path, filename)

    try:
        with open(full_path, "a") as file:
            file.write(f"\nTimestamp: {datetime.now()}\n")
            file.write("Distributions (excluding instance data):\n")

            # Write distributions info excluding instances
            for filetype, content in distributions.items():
                file.write(f"\n{filetype}:\n")

                for key, value in content.items():
                    if key != "instances":
                        file.write(f"  {key}: {value}\n")

                if filetype == 'complete':
                    total_duration = (content['global_max_end_time'] - content[
                        'global_min_start_time']).total_seconds() / 3600  # convert seconds to hours
                    file.write(f"\nTotal completion time in hours: {total_duration:.3f}\n")

            # Write total cost
            file.write(f"\nTotal detailed estimated cost for all instances: ${total_cost}\n")
            # assuming you have defined NUMBER_OF_INSTANCES, RUNNING_HOURS, ON_DEMAND_COST_PER_HOUR
            file.write(f"\nPrice for Number of {NUMBER_OF_INSTANCES} On-Demand Instances for {RUNNING_HOURS} Hours is "
                       f"${NUMBER_OF_INSTANCES * RUNNING_HOURS * ON_DEMAND_COST_PER_HOUR}\n")

            logging.info(f"Results saved to {full_path}")

    except Exception as e:
        logging.error(f"Failed to write to {full_path}: {str(e)}")


def main():
    BaseDir = os.getcwd()
    base_dir = BaseDir
    target_name = 'data'  # The target directory name to match against
    selected_dir_path = select_subdirectory(base_dir, target_name)
    logger.info(f"Selected directory path: {selected_dir_path}")

    print("Which file do you want to use?")
    print("1. filtered_distributions.pkl")
    print("2. filtered_distributions_with_filled_complete_bucket.pkl")
    choice = input("Enter the number (1 or 2): ").strip()

    # Determine the file based on user input
    if choice == '1':
        file_to_use = 'filtered_distributions.pkl'
    elif choice == '2':
        file_to_use = 'filtered_distributions_with_filled_complete_bucket.pkl'
    else:
        print("Invalid choice.")
        exit()  # Exit the script

    print(f"You've chosen to use: {file_to_use}")

    loaded_distributions = load_data(os.path.join(selected_dir_path, file_to_use))
    # logger.debug(f"Loaded distributions: {loaded_distributions}")

    all_spot_price_histories = load_all_spot_price_histories(selected_dir_path)
    # logger.debug(all_spot_price_histories)

    # Initialize a variable to accumulate total cost for all instances.
    total_all_instances_cost = 0.0

    # Assuming loaded_distributions has a structure like: {'complete': {'instances': {'i-12345': instance_obj}}}
    for filetype, content in loaded_distributions.items():
        for instance_id, instance_data in content["instances"].items():
            az = instance_data.availability_zone
            if az in all_spot_price_histories:
                spot_price_history = all_spot_price_histories[az]
                cost = calculate_cost(instance_data, spot_price_history)

                if cost is not None:

                    # Add the cost to total_all_instances_cost.
                    total_all_instances_cost += cost
                    # logging.debug(f"Estimated cost for instance {instance_id} ({az}): ${cost}")
                else:
                    logging.info(f"Cannot estimate cost for instance {instance_id} ({az}) due to lack of pricing data.")
            else:
                logging.info(f"No price history available for instance {instance_id} ({az}).")

    # logging.info the total cost for all instances.
    logging.info(
        f"\nTotal estimated cost for all instances: ${total_all_instances_cost}")  # Print cost with 3 decimal points
    save_results_to_file(loaded_distributions, total_all_instances_cost, selected_dir_path)


if __name__ == "__main__":
    main()
