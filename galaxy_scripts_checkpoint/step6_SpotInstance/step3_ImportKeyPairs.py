import boto3
import os
import configparser
from pathlib import Path

def import_key_pair_to_region(key_name, key_file_path, region_name):
    """
    Import an existing public key as a key pair to a specific AWS region.

    :param key_name: The name of the key pair in AWS.
    :param key_file_path: The local path to the public key file.
    :param region_name: The AWS region where the key pair should be imported.
    """
    # Read the public key file
    try:
        with open(key_file_path, 'r') as key_file:
            public_key_material = key_file.read()
    except FileNotFoundError:
        print(f"Error: The file '{key_file_path}' was not found.")
        return
    except Exception as e:
        print(f"Error reading the file '{key_file_path}': {str(e)}")
        return

    # Create a session using Boto3 for the specific region
    session = boto3.Session(region_name=region_name)
    ec2 = session.client('ec2')

    try:
        # Import the key pair to AWS in the specific region
        ec2.import_key_pair(KeyName=key_name, PublicKeyMaterial=public_key_material)
        print(f"Key pair '{key_name}' imported successfully to region '{region_name}'.")
    except ec2.exceptions.ClientError as e:
        print(f"Error importing key pair to region '{region_name}': {str(e)}")

if __name__ == "__main__":
    # Define the path to the conf.ini file located in the upper parent directory
    config_path = Path(__file__).resolve().parent.parent / 'conf.ini'
    if not config_path.is_file():
        raise FileNotFoundError("Config file not found. Please ensure conf.ini is in the upper parent directory.")

    # Load the configuration file
    config = configparser.ConfigParser()
    config.read(str(config_path))

    # Extract the 'regions_to_use' entry from the 'settings' section
    regions_string = config.get('settings', 'regions_to_use')
    regions_to_use = [region.strip() for region in regions_string.split(',') if region.strip()]

    # Define the key pair name and key file path
    key_name = "mjay_m1"  # The desired name for the key pair in AWS
    key_file_path = os.path.expanduser("~/.ssh/mjay_m1.pub")  # Path to the public key file

    # Import the key pair into each region specified in the 'regions_to_use'
    for region in regions_to_use:
        import_key_pair_to_region(key_name, key_file_path, region)
