"""
This script parses the data and saves all the information in a pickle file.
"""
import logging
import os
import pickle
import re
from datetime import datetime
from typing import Dict, Optional

import pytz

from directory_selector import select_subdirectory
from my_logger import LoggerSetup

logger = LoggerSetup.setup_logger()

ON_DEMAND_COST_PER_HOUR = 0.192
RUNNING_HOURS = 10
NUMBER_OF_INSTANCES = 40
INSTANCE_TYPE = 'm5.xlarge'

from utils import FileType, Instance


def extract_content(text: str, pattern: str) -> str:
    """
    Extract the content from the text using the pattern.
    """
    match = re.search(pattern, text)
    return match[1] if match else None


def convert_to_datetime(datetime_str: str) -> Optional[datetime]:
    """
    Convert the datetime string to datetime object.
    :param datetime_str:
    :return:
    """
    try:
        # If the datetime string has a 'Z', replace it with '+00:00' to make it offset-aware
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00')) if datetime_str else None
    except Exception as e:
        logging.error(f"Error converting datetime: {datetime_str}, Error: {str(e)}")
        return None


def parse_file_content_complete(file_path: str) -> tuple:
    """
    Parse the file content and return the instance ID, availability zone, region, start time, end time, and cost.
    """
    with open(file_path, 'r') as file:
        content = file.read()

        instance_id = extract_content(content, r'Instance ID: (\S+)')
        availability_zone = extract_content(content, r'Availability Zone: (\w+-\w+-\d\w)')
        region = availability_zone[:-1] if availability_zone else None

        start_time = convert_to_datetime(extract_content(content, r'Instance Launch Time: (.+)'))
        end_time = convert_to_datetime(extract_content(content, r'Current Time: (.+)'))
        cost = float(extract_content(content, r'Current Spot Price: (.+)'))

        return instance_id, availability_zone, region, start_time, end_time, cost


def parse_file_content_interruption(file_path: str) -> tuple:
    """
    Parse the file content and return the instance ID, availability zone, region, start time, end time, and cost.
    """
    with open(file_path, 'r') as file:
        content = file.read()

        instance_id = extract_content(content, r'Instance ID: (\S+)')
        availability_zone = extract_content(content, r'Availability Zone: (\w+-\w+-\d\w)')
        region = availability_zone[:-1] if availability_zone else None

        start_time = convert_to_datetime(extract_content(content, r'Instance Launch Time: (.+)'))
        end_time = convert_to_datetime(extract_content(content, r'Spot Interruption Warning Time: (.+)'))

        cost_str = extract_content(content, r'Current Spot Price: (.+)')
        if cost_str is not None:
            cost = float(cost_str)
        else:
            cost = 0.0
            logger.debug("Cost was None, setting to 0.0")

        return instance_id, availability_zone, region, start_time, end_time, cost


def update_distribution(distribution: dict, key: str):
    """
    Update the distribution dictionary with the key.
    """
    if key:
        distribution[key] = distribution.get(key, 0) + 1


def initialize_distributions():
    """
    Initialize the distribution's dictionary.
    """
    utc = pytz.UTC
    return {
        "zone": {},
        "region": {},
        "instance_type": INSTANCE_TYPE,
        "instances": {},
        "global_min_start_time": utc.localize(datetime.max),
        "global_max_end_time": utc.localize(datetime.min),
        "min_start_instance_id": None,
        "max_end_instance_id": None,
        "second_min_start_time": utc.localize(datetime.max),
        "second_max_end_time": utc.localize(datetime.min),
        "second_min_start_instance_id": None,
        "second_max_end_instance_id": None
    }


def update_min_max_times(distribution_information, start_time, end_time, instance_id):
    """
    Update the min and next min start times and max and previous max end times.
    """
    utc = pytz.UTC
    start_time = utc.localize(start_time) if start_time.tzinfo is None else start_time
    end_time = utc.localize(end_time) if end_time.tzinfo is None else end_time

    global_min_start_time = distribution_information["global_min_start_time"]
    global_max_end_time = distribution_information["global_max_end_time"]
    second_min_start_time = distribution_information["second_min_start_time"]
    second_max_end_time = distribution_information["second_max_end_time"]

    # Update min and second min start times
    if start_time < global_min_start_time:
        distribution_information["second_min_start_time"], distribution_information["second_min_start_instance_id"] = \
            global_min_start_time, distribution_information["min_start_instance_id"]
        distribution_information["global_min_start_time"], distribution_information[
            "min_start_instance_id"] = start_time, instance_id
    elif global_min_start_time < start_time < second_min_start_time:
        distribution_information["second_min_start_time"], distribution_information[
            "second_min_start_instance_id"] = start_time, instance_id

    # Update max and second max end times
    if end_time > global_max_end_time:
        distribution_information["second_max_end_time"], distribution_information["second_max_end_instance_id"] = \
            global_max_end_time, distribution_information["max_end_instance_id"]
        distribution_information["global_max_end_time"], distribution_information[
            "max_end_instance_id"] = end_time, instance_id
    elif global_max_end_time > end_time > second_max_end_time:
        distribution_information["second_max_end_time"], distribution_information[
            "second_max_end_instance_id"] = end_time, instance_id


def analyze_directory(base_directory: str, file_type: FileType) -> dict:
    """
    Analyze the directory and return the distribution dictionary.
    """

    utc = pytz.UTC

    # Initialize the distribution dictionary
    distribution_info = initialize_distributions()

    for root, _, files in os.walk(base_directory):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            try:
                # logger.debug(f"Processing {file_path}...")
                if file_type == FileType.COMPLETE:
                    instance_id, availability_zone, region, start_time, end_time, cost = \
                        parse_file_content_complete(file_path)
                else:
                    instance_id, availability_zone, region, start_time, end_time, cost = \
                        parse_file_content_interruption(file_path)

                update_distribution(distribution_info["zone"], availability_zone)
                update_distribution(distribution_info["region"], region)

                completion_hours = ((end_time - start_time).total_seconds() / 3600) if start_time and end_time else None
                total_cost = completion_hours * cost if completion_hours is not None and cost is not None else None

                distribution_info["instances"][instance_id] = Instance(start_time, end_time, availability_zone, cost,
                                                                       completion_hours, total_cost)

                if start_time and end_time:
                    update_min_max_times(distribution_info, start_time, end_time, instance_id)

            except Exception as e:
                logging.error(f"Error processing {file_path}: {str(e)}")

    return distribution_info


def print_distribution(distributions: dict):
    """
    Print the distribution.
    """
    logging.info(f"Availability Zone Distribution: {distributions['zone']}")
    logging.info(f"Region Distribution: {distributions['region']}")
    logging.info("Instance Information: ")
    logging.info(f"Earliest Start Time: {distributions['global_min_start_time']}, "
                 f"Instance ID: {distributions['min_start_instance_id']}")
    logging.info(f"Second Earliest Start Time: {distributions['second_min_start_time']}, "
                 f"Instance ID: {distributions['second_min_start_instance_id']}")
    logging.info(f"Second Latest End Time: {distributions['second_max_end_time']}, "
                 f"Instance ID: {distributions['second_max_end_instance_id']}")
    logging.info(f"Latest End Time: {distributions['global_max_end_time']}, "
                 f"Instance ID: {distributions['max_end_instance_id']}")

    # for instance_id, instance_info in distributions["instances"].items():
    #     logging.info(f"  {instance_id}:")
    #     logging.info(f"    Start Time: {instance_info.start_time}")
    #     logging.info(f"    End Time: {instance_info.end_time}")
    #     logging.info(f"    Availability Zone: {instance_info.availability_zone}")
    #     logging.info(f"    Cost Per Hour: {instance_info.cost_per_hour}")
    #     logging.info(f"    Completion Hours: {instance_info.completion_hours}")
    #     logging.info(f"    Total Cost: {instance_info.total_cost}")  # Add this line

    # Calculate and logging.info the total duration
    total_duration = distributions['global_max_end_time'] - distributions['global_min_start_time']
    logging.info(f"Total Duration: {total_duration} (HH:MM:SS)")
    logging.info("=========================================")


def compare_start_times(all_distributions_info: Dict[str, Dict[str, Optional[datetime]]]) -> None:
    """
    Compare the earliest start times in the 'complete' and 'interruption' logs.
    """
    if "complete" in all_distributions_info and "interruption" in all_distributions_info:
        complete_min_time = all_distributions_info["complete"].get("global_min_start_time")
        interruption_min_time = all_distributions_info["interruption"].get("global_min_start_time")

        if complete_min_time is not None and interruption_min_time is not None:
            utc = pytz.UTC

            # Ensure datetime are timezone-aware
            complete_min_time = utc.localize(
                complete_min_time) if complete_min_time.tzinfo is None else complete_min_time
            interruption_min_time = utc.localize(
                interruption_min_time) if interruption_min_time.tzinfo is None else interruption_min_time

            if complete_min_time < interruption_min_time:
                logging.info("The earliest start time is in the 'complete' logs.")
                logging.info(f"Min start time in 'complete' logs: {complete_min_time.isoformat()}")
            elif complete_min_time > interruption_min_time:
                logging.info("The earliest start time is in the 'interruption' logs.")
                logging.info(f"Min start time in 'interruption' logs: {interruption_min_time.isoformat()}")
            else:
                logging.info("The earliest start times in both 'complete' and 'interruption' logs are equal.")
                logging.info(f"Min start time: {complete_min_time.isoformat()}")
        else:
            logging.info("\nCould not determine the earliest start time due to None values.")
    else:
        logging.info("\nUnable to compare start times as logs for 'complete' and/or 'interruption' do not exist.")


def compare_end_times(all_distributions_info: Dict[str, Dict[str, Optional[datetime]]]) -> None:
    """
    Compare the latest end times in the 'complete' and 'interruption' logs.

    :param all_distributions_info: Dictionary containing log data of 'complete' and 'interruption' events.
    :return: None. Print the comparison result.
    """
    if "complete" in all_distributions_info and "interruption" in all_distributions_info:
        complete_max_time = all_distributions_info["complete"].get("global_max_end_time")
        interruption_max_time = all_distributions_info["interruption"].get("global_max_end_time")

        if complete_max_time is not None and interruption_max_time is not None:
            utc = pytz.UTC  # Ensure using the same timezone for comparison

            # Ensure datetime are timezone-aware
            complete_max_time = utc.localize(
                complete_max_time) if complete_max_time.tzinfo is None else complete_max_time
            interruption_max_time = utc.localize(
                interruption_max_time) if interruption_max_time.tzinfo is None else interruption_max_time

            if complete_max_time > interruption_max_time:
                logging.info("The latest end time is in the 'complete' logs.")
                logging.info(f"Max end time in 'complete' logs: {complete_max_time.isoformat()}")
            elif complete_max_time < interruption_max_time:
                logging.info("The latest end time is in the 'interruption' logs.")
                logging.info(f"Max end time in 'interruption' logs: {interruption_max_time.isoformat()}")
            else:
                logging.info("The latest end times in both 'complete' and 'interruption' logs are equal.")
                logging.info(f"Max end time: {complete_max_time.isoformat()}")
        else:
            logging.error("Could not determine the latest end time due to None values.")
    else:
        logging.error("Unable to compare end times as logs for 'complete' and/or 'interruption' do not exist.")


def aggregate_costs(instances):
    """
    Aggregate the total cost of all instances.
    """
    total_cost = 0.0
    for instance_id, instance in instances.items():
        if instance.total_cost:
            total_cost += instance.total_cost
    return total_cost


def analyze_and_add_distribution(full_path, file_type, all_distributions_info):
    """
    Analyze the directory and add the distribution to the dictionary of all distributions.
    :return:
    """
    logging.info("=========================================")
    logging.info(f"Analyzing {file_type}")
    logging.info(f"Directory is {full_path}...")

    # Analyze the directory
    distribution_info = analyze_directory(full_path, file_type)

    # Print the distribution
    print_distribution(distribution_info)

    # Save the distribution to the dictionary of all distributions
    all_distributions_info[file_type.name.lower()] = distribution_info

    return distribution_info


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


def get_subdirectories(path):
    """
    Retrieve the subdirectories of a given path.

    Parameters:
        path (str): The path for which to retrieve the subdirectories.

    Returns:
        list: A list of subdirectory names.
    """
    try:
        subdirectories = next(os.walk(path))[1]
    except StopIteration:
        logger.error(f"No subdirectories found in {path}")
        subdirectories = []

    return subdirectories


####################################################################################################

def find_directory(target_dir_name):
    BaseDir = os.getcwd()
    base_dir = BaseDir
    global_total_cost = 0.0
    all_distributions = {}

    selected_dir_path = select_subdirectory(base_dir, target_dir_name)
    logger.debug(f"Selected directory path: {selected_dir_path}")

    subdirectories = get_subdirectories(selected_dir_path)
    if not subdirectories:
        logger.warning(f"No subdirectories to process in {selected_dir_path}")
        return
    logger.debug(f"Subdirectories: {subdirectories}")

    for directory in subdirectories:
        full_dir_path = os.path.join(selected_dir_path, directory)

        if "complete" in directory.lower():
            distributions = analyze_and_add_distribution(full_dir_path, FileType.COMPLETE, all_distributions)
        elif "interruption" in directory.lower():
            distributions = analyze_and_add_distribution(full_dir_path, FileType.INTERRUPTION, all_distributions)
        else:
            logger.warning(f"Directory type not recognized: {directory}")
            continue

        global_total_cost += aggregate_costs(distributions['instances'])

    logging.info(f"Total Cost of Spot Instances (Without Detailed Information): ${global_total_cost:.2f}")

    compare_start_times(all_distributions)
    compare_end_times(all_distributions)

    file_name = "original_distribution.pkl"
    save_distributions(all_distributions, file_name, selected_dir_path)


# Main Entry Point
if __name__ == "__main__":
    target_directory_name = "data"  # The name of the directory you're trying to find
    find_directory(target_directory_name)
