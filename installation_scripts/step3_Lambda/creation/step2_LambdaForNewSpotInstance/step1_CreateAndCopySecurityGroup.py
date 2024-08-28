# Multi-Region Security Group Creator

import configparser

import boto3
import botocore


def get_existing_security_group_id(region_name, group_name):
    """Check if a security group with the specified name exists in the region."""
    client = boto3.client('ec2', region_name=region_name)
    try:
        response = client.describe_security_groups(GroupNames=[group_name])
        if response and 'SecurityGroups' in response and len(response['SecurityGroups']) > 0:
            return response['SecurityGroups'][0]['GroupId']
    except botocore.exceptions.ClientError as e:
        # Group not found
        if e.response['Error']['Code'] == 'InvalidGroup.NotFound':
            return None
        else:
            raise
    return None


def create_security_group_with_rules(region_name, group_name, description, output_file):
    """Create a security group with specified inbound and outbound rules."""
    client = boto3.client('ec2', region_name=region_name)

    if existing_sg_id := get_existing_security_group_id(
            region_name, group_name
    ):
        print(f"Security Group {existing_sg_id} already exists in {region_name}.")
        # Write the region and security group ID to the file
        with open(output_file, 'a') as f:
            f.write(f"{region_name} {existing_sg_id}\n")
        return existing_sg_id

    # Create the security group
    response = client.create_security_group(GroupName=group_name, Description=description)
    sg_id = response['GroupId']
    print(f"Security Group {sg_id} created in {region_name}.")

    # Write the region and security group ID to the file
    with open(output_file, 'a') as f:
        f.write(f"{region_name} {sg_id}\n")

    # Define the inbound rules
    ip_permissions = [
        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        {'IpProtocol': 'tcp', 'FromPort': 8080, 'ToPort': 8080, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
    ]

    # Authorize the inbound rules
    client.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=ip_permissions)
    print(f"Inbound rules set for Security Group {sg_id} in {region_name}.")

    # Define the outbound rules
    egress_permissions = [
        {'IpProtocol': '-1', 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
    ]

    # Try to authorize the outbound rules, but handle duplicates gracefully
    try:
        client.authorize_security_group_egress(GroupId=sg_id, IpPermissions=egress_permissions)
        print(f"Outbound rules set for Security Group {sg_id} in {region_name}.")
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'InvalidPermission.Duplicate':
            print(f"Outbound rule already exists for Security Group {sg_id} in {region_name}.")
        else:
            # Raise the exception if it's not due to a duplicate rule.
            raise

    return sg_id


def copy_security_group_to_regions(source_region, dest_regions, sg_id, group_name, description, output_file):
    for region in dest_regions:
        create_security_group_with_rules(region, group_name, description, output_file)
        print(f"Security Group {group_name} copied to {region}.")


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


#  ====================== MAIN =================

# Example usage
source_region = 'us-east-1'

# Initialize the parser and read the ini file
config = configparser.ConfigParser()

conf_file_path = find_config_file()
config_path = str(conf_file_path)
config.read(config_path)

# Extract the 'regions' entry from the 'settings' section
regions_string = config.get('settings', 'regions_to_use')

# Convert the comma-separated string to a list
destination_regions = [region.strip() for region in regions_string.split(',') if region.strip() != 'us-east-1']

print(f"Destination regions: {destination_regions}")

group_name = 'Galaxy-SG'
description = 'Security group with inbound ports 22 and 8080, and all outbound ports open for all IPv4s'
output_file = 'lambda_codes/security_group_ids.txt'

# Clear the file content before writing to it
print(f"Clearing the content of {output_file} before writing to it")
with open(output_file, 'w') as f:
    f.write("")

print(f"Creating security group in the source region: {source_region}")
sg_id = create_security_group_with_rules(source_region, group_name, description, output_file)
print(f"Created security group with ID: {sg_id}")

print("Copying security group to destination regions")
copy_security_group_to_regions(source_region, destination_regions, sg_id, group_name, description, output_file)

print("Script execution completed.")
