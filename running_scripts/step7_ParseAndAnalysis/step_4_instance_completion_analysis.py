import configparser
import pickle
import warnings
import logging
import os
import matplotlib.pyplot as plt
from pathlib import Path

from my_logger import LoggerSetup

# Suppress warnings judiciously
warnings.filterwarnings("ignore", category=DeprecationWarning)

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
NUMBER_OF_INSTANCES = int(config.get('settings', 'number_of_spot_instances'))
print(f"instance_type: {INSTANCE_TYPE}")
print(f"number_of_spot_instances: {NUMBER_OF_INSTANCES}")


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


def sort_instances_by_end_time(instances):
    """Sort instances by end time."""
    return sorted(instances, key=lambda x: x.end_time)


def append_max_end_time(times, max_end_time):
    """Append max end time to the list of times if needed."""
    while len(times) < NUMBER_OF_INSTANCES:
        times.append(max_end_time)
    return times[:NUMBER_OF_INSTANCES]


def convert_to_relative_times_hours(times, reference_time):
    """Convert times to relative times in hours based on the reference time."""
    return [(t - reference_time).total_seconds() / 3600 for t in times]


def plot_cumulative_completions(relative_times, cumulative_counts, max_end_time, min_start_time, save_dir,
                                filename="cumulative_completions.png"):
    """Plot and save a graph of cumulative completions."""
    plt.figure(figsize=(10, 6))
    plt.plot(relative_times, cumulative_counts, linestyle='-', marker='', color='b')

    plt.xlabel('Time (hours)', fontsize=20, fontweight='bold')
    plt.ylabel('Cumulative # of completions', fontsize=20, fontweight='bold')

    max_end_time_hours = (max_end_time - min_start_time).total_seconds() / 3600
    padding_hours = 5

    plt.xlim([0, max_end_time_hours + padding_hours])
    plt.xticks(range(0, int(max_end_time_hours + padding_hours) + 1, 5))
    plt.tick_params(axis='both', which='major', labelsize=12)
    plt.grid(True)

    plt.tight_layout()

    # Save the plot to the file
    full_path = os.path.join(save_dir, filename)
    plt.savefig(full_path)
    logging.info(f"Saved figure to {full_path}")

    # Display the plot
    plt.show()


def main():
    selected_dir_path = os.path.join(os.getcwd(), 'data')
    logger.info(f"Selected directory path: {selected_dir_path}")

    file_to_use = 'filtered_distributions.pkl'
    loaded_distributions = load_distributions(os.path.join(selected_dir_path, file_to_use))

    complete_information = loaded_distributions.get('complete')
    if complete_information is None:
        logger.error(f"Failed to load 'complete' data from {file_to_use}.")
        return

    min_start_time = complete_information.get('global_min_start_time')
    max_end_time = complete_information.get('global_max_end_time')

    if not min_start_time or not max_end_time:
        logger.error("Global start and end times are missing.")
        return

    instances = complete_information['instances'].values()
    instances_sorted = sort_instances_by_end_time(instances)

    completion_times = [instance.end_time for instance in instances_sorted]
    completion_times = append_max_end_time(completion_times, max_end_time)

    cumulative_counts = list(range(1, len(completion_times) + 1))
    relative_times_hours = convert_to_relative_times_hours(completion_times, min_start_time)

    plot_cumulative_completions(relative_times_hours, cumulative_counts, max_end_time, min_start_time, selected_dir_path)


if __name__ == "__main__":
    main()
