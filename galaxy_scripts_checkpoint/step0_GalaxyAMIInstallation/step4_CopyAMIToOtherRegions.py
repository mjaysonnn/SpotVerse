import configparser
from pathlib import Path

import boto3


# This script is designed to copy an Amazon Machine Image (AMI) from a specified source region
# to multiple target regions. After copying, it saves the AMI IDs for each region in a file
# named `ami_ids.txt`, which will be used later for deploying Lambda functions and EC2 instances.

def copy_ami_to_regions(source_ami_id, source_region, target_regions):
    """
    Copy an AMI from the source region to the specified target regions.

    :param source_ami_id: The ID of the AMI to copy.
    :param source_region: The region where the source AMI is located.
    :param target_regions: A list of regions to copy the AMI to.
    :return: A dictionary mapping target region names to new AMI IDs.
    """
    copied_ami_dict = {}
    for region in target_regions:
        try:
            print(f"Copying AMI {source_ami_id} from {source_region} to {region}")
            client = boto3.client('ec2', region_name=region)
            response = client.copy_image(
                SourceRegion=source_region,
                SourceImageId=source_ami_id,
                Name=f"Copied from {source_region} - {source_ami_id}",
                Description=f"AMI copied from {source_region} - {source_ami_id}"
            )

            copied_ami_id = response['ImageId']
            copied_ami_dict[region] = copied_ami_id
            print(f"Successfully copied AMI to {region}. New AMI ID: {copied_ami_id}")
        except Exception as e:
            print(f"Error copying AMI to {region}: {e}")

    return copied_ami_dict


# ====================== MAIN =================

# The script assumes the `conf.ini` file is in the same directory as this script.
config_path = Path(__file__).resolve().parent.parent / 'conf.ini'
if not config_path.is_file():
    raise FileNotFoundError("Config file not found. Please ensure conf.ini is in the same directory as the script.")

config = configparser.ConfigParser()
config.read(str(config_path))

# Set source region
source_region = "us-east-1"  # Replace this with your actual source region

# Manually specify the source AMI ID
source_ami_id = "ami-082f7792a68d31ded"  # Replace this with your actual AMI ID

# Extract the 'regions' entry from the 'settings' section
regions_string = config.get('settings', 'regions_to_use')

# Convert the comma-separated string to a list
target_regions = [region.strip() for region in regions_string.split(',')]

# Remove the source region from the target regions list if it's included
target_regions = [region for region in target_regions if region != source_region]

print(f"Copying AMI {source_ami_id} from {source_region} to regions: {target_regions}")

# Copy the AMI to the target regions
copied_amis = copy_ami_to_regions(source_ami_id, source_region, target_regions)
print("Copied AMI IDs:", copied_amis)

# Save the source AMI ID and copied AMI IDs to a file in the same directory
copied_ami_ids_file = Path(__file__).parent / 'ami_ids.txt'
with open(copied_ami_ids_file, 'w') as f:
    # Write the source AMI ID
    f.write(f"{source_region} {source_ami_id}\n")

    # Write the copied AMI IDs
    for region, ami_id in copied_amis.items():
        f.write(f"{region} {ami_id}\n")

# This `ami_ids.txt` file will be used later for deploying Lambda functions and EC2 instances.
print(
    f"Source AMI ID and copied AMI IDs have been saved to '{copied_ami_ids_file}' in the same directory as the script")
print(f"Give some time for the AMIs to be fully copied before proceeding with the next steps.")
