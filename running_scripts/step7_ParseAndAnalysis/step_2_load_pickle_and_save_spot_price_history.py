# from datetime import datetime
import copy
import logging
import os
import pickle
from collections import Counter
from datetime import datetime

import boto3

from directory_selector import select_subdirectory, load_data
from my_logger import LoggerSetup

logger = LoggerSetup.setup_logger()
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)

INSTANCE_TYPE = 'm5.xlarge'

TARGET_NUMBER_OF_INSTANCES = 40


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


def select_directory_and_load(file_name, target_dir_name):
    """
    Find directories, let user choose one, and load a file from that directory.

    :param file_name: The name of the file to load.
    :param target_dir_name: A string to match against directory names.
    :return: The loaded data, or None if loading failed.
    """
    base_dir = '..'

    # Try to get the list of directories
    try:
        directories = next(os.walk(base_dir))[1]
    except StopIteration:
        logging.error(f"No directories found in {base_dir}")
        directories = []

    logging.info(f"Directories: {directories}")

    # Find directories containing the target string
    matching_directories = [
        dir_name for dir_name in directories if target_dir_name in dir_name
    ]

    if matching_directories:
        logging.info(f"Directories containing '{target_dir_name}': {matching_directories}")
    else:
        logging.warning(f"No directories containing '{target_dir_name}' found in {base_dir}")
        return None

    # Prompt user to select one of the found directories
    print("Please select a directory:")
    for i, dir_name in enumerate(matching_directories):
        logging.info(f"{i + 1}. {dir_name}")

    selected_index = input(f"Enter number (1-{len(matching_directories)}): ")

    # Validate input and load the data
    try:
        selected_index = int(selected_index)
        if 1 <= selected_index <= len(matching_directories):
            selected_dir = matching_directories[selected_index - 1]
            logging.info(f"You selected: {selected_dir}")

            file_path = os.path.join(base_dir, selected_dir, file_name)
            logging.info(f"Loading data from {file_path}...")
            return load_distributions(file_path), selected_dir
        else:
            logging.warning(
                f"Invalid selection: {selected_index}. Please enter a number between 1 and {len(matching_directories)}."
            )
            return None
    except ValueError:
        logging.warning(f"Invalid input: {selected_index}. Please enter a number.")
        return None


def get_min_max_times_by_zone(loaded_distributions):
    """
    Calculates the minimum start time and maximum end time per availability zone.

    Args:
    - loaded_distributions (dict): A dictionary containing instances data.

    Returns:
    dict: A dictionary mapping availability zones to their min start time and max end time.
    """
    zone_times = {}

    # Iterate through each key (interruption and complete) and their instances
    for key, content in loaded_distributions.items():
        for instance_id, instance_data in content["instances"].items():
            # Retrieve the zone of the current instance
            zone = instance_data.availability_zone

            # Retrieve the start and end times of the current instance
            start_time = instance_data.start_time
            end_time = instance_data.end_time

            # If the zone is not already in the results' dictionary, add it
            if zone not in zone_times:
                zone_times[zone] = {"min_start_time": start_time, "max_end_time": end_time}
            else:
                # Compare and update the min start time and max end time for the zone
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
    # Initialize a session using Amazon DynamoDB.
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

        # Filter entries between start_time and end_time or the most recent before start_time
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
    elif isinstance(input_data, datetime.datetime):
        return input_data.isoformat()
    else:
        return input_data


# Use the function before saving the data


def store_spot_price_history(spot_price_history, filename, subdirectory_path):
    """
    Store the spot price history in a specified file within a specified directory.
    :param spot_price_history: Data containing spot price history to store.
    :param filename: Name of the file to store the data.
    :param subdirectory_path: Path to the subdirectory where the file should be saved.
    """
    # Creating a path to the 'spot_price_history' folder inside the chosen subdirectory
    directory_path = os.path.join(subdirectory_path, "spot_price_history")

    try:
        # Check if directory exists, if not, create it
        os.makedirs(directory_path, exist_ok=True)

        filepath = os.path.join(directory_path, filename)

        # Save the spot price history
        with open(filepath, 'w') as file:
            json.dump(spot_price_history, file)

        logger.info(f"Data stored successfully in {filepath}")
    except Exception as e:
        logger.error(f"Failed to store data: {str(e)}")


def remove_old_interruptions(loaded_distributions, hours_limit=10):
    """
    Remove interruption instances with end_time that is behind [hours_limit] hours compared to
    complete's global_max_end_time.

    Args:
    - loaded_distributions (dict): The distributions data loaded from the pickle file.
    - hours_limit (int): The maximum allowable hours between interruption end_time and complete's global_max_end_time.
    """
    # Extracting global_max_end_time from "complete" part of the distributions
    global_max_end_time = loaded_distributions['complete']['global_max_end_time']

    # Creating a time delta object for hours_limit
    time_limit = global_max_end_time - timedelta(hours=hours_limit)

    logger.debug(f"Complete global_max_end_time: {global_max_end_time}")
    logger.debug(f"Time limit: {time_limit}")

    # Identifying instances to remove based on their end_time
    to_remove = [
        instance_id
        for instance_id, instance_data in loaded_distributions['interruption']['instances'].items()
        if instance_data.end_time >= time_limit
    ]

    logger.info("Removing number of instances: %s", len(to_remove))

    # Removing identified instances
    for instance_id in to_remove:
        del loaded_distributions['interruption']['instances'][instance_id]
        logger.debug(f"Removed instance {instance_id} due to old end_time.")

    return loaded_distributions


def update_times_zones_and_regions(loaded_distributions):
    """
    Update global time attributes and zone/region attributes in the loaded_distributions.

    Args:
    - loaded_distributions (dict): The distributions containing instances.

    Returns:
    dict: The updated distributions with recalculated global times, zones, and regions.
    """
    for key in ['complete', 'interruption']:  # Assuming you have these two keys
        instances = loaded_distributions[key]['instances']

        # Recalculate global min/max start/end times
        global_min_start_time = min(
            instances.values(), key=lambda x: x.start_time).start_time if instances else None
        global_max_end_time = max(
            instances.values(), key=lambda x: x.end_time).end_time if instances else None

        # Update global times in the loaded_distributions
        loaded_distributions[key]['global_min_start_time'] = global_min_start_time
        loaded_distributions[key]['global_max_end_time'] = global_max_end_time

        # Exclude instances with global min start and max end times
        instances_without_extremes = {
            k: v for k, v in instances.items()
            if v.start_time != global_min_start_time and v.end_time != global_max_end_time
        }

        # Find second min/max start/end times and related instance IDs
        second_min_start_time = min(
            instances_without_extremes.values(), key=lambda x: x.start_time, default=None)
        second_min_start_time = second_min_start_time.start_time if second_min_start_time else None
        second_max_end_time = max(
            instances_without_extremes.values(), key=lambda x: x.end_time, default=None)
        second_max_end_time = second_max_end_time.end_time if second_max_end_time else None

        # Update the other times in the loaded_distributions
        loaded_distributions[key]['second_min_start_time'] = second_min_start_time
        loaded_distributions[key]['second_max_end_time'] = second_max_end_time

        # Update instance IDs related to global times in the loaded_distributions
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

        # Update zones and regions distributions based on the instances data
        all_zones = [instance_data.availability_zone for instance_data in instances.values()]
        all_regions = [zone[:-1] for zone in all_zones]

        # Use Counter to create a distribution of zones and regions
        zone_distribution = Counter(all_zones)
        region_distribution = Counter(all_regions)

        loaded_distributions[key]['zone'] = zone_distribution
        loaded_distributions[key]['region'] = region_distribution

    return loaded_distributions


import datetime

import json


def print_dict_without_instances(input_dict):
    """
    Print the dictionary without the 'instances' key, but show the number of instances.

    Args:
    - input_dict (dict): The original dictionary.
    """
    # Create a copy of the dictionary to keep the original unmodified
    dict_copy = copy.deepcopy(input_dict)

    # Check if 'instances' key is in the dictionary and replace it with its length
    for key in dict_copy.keys():
        if 'instances' in dict_copy[key]:
            instance_count = len(dict_copy[key]['instances'])
            dict_copy[key]['instances'] = f"{instance_count} instances"

    # Print the modified copy
    print(json.dumps(dict_copy, indent=4, default=str))


def save_distributions(dist_info, file_name, sub_directory):
    """
    Save the distributions to a pickle file in the specified subdirectory.

    :param dist_info: The distribution information to save.
    :param file_name: The name of the file to save the distribution info into.
    :param sub_directory: The subdirectory to save the file in.
    """
    # Ensure the subdirectory exists; if not, create it.
    os.makedirs(sub_directory, exist_ok=True)

    file_path = os.path.join(sub_directory, file_name)
    logging.info("=========================================")
    logging.info(f"Saving distributions to {file_path}...")

    with open(file_path, 'wb') as f:
        pickle.dump(dist_info, f)


import random
from datetime import timedelta


def fill_complete_from_interruption(loaded_distributions, TARGET_NUMBER_OF_INSTANCES, ):
    """
    Process the loaded_distributions dictionary and log the results.

    Args:
        loaded_distributions (dict): Dictionary containing instances data.
        TARGET_NUMBER_OF_INSTANCES (int): Target number of instances.
        logger (Logger): Logger object for logging.

    Returns:
        dict: Updated loaded_distributions dictionary.
    """
    # Number of instances in complete
    # logger.debug(f"Number of instances in complete: {len(loaded_distributions['complete']['instances'])}")

    # Have to fill in the missing instances from interruption
    logger.debug(f"Target number of instances in complete: {TARGET_NUMBER_OF_INSTANCES}")
    missing_instances_count = TARGET_NUMBER_OF_INSTANCES - len(loaded_distributions['complete']['instances'])
    logger.debug(f"Will use last {missing_instances_count} instances from interruption")

    # Sort instances from interruption by end time
    sorted_instances = sorted(loaded_distributions['interruption']['instances'].items(), key=lambda x: x[1].end_time)

    # Show first and last items in sorted instances
    # logger.debug(f"First item in sorted instances: {sorted_instances[0]}")
    # logger.debug(f"Last item in sorted instances: {sorted_instances[-1]}")

    # Get the last missing_instances_count instances
    instances_to_use = sorted_instances[-missing_instances_count:]
    # logger.debug(f"Instances to use: {instances_to_use}")
    # logger.debug(f"Number of instances to use: {len(instances_to_use)}")

    for instance_id, instance_data in instances_to_use:
        # logger.debug(instance_data)
        minute_rand_value = random.randint(0, 56)  # Currently, this random value is generated but not used
        instance_data.start_time = instance_data.end_time - timedelta(hours=10, minutes=minute_rand_value)
        # update total_cost and duration based on the new start time
        instance_data.completion_hours = (instance_data.end_time - instance_data.start_time).total_seconds() / 3600
        instance_data.total_cost = instance_data.cost_per_hour * instance_data.completion_hours
        # logger.debug(instance_data)
        loaded_distributions['complete']['instances'][instance_id] = instance_data
        del loaded_distributions['interruption']['instances'][instance_id]

    # Update region and zone distributions
    # logger.debug("Updating region and zone distributions...")
    # logger.debug("Before update:")
    # logger.debug("Complete region distribution: %s", loaded_distributions['complete']['region'])
    # logger.debug("Complete zone distribution: %s", loaded_distributions['complete']['zone'])
    loaded_distributions = update_times_zones_and_regions(loaded_distributions)
    # logger.debug("After update:")
    # logger.debug("Complete region distribution: %s", loaded_distributions['complete']['region'])
    # logger.debug("Complete zone distribution: %s", loaded_distributions['complete']['zone'])
    # logger.debug(loaded_distributions)

    # Print the last 35 instances in complete
    # logger.debug("Last 35 instances in complete:")
    # for instance_id, instance_data in sorted(loaded_distributions['complete']['instances'].items(),
    #                                          key=lambda x: x[1].end_time)[-35:]:
    # logger.debug(f"{instance_id}: {instance_data}")

    # Number of instances in complete
    # logger.debug(f"Number of instances in complete: {len(loaded_distributions['complete']['instances'])}")

    return loaded_distributions


def main():
    BaseDir = os.getcwd()
    base_dir = BaseDir
    target_name = 'data'  # The target directory name to match against
    selected_dir_path = select_subdirectory(base_dir, target_name)
    logger.debug(f"Selected directory path: {selected_dir_path}")
    loaded_distributions = load_data(os.path.join(selected_dir_path, 'original_distribution.pkl'))
    # logger.debug(f"Loaded distributions: {loaded_distributions}")

    logger.debug("Original distributions:")
    logger.debug("Global min start time for complete: %s", loaded_distributions['complete']['global_min_start_time'])
    logger.debug("Global min start time for interruption: %s",
                 loaded_distributions['interruption']['global_min_start_time'])
    logger.info("Global max end time for complete: %s", loaded_distributions['complete']['global_max_end_time'])
    logger.debug("Global max end time for interruption: %s",
                 loaded_distributions['interruption']['global_max_end_time'])

    # Main script or main function
    logger.debug("Number of instances in original complete bucket: %s",
                 len(loaded_distributions['complete']['instances']))

    file_name = "filtered_distributions.pkl"

    # Prompt user for input
    choice = input(
        "Do you want to fill the 'complete' bucket from the 'interruption' bucket? (yes/no): ").strip().lower()

    if choice == 'yes':
        complete_bucket_filled_distributions = fill_complete_from_interruption(loaded_distributions,
                                                                               TARGET_NUMBER_OF_INSTANCES)
        logger.debug(
            f"Number of instances in complete bucket filled: {len(complete_bucket_filled_distributions['complete']['instances'])}")
        file_name = "filtered_distributions_with_filled_complete_bucket.pkl"
    else:
        complete_bucket_filled_distributions = loaded_distributions
        logger.debug("Operation aborted by the user.")

    logger.info("Removing old interruption instances...")
    old_interruption_removed_distributions = remove_old_interruptions(complete_bucket_filled_distributions)
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

    # Iterate through each zone and its times
    for zone, times in zone_times.items():

        # Convert string times to datetime objects (needed for API requests)
        start_time = times["min_start_time"]
        end_time = times["max_end_time"]

        logger.info(f"Retrieving spot price history for {zone} from {start_time} to {end_time}...")
        spot_price_history = get_spot_price_history(start_time, end_time, zone, INSTANCE_TYPE)

        spot_price_history = convert_datetimes(spot_price_history)

        logger.info(f"Storing spot price history for {zone} from {start_time} to {end_time}...")
        # logger.debug(f"Spot price history for {zone} from {start_time} to {end_time}: {spot_price_history[:5]}")
        if spot_price_history is not None:
            filename = f"{zone}_{start_time.strftime('%Y%m%dT%H%M%S')}_{end_time.strftime('%Y%m%dT%H%M%S')}.json"
            store_spot_price_history(spot_price_history, filename, selected_dir_path)


if __name__ == "__main__":
    main()
