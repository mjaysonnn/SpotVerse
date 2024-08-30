import logging
import pickle
import warnings

from matplotlib.ticker import MaxNLocator

from directory_selector import select_subdirectory, load_data
from my_logger import LoggerSetup

# Suppress warnings (use judiciously)

logger = LoggerSetup.setup_logger()
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)

warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("matplotlib").setLevel(logging.WARNING)

from utils import FileType, Instance


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
    return sorted(instances, key=lambda x: x.end_time)


def append_dummy_points(times, counts, last_time):
    """
    Append dummy points to the times and counts lists.
    :param times:
    :param counts:
    :param last_time:
    :return:
    """
    times.append(last_time)
    times.append(last_time)
    last_count = counts[-1] if counts else 0
    counts.append(last_count)
    counts.append(last_count)
    return times, counts


def convert_to_relative_times_hours(times, reference_time):
    return [(t - reference_time).total_seconds() / 3600 for t in times]


import os
import matplotlib.pyplot as plt


def plot_cumulative_counts(relative_times, cumulative_counts, max_end_time,
                           min_start_time, save_dir, filename="cumulative_interruptions.png"):
    plt.figure(figsize=(10, 6))
    plt.plot(relative_times, cumulative_counts, linestyle='-', marker='', color='b')
    plt.xlabel('Time (hours)', fontsize=20, fontweight='bold')
    plt.ylabel('Cumulative # of interruptions', fontsize=20, fontweight='bold')

    # plt.title('Cumulative number of interruptions')

    max_end_time_hours = (max_end_time - min_start_time).total_seconds() / 3600
    padding_hours = 5

    plt.xlim([0, max_end_time_hours + padding_hours])
    plt.xticks(range(0, int(max_end_time_hours + padding_hours) + 1, 5))
    plt.grid(True)

    # Set the y-axis to only show integer values
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))

    # Set tick size
    plt.tick_params(axis='both', which='major', labelsize=12)

    # Add tight layout
    plt.tight_layout()

    # Save the plot to a file
    if save_dir:
        # Ensure the directory exists
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)
        plt.savefig(save_path)
        print(f"Plot saved at {save_path}")

    try:
        plt.show()
    except Exception as e:
        print(f"Unable to show plot due to error: {str(e)}")


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

    complete_information = loaded_distributions[FileType.COMPLETE.value]
    max_end_time = complete_information.get('global_max_end_time')

    interruption_information = loaded_distributions[FileType.INTERRUPTION.value]
    min_start_time = interruption_information.get('global_min_start_time')
    instances = interruption_information['instances'].values()
    instances_sorted = sort_instances_by_end_time(instances)

    logger.debug(f"min_start_time: {min_start_time}")
    logger.debug(f"max_start_time: {max_end_time}")

    cumulative_counts = list(range(1, len(instances_sorted) + 1))
    logger.debug(f"cumulative_counts: {cumulative_counts}")
    interruption_times = [instance.end_time for instance in instances_sorted]
    logger.debug("First 3 interruption times:")
    logger.debug(interruption_times[:3])

    relative_times_hours = convert_to_relative_times_hours(interruption_times, min_start_time)

    # plot_cumulative_counts(relative_times_hours, cumulative_counts, max_end_time, min_start_time, selected_dir_path)
    if file_to_use == "filtered_distributions.pkl":
        plot_cumulative_counts(relative_times_hours, cumulative_counts, max_end_time, min_start_time,
                               selected_dir_path)

    elif file_to_use == "filtered_distributions_with_filled_complete_bucket.pkl":
        plot_cumulative_counts(relative_times_hours, cumulative_counts, max_end_time, min_start_time,
                               selected_dir_path, filename="cumulative_interruptions_with_filled_complete_bucket.png")


if __name__ == "__main__":
    main()
