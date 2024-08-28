"""
Single region deployment script

This script is used to copy the 'conf.ini' file to the lambda_codes directory.
"""

import shutil
from pathlib import Path


def find_config_file(filename='conf.ini'):
    current_dir = Path(__file__).resolve().parent
    while current_dir != current_dir.parent:
        config_file = current_dir / filename
        if config_file.is_file():
            return config_file
        current_dir = current_dir.parent
    return None


conf_file_path = find_config_file()

if conf_file_path:
    source_file = str(conf_file_path)  # Convert Path object to string for shutil
    destination_directory = 'lambda_codes'

    # Debug print
    print(f"Attempting to copy '{source_file}' to '{destination_directory}'")

    # Ensure the destination directory exists, create if not
    dest_path = Path(destination_directory)
    dest_path.mkdir(parents=True, exist_ok=True)

    # Additional check to confirm directory creation (for debugging)
    if not dest_path.is_dir():
        print(f"Failed to create or find the directory: {destination_directory}")
    else:
        shutil.copy(source_file, destination_directory)
        print(f"File '{source_file}' has been successfully copied to directory '{destination_directory}'.")
else:
    print("Configuration file 'conf.ini' not found.")
