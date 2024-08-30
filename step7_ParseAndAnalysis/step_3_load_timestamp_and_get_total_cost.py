import configparser
import json
import logging
import os
import pickle
from datetime import datetime
from pathlib import Path

from my_logger import LoggerSetup

logger = LoggerSetup.setup_logger()
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)

# Constants
ON_DEMAND_COST_PER_HOUR = 0.17
RUNNING_HOURS = 10
DATA_DIR = 'data'
PICKLE_FILE = 'filtered_distributions.pkl'


def find_config_file(filename='conf.ini'):
    """ Find the configuration file in the parent directories of the current file. """
    current_dir = Path(__file__).resolve().parent
    while current_dir != current_dir.parent:
        config_file = current_dir / filename
        if config_file.is_file():
            print(f"Config file found at {config_file}")
            return config_file
        current_dir = current_dir.parent
    return None


# Initialize the parser and read the ini file
config = configparser.ConfigParser()
conf_file_path = find_config_file()
config_path = str(conf_file_path)
config.read(config_path)

# Fetch configurations
INSTANCE_TYPE = config.get('settings', 'instance_type')
NUMBER_OF_INSTANCES = int(config.get('settings', 'number_of_spot_instances'))
print(f"instance_type: {INSTANCE_TYPE}")
print(f"number_of_spot_instances: {NUMBER_OF_INSTANCES}")


def load_distributions(file_path: str) -> dict:
    """Load and return distributions from a pickle file."""
    try:
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    except (FileNotFoundError, pickle.UnpicklingError) as e:
        logger.error(f"Error loading distributions: {str(e)}")
        return {}


def load_all_spot_price_histories(selected_dir_path, directory_name="spot_price_history"):
    """Load all spot price histories from the specified directory."""
    all_spot_price_histories = {}
    time_format = "%Y-%m-%dT%H:%M:%S%z"

    spot_price_history_dir = os.path.join(selected_dir_path, directory_name)
    logger.debug(spot_price_history_dir)

    try:
        for filename in os.listdir(spot_price_history_dir):
            az = filename.split('_')[0]
            filepath = os.path.join(spot_price_history_dir, filename)

            try:
                with open(filepath, 'r') as file:
                    spot_price_history = json.load(file)
                    for entry in spot_price_history:
                        entry["Timestamp"] = datetime.fromisoformat(entry["Timestamp"])
                    all_spot_price_histories[az] = spot_price_history
                    logging.info(f"Data loaded successfully from {filepath}")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logging.info(f"Failed to load data from '{filepath}': {str(e)}")
    except FileNotFoundError:
        logging.info(f"No such directory: '{spot_price_history_dir}'")

    return all_spot_price_histories


def calculate_cost(instance, spot_price_history):
    """Calculate the cost for a given instance based on its spot price history."""
    relevant_prices = [entry for entry in spot_price_history if entry["Timestamp"] <= instance.end_time]
    relevant_prices.sort(key=lambda x: x["Timestamp"])

    total_cost = 0.0
    applicable_price_entry = next(
        (entry for entry in relevant_prices[::-1] if entry["Timestamp"] <= instance.start_time), None)
    if not applicable_price_entry:
        logging.info(f"No applicable price entry found for instance starting at {instance.start_time}")
        return None

    current_time = instance.start_time
    for entry in relevant_prices:
        if entry["Timestamp"] > instance.start_time:
            duration = entry["Timestamp"] - current_time
            cost_per_second = float(applicable_price_entry["SpotPrice"]) / 3600
            total_cost += duration.total_seconds() * cost_per_second
            current_time = entry["Timestamp"]
        applicable_price_entry = entry

    duration = instance.end_time - current_time
    cost_per_second = float(applicable_price_entry["SpotPrice"]) / 3600
    total_cost += duration.total_seconds() * cost_per_second

    return total_cost


def save_results_to_file(distributions, total_cost, directory_path, filename="results.txt"):
    """Save distributions and total cost to a text file."""
    full_path = os.path.join(directory_path, filename)
    try:
        with open(full_path, "a") as file:
            file.write(f"\nTimestamp: {datetime.now()}\n")
            file.write("Distributions (excluding instance data):\n")
            for filetype, content in distributions.items():
                file.write(f"\n{filetype}:\n")
                for key, value in content.items():
                    if key != "instances":
                        file.write(f"  {key}: {value}\n")
                if filetype == 'complete':
                    total_duration = (content['global_max_end_time'] - content[
                        'global_min_start_time']).total_seconds() / 3600
                    file.write(f"\nTotal completion time in hours: {total_duration:.3f}\n")
            file.write(f"\nTotal detailed estimated cost for all instances: ${total_cost}\n")
            file.write(
                f"\nPrice for {NUMBER_OF_INSTANCES} On-Demand Instances for {RUNNING_HOURS} Hours is ${NUMBER_OF_INSTANCES * RUNNING_HOURS * ON_DEMAND_COST_PER_HOUR}\n")
            logging.info(f"Results saved to {full_path}")
    except Exception as e:
        logging.error(f"Failed to write to {full_path}: {str(e)}")


def main():
    selected_dir_path = os.path.join(os.getcwd(), DATA_DIR)
    logger.info(f"Selected directory path: {selected_dir_path}")
    loaded_distributions = load_distributions(os.path.join(selected_dir_path, PICKLE_FILE))

    all_spot_price_histories = load_all_spot_price_histories(selected_dir_path)

    total_all_instances_cost = 0.0
    for filetype, content in loaded_distributions.items():
        for instance_id, instance_data in content["instances"].items():
            az = instance_data.availability_zone
            if az in all_spot_price_histories:
                cost = calculate_cost(instance_data, all_spot_price_histories[az])
                if cost is not None:
                    total_all_instances_cost += cost
                else:
                    logging.info(f"Cannot estimate cost for instance {instance_id} ({az}) due to lack of pricing data.")
            else:
                logging.info(f"No price history available for instance {instance_id} ({az}).")

    logging.info(f"\nTotal estimated cost for all instances: ${total_all_instances_cost:.3f}")
    save_results_to_file(loaded_distributions, total_all_instances_cost, selected_dir_path)


if __name__ == "__main__":
    main()
