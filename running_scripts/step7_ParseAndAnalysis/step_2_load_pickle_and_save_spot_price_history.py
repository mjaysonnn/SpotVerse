"""
This script is responsible for loading the original distributions, removing old interruptions, updating times, zones,
and saving the filtered distributions. It also retrieves spot price history for each availability zone \
and stores it in a JSON file.
"""
import configparser
import copy
import json
import logging
import os
import pickle
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import boto3

from my_logger import LoggerSetup

logger = LoggerSetup.setup_logger()
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)


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
TARGET_NUMBER_OF_INSTANCES = int(config.get('settings', 'number_of_spot_instances'))
print(f"instance_type: {INSTANCE_TYPE}")
print(f"number_of_spot_instances: {TARGET_NUMBER_OF_INSTANCES}")


def load_distributions(file_path: str) -> dict:
    """Load and return distributions from a pickle file."""
    try:
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        logger.error(f"No such file: '{file_path}'")
        return {}
    except pickle.UnpicklingError:
        logger.error("Could not unpickle file")
        return {}


def get_min_max_times_by_zone(loaded_distributions):
    """
    Calculates the minimum start time and maximum end time per availability zone.

    Args:
    - loaded_distributions (dict): A dictionary containing instances data.

    Returns:
    dict: A dictionary mapping availability zones to their min start time and max end time.
    """
    zone_times = {}

    for key, content in loaded_distributions.items():
        for instance_id, instance_data in content["instances"].items():
            zone = instance_data.availability_zone
            start_time = instance_data.start_time
            end_time = instance_data.end_time

            if zone not in zone_times:
                zone_times[zone] = {"min_start_time": start_time, "max_end_time": end_time}
            else:
                zone_times[zone]["min_start_time"] = min(start_time, zone_times[zone]["min_start_time"])
                zone_times[zone]["max_end_time"] = max(end_time, zone_times[zone]["max_end_time"])

    return zone_times


def print_zone_times(zone_times):
    """
    Prints the availability zone along with its min start time and max end time.

    Args:
    - zone_times (dict): A dictionary mapping availability zones to their min start time and max end time.
    """
    for zone, times in zone_times.items():
        logger.info(
            f"Availability Zone: {zone}, Min Start Time: {times['min_start_time']}, Max End Time: {times['max_end_time']}"
        )


def extract_region_from_availability_zone(availability_zone):
    """
    Extracts the region from an availability zone.
    e.g., us-east-1a -> us-east-1
    """
    return availability_zone[:-1]


def get_spot_price_history(start_time, end_time, availability_zone, instance_type):
    region_name = extract_region_from_availability_zone(availability_zone)
    session = boto3.Session(region_name=region_name)
    ec2 = session.client('ec2')

    try:
        result = ec2.describe_spot_price_history(
            StartTime=start_time,
            EndTime=end_time,
            InstanceTypes=[instance_type],
            ProductDescriptions=['Linux/UNIX'],
            AvailabilityZone=availability_zone,
            MaxResults=1000
        )

        spot_price_history = result['SpotPriceHistory']

        filtered_spot_price_history = [
            entry for entry in spot_price_history
            if start_time <= entry['Timestamp'] <= end_time
        ]

        if before_start_time_entries := [
            entry
            for entry in spot_price_history
            if entry['Timestamp'] < start_time
        ]:
            most_recent_before_start = max(before_start_time_entries, key=lambda x: x['Timestamp'])
            if most_recent_before_start not in filtered_spot_price_history:
                filtered_spot_price_history.insert(0, most_recent_before_start)

        return filtered_spot_price_history

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return None


def datetime_serializer(obj):
    """Serialize datetime objects as ISO 8601 formatted strings."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError("Type not serializable")


def convert_datetimes(input_data):
    """Convert datetime objects to string recursively in a nested structure."""
    if isinstance(input_data, dict):
        return {key: convert_datetimes(value) for key, value in input_data.items()}
    elif isinstance(input_data, list):
        return [convert_datetimes(element) for element in input_data]
    elif isinstance(input_data, datetime):
        return input_data.isoformat()
    else:
        return input_data


def store_spot_price_history(spot_price_history, filename, subdirectory_path):
    """
    Store the spot price history in a specified file within a specified directory.
    :param spot_price_history: Data containing spot price history to store.
    :param filename: Name of the file to store the data.
    :param subdirectory_path: Path to the subdirectory where the file should be saved.
    """
    directory_path = os.path.join(subdirectory_path, "spot_price_history")

    try:
        os.makedirs(directory_path, exist_ok=True)
        filepath = os.path.join(directory_path, filename)

        with open(filepath, 'w') as file:
            json.dump(spot_price_history, file)

        logger.info(f"Data stored successfully in {filepath}")
    except Exception as e:
        logger.error(f"Failed to store data: {str(e)}")


def remove_old_interruptions(loaded_distributions, hours_limit=10):
    global_max_end_time = loaded_distributions['complete']['global_max_end_time']
    time_limit = global_max_end_time - timedelta(hours=hours_limit)

    logger.debug(f"Complete global_max_end_time: {global_max_end_time}")
    logger.debug(f"Time limit: {time_limit}")

    to_remove = [
        instance_id
        for instance_id, instance_data in loaded_distributions['interruption']['instances'].items()
        if instance_data.end_time >= time_limit
    ]

    logger.info("Removing number of instances: %s", len(to_remove))

    for instance_id in to_remove:
        del loaded_distributions['interruption']['instances'][instance_id]
        logger.debug(f"Removed instance {instance_id} due to old end_time.")

    return loaded_distributions


def update_times_zones_and_regions(loaded_distributions):
    for key in ['complete', 'interruption']:
        instances = loaded_distributions[key]['instances']

        global_min_start_time = min(
            instances.values(), key=lambda x: x.start_time).start_time if instances else None
        global_max_end_time = max(
            instances.values(), key=lambda x: x.end_time).end_time if instances else None

        loaded_distributions[key]['global_min_start_time'] = global_min_start_time
        loaded_distributions[key]['global_max_end_time'] = global_max_end_time

        instances_without_extremes = {
            k: v for k, v in instances.items()
            if v.start_time != global_min_start_time and v.end_time != global_max_end_time
        }

        second_min_start_time = min(
            instances_without_extremes.values(), key=lambda x: x.start_time, default=None)
        second_min_start_time = second_min_start_time.start_time if second_min_start_time else None
        second_max_end_time = max(
            instances_without_extremes.values(), key=lambda x: x.end_time, default=None)
        second_max_end_time = second_max_end_time.end_time if second_max_end_time else None

        loaded_distributions[key]['second_min_start_time'] = second_min_start_time
        loaded_distributions[key]['second_max_end_time'] = second_max_end_time

        loaded_distributions[key]['min_start_instance_id'] = (
            next((id_ for id_, inst in instances.items() if inst.start_time == global_min_start_time), None))
        loaded_distributions[key]['max_end_instance_id'] = (
            next((id_ for id_, inst in instances.items() if inst.end_time == global_max_end_time), None))
        loaded_distributions[key]['second_min_start_instance_id'] = (
            next((id_ for id_, inst in instances_without_extremes.items() if inst.start_time == second_min_start_time),
                 None))
        loaded_distributions[key]['second_max_end_instance_id'] = (
            next((id_ for id_, inst in instances_without_extremes.items() if inst.end_time == second_max_end_time),
                 None))

        all_zones = [instance_data.availability_zone for instance_data in instances.values()]
        all_regions = [zone[:-1] for zone in all_zones]

        zone_distribution = Counter(all_zones)
        region_distribution = Counter(all_regions)

        loaded_distributions[key]['zone'] = zone_distribution
        loaded_distributions[key]['region'] = region_distribution

    return loaded_distributions


def print_dict_without_instances(input_dict):
    dict_copy = copy.deepcopy(input_dict)

    for key in dict_copy.keys():
        if 'instances' in dict_copy[key]:
            instance_count = len(dict_copy[key]['instances'])
            dict_copy[key]['instances'] = f"{instance_count} instances"

    print(json.dumps(dict_copy, indent=4, default=str))


def save_distributions(dist_info, file_name, sub_directory):
    os.makedirs(sub_directory, exist_ok=True)

    file_path = os.path.join(sub_directory, file_name)
    logging.info("=========================================")
    logging.info(f"Saving distributions to {file_path}...")

    with open(file_path, 'wb') as f:
        pickle.dump(dist_info, f)


def main():
    BaseDir = os.getcwd()
    base_dir = BaseDir
    target_name = 'data'
    selected_dir_path = os.path.join(base_dir, target_name)
    logger.debug(f"Selected directory path: {selected_dir_path}")
    loaded_distributions = load_distributions(os.path.join(selected_dir_path, 'original_distribution.pkl'))

    logger.debug("Original distributions:")
    logger.debug("Global min start time for complete: %s", loaded_distributions['complete']['global_min_start_time'])
    logger.debug("Global min start time for interruption: %s",
                 loaded_distributions['interruption']['global_min_start_time'])
    logger.info("Global max end time for complete: %s", loaded_distributions['complete']['global_max_end_time'])
    logger.debug("Global max end time for interruption: %s",
                 loaded_distributions['interruption']['global_max_end_time'])

    logger.debug("Number of instances in original complete bucket: %s",
                 len(loaded_distributions['complete']['instances']))

    file_name = "filtered_distributions.pkl"

    logger.info("Removing old interruption instances...")
    old_interruption_removed_distributions = remove_old_interruptions(loaded_distributions)
    logger.debug(old_interruption_removed_distributions)

    logger.info("Updating times, zones, and regions...")
    filtered_distributions = update_times_zones_and_regions(old_interruption_removed_distributions)
    logger.debug(filtered_distributions)

    logger.debug("Updated distributions:")
    logger.debug("Global min start time for complete: %s", filtered_distributions['complete']['global_min_start_time'])
    logger.debug("Global min start time for interruption: %s",
                 filtered_distributions['interruption']['global_min_start_time'])
    logger.debug("Global max end time for complete: %s", filtered_distributions['complete']['global_max_end_time'])
    logger.debug("Global max end time for interruption: %s",
                 filtered_distributions['interruption']['global_max_end_time'])

    logger.info("Saving filtered distributions...")

    save_distributions(filtered_distributions, file_name, selected_dir_path)

    logger.info("Getting min and max end time per availability zone...")
    zone_times = get_min_max_times_by_zone(filtered_distributions)
    print_zone_times(zone_times)

    for zone, times in zone_times.items():
        start_time = times["min_start_time"]
        end_time = times["max_end_time"]

        logger.info(f"Retrieving spot price history for {zone} from {start_time} to {end_time}...")
        spot_price_history = get_spot_price_history(start_time, end_time, zone, INSTANCE_TYPE)

        spot_price_history = convert_datetimes(spot_price_history)

        logger.info(f"Storing spot price history for {zone} from {start_time} to {end_time}...")
        if spot_price_history is not None:
            filename = f"{zone}_{start_time.strftime('%Y%m%dT%H%M%S')}_{end_time.strftime('%Y%m%dT%H%M%S')}.json"
            store_spot_price_history(spot_price_history, filename, selected_dir_path)


if __name__ == "__main__":
    main()
