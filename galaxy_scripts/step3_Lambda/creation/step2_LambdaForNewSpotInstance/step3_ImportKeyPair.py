# Multi-Region Key Pair Importer

import configparser
from pathlib import Path

import boto3


def find_config_file(filename='conf.ini'):
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

# Extract the 'regions' entry from the 'settings' section
regions_string = config.get('settings', 'regions_to_use')

# Convert the comma-separated string to a list
target_regions = [region.strip() for region in regions_string.split(',')]
print(f"Configured target regions: {target_regions}")


def import_key_pair_to_all_regions(key_name, public_key_material):
    # Import the public key to each of the target regions
    for region in target_regions:
        client = boto3.client('ec2', region_name=region)
        try:
            client.import_key_pair(KeyName=key_name, PublicKeyMaterial=public_key_material)
            print(f"Successfully imported key '{key_name}' to {region}")
        except client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidKeyPair.Duplicate':
                print(f"Key '{key_name}' already exists in {region}")
            else:
                print(f"Error importing key '{key_name}' to {region}: {e}")


key_name = "xxay_m1"
print(f"Reading public key material from /Users/xx/.ssh/{key_name}.pub...")
with open(f"/Users/xx/.ssh/{key_name}.pub", "r") as f:
    public_key_material = f.read()

print(f"Starting to import key '{key_name}' to the target regions...")
import_key_pair_to_all_regions(key_name, public_key_material)
print("Key import process completed.")
