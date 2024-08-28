"""Single Region AMI Finder"""

import boto3


def get_ami_ids_for_all_regions(description):
    """
    Fetch AMI IDs across all AWS regions for AMIs matching the given description.

    :param description: The description of the AMI to search for.
    :return: A dictionary mapping region names to AMI IDs.
    """
    ec2_client = boto3.client('ec2', region_name='us-east-1')

    # Fetch all available regions
    print("Fetching available regions...")
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
    print(f"Found regions: {regions}")

    ami_dict = {}
    for region in regions:
        try:
            print(f"Checking AMI in region: {region}")
            client = boto3.client('ec2', region_name=region)
            response = client.describe_images(Owners=['amazon'],
                                              Filters=[{'Name': 'description', 'Values': [description]}])

            # Check if we found an AMI for the current region
            if response['Images']:
                ami_dict[region] = response['Images'][0]['ImageId']
            else:
                print(f"No AMI found for '{description}' in {region}.")
        except Exception as e:
            print(f"Error checking AMI in {region}: {e}")

    return ami_dict


# Example usage
description = "Amazon Linux 2023 AMI 2023.3.20240312.0 x86_64 HVM kernel-6.1"  # This could change in the future

ami_ids = get_ami_ids_for_all_regions(description)
print("AMI IDs found:", ami_ids)

print("AMI IDs found for the regions:")
for region, ami_id in ami_ids.items():
    print(f"{region}: {ami_id}")

# Save ami_ids to a file
ami_ids_file = 'lambda_codes/ami_ids.txt'
with open(ami_ids_file, 'w') as f:
    for region, ami_id in ami_ids.items():
        f.write(f"{region} {ami_id}\n")

print(f"AMI IDs have been saved to '{ami_ids_file}'")
