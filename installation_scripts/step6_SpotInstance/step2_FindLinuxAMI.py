import configparser
import boto3
from pathlib import Path


def find_config_file(filename='conf.ini'):
    current_dir = Path(__file__).resolve().parent
    while current_dir != current_dir.parent:
        config_file = current_dir / filename
        if config_file.is_file():
            print(f"Config file found at {config_file}")
            return config_file
        current_dir = current_dir.parent
    return None


def get_ami_ids_for_selected_regions(description, regions):
    """
    Fetch AMI IDs across selected AWS regions for AMIs matching the given description.

    :param description: The description of the AMI to search for.
    :param regions: A list of regions to search in.
    :return: A dictionary mapping region names to AMI IDs.
    """
    ami_dict = {}
    for region in regions:
        try:
            print(f"Checking AMI in region: {region}")
            client = boto3.client('ec2', region_name=region)
            response = client.describe_images(Owners=['amazon'],
                                              Filters=[{'Name': 'description', 'Values': [description]}])

            # Check if we found an AMI for the current region
            if response['Images']:
                ami_id = response['Images'][0]['ImageId']
                print(f"Found AMI: {ami_id} in region: {region}")
                ami_dict[region] = ami_id
            else:
                print(f"No AMI found for '{description}' in {region}.")
        except Exception as e:
            print(f"Error checking AMI in {region}: {e}")

    return ami_dict


# ====================== MAIN =================

# Example usage
# make sure to check if  ami description is still valid
description = "Amazon Linux 2023 AMI 2023.5.20240819.0 x86_64 HVM kernel-6.1"  # Update this to match your exact need

# Initialize the parser and read the ini file
config = configparser.ConfigParser()

conf_file_path = find_config_file()
config_path = str(conf_file_path)
config.read(config_path)

# Extract the 'regions' entry from the 'settings' section
regions_string = config.get('settings', 'regions_to_use')

# Convert the comma-separated string to a list
selected_regions = [region.strip() for region in regions_string.split(',')]

print(f"Searching for AMI in regions: {selected_regions}")

ami_ids = get_ami_ids_for_selected_regions(description, selected_regions)
print("AMI IDs found:", ami_ids)

print("AMI IDs found for the regions:")
for region, ami_id in ami_ids.items():
    print(f"{region}: {ami_id}")

# Save ami_ids to a file
ami_ids_file = 'ami_ids.txt'
with open(ami_ids_file, 'w') as f:
    for region, ami_id in ami_ids.items():
        f.write(f"{region} {ami_id}\n")

print(f"AMI IDs have been saved to '{ami_ids_file}'")
