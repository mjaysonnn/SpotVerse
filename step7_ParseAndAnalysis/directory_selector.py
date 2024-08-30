import logging
import os
import pickle

from my_logger import LoggerSetup

logger = LoggerSetup.setup_logger()


def select_subdirectory(base_dir, target_dir_name):
    """
    Given a base directory and target name, allow the user to select from matching subdirectories.

    Parameters:
    - base_dir (str): The base directory to search within.
    - target_dir_name (str): The string to look for in subdirectory names.

    Returns:
    str: The path to the selected subdirectory, or None if no selection was made.
    """
    try:
        directories = next(os.walk(base_dir))[1]
    except StopIteration:
        logger.error(f"No directories found in {base_dir}")
        return None

    matching_directories = [d for d in directories if target_dir_name.lower() in d.lower()]

    # Sort the directories before logging and showing them to the user
    matching_directories_sorted = sorted(matching_directories)

    logger.info(f"Directories containing '{target_dir_name}': {matching_directories_sorted}")

    print("Please select a directory:")
    for i, dir_name in enumerate(matching_directories_sorted):
        print(f"{i + 1}. {dir_name}")

    selected_index = input(f"Enter number (1-{len(matching_directories_sorted)}): ")

    try:
        selected_index = int(selected_index) - 1
        selected_dir = matching_directories_sorted[selected_index]
    except (ValueError, IndexError):
        logger.error(
            f"Invalid selection: {selected_index}. "
            f"Please enter a number between 1 and {len(matching_directories_sorted)}.")
        return None

    return os.path.join(base_dir, selected_dir)


def load_data(file_path):
    """
    Load data from a pickle file.
    :param file_path:
    :return:
    """
    logger.debug(f"Loading data from {file_path}...")
    try:
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    except (FileNotFoundError, pickle.UnpicklingError) as e:
        logging.error(f"Failed to load data from {file_path}: {str(e)}")
        return None
