import logging
import os
import pickle
import warnings

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from my_logger import LoggerSetup
from utils import FileType

# Suppress warnings judiciously
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Setup logger
logger = LoggerSetup.setup_logger()
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)


def load_distributions(file_path: str) -> dict:
    """Load and return distributions from a pickle file."""
    try:
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    except (FileNotFoundError, pickle.UnpicklingError) as e:
        logger.error(f"Error loading distributions: {str(e)}")
        return {}


def sort_instances_by_end_time(instances):
    """Sort instances by end time."""
    return sorted(instances, key=lambda x: x.end_time)


def convert_to_relative_times_hours(times, reference_time):
    """Convert times to relative times in hours based on the reference time."""
    return [(t - reference_time).total_seconds() / 3600 for t in times]


def plot_cumulative_counts(relative_times, cumulative_counts, max_end_time, min_start_time, save_dir,
                           filename="cumulative_interruptions.png"):
    """Plot and save a graph of cumulative interruptions."""
    plt.figure(figsize=(10, 6))
    plt.plot(relative_times, cumulative_counts, linestyle='-', marker='', color='b')
    plt.xlabel('Time (hours)', fontsize=20, fontweight='bold')
    plt.ylabel('Cumulative # of interruptions', fontsize=20, fontweight='bold')

    max_end_time_hours = (max_end_time - min_start_time).total_seconds() / 3600
    padding_hours = 5

    plt.xlim([0, max_end_time_hours + padding_hours])
    plt.xticks(range(0, int(max_end_time_hours + padding_hours) + 1, 5))
    plt.grid(True)
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.tick_params(axis='both', which='major', labelsize=12)
    plt.tight_layout()

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)
        plt.savefig(save_path)
        print(f"Plot saved at {save_path}")

    try:
        plt.show()
    except Exception as e:
        print(f"Unable to show plot due to error: {str(e)}")


def main():
    base_dir = os.getcwd()
    selected_dir_path = os.path.join(base_dir, 'data')
    logger.info(f"Selected directory path: {selected_dir_path}")

    file_to_use = 'filtered_distributions.pkl'
    loaded_distributions = load_distributions(os.path.join(selected_dir_path, file_to_use))

    complete_information = loaded_distributions.get(FileType.COMPLETE.value)
    if complete_information is None:
        logger.error("Failed to load 'complete' data.")
        return

    max_end_time = complete_information.get('global_max_end_time')
    if max_end_time is None:
        logger.error("Global max end time is missing.")
        return

    interruption_information = loaded_distributions.get(FileType.INTERRUPTION.value)
    if interruption_information is None:
        logger.warning("No 'interruption' data found. Creating default zero-interruption graph.")
        min_start_time = max_end_time
        relative_times_hours = [0, (max_end_time - min_start_time).total_seconds() / 3600]
        cumulative_counts = [0, 0]
    else:
        min_start_time = interruption_information.get('global_min_start_time')
        if min_start_time is None:
            logger.warning("Min start time is missing, using max end time as a fallback.")
            min_start_time = max_end_time

        instances = interruption_information['instances'].values()
        instances_sorted = sort_instances_by_end_time(instances)

        if not instances_sorted:
            logger.info("No interruption instances found. Creating default zero-interruption graph.")
            relative_times_hours = [0, (max_end_time - min_start_time).total_seconds() / 3600]
            cumulative_counts = [0, 0]
        else:
            logger.debug(f"min_start_time: {min_start_time}")
            logger.debug(f"max_end_time: {max_end_time}")

            cumulative_counts = list(range(1, len(instances_sorted) + 1))
            interruption_times = [instance.end_time for instance in instances_sorted]
            logger.debug(f"Interruption times: {interruption_times}")

            relative_times_hours = convert_to_relative_times_hours(interruption_times, min_start_time)
            logger.debug(f"Relative times (hours): {relative_times_hours}")

    plot_cumulative_counts(relative_times_hours, cumulative_counts, max_end_time, min_start_time, selected_dir_path)


if __name__ == "__main__":
    main()
