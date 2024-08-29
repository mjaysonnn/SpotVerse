import pickle
import warnings

# Suppress warnings judiciously
warnings.filterwarnings("ignore", category=DeprecationWarning)
from directory_selector import select_subdirectory, load_data

import logging
from my_logger import LoggerSetup

logger = LoggerSetup.setup_logger()
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)


from utils import FileType, Instance

import matplotlib.pyplot as plt
import os


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


def append_max_end_time(times, max_end_time, max_datasets=40):
    while len(times) < max_datasets:
        times.append(max_end_time)
    return times[:max_datasets]


def convert_to_relative_times_hours(times, reference_time):
    return [(t - reference_time).total_seconds() / 3600 for t in times]


def plot_cumulative_completions(relative_times, cumulative_counts, max_end_time, min_start_time, save_dir,
                                filename="cumulative_completions.png"):
    """
    Plots and saves a graph of cumulative completions.
    """
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
    min_start_time = complete_information.get('global_min_start_time')
    max_end_time = complete_information.get('global_max_end_time')

    instances = complete_information['instances'].values()
    instances_sorted = sort_instances_by_end_time(instances)

    completion_times = [instance.end_time for instance in instances_sorted]
    completion_times = append_max_end_time(completion_times, max_end_time)

    cumulative_counts = list(range(1, len(completion_times) + 1))
    relative_times_hours = convert_to_relative_times_hours(completion_times, min_start_time)

    if file_to_use == "filtered_distributions.pkl":
        plot_cumulative_completions(relative_times_hours, cumulative_counts, max_end_time, min_start_time,
                                    selected_dir_path)

    elif file_to_use == "filtered_distributions_with_filled_complete_bucket.pkl":
        plot_cumulative_completions(relative_times_hours, cumulative_counts, max_end_time, min_start_time,
                                    selected_dir_path,
                                    filename="cumulative_completions_with_filled_complete_bucket.png")


if __name__ == "__main__":
    main()
