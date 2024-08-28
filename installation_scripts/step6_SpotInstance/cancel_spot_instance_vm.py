import configparser

import boto3

inst_id = None

import re

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


# Initialize the parser and read the ini file
config = configparser.ConfigParser()
conf_file_path = find_config_file()
config_path = str(conf_file_path)
config.read(config_path)
complete_bucket_name = config.get('settings', 'complete_s3_bucket_name')
interrupt_s3_bucket_name = config.get('settings', 'interrupt_s3_bucket_name')
sleep_time = int(config.get('settings', 'sleep_time'))
number_of_spot_instances = int(config.get('settings', 'number_of_spot_instances'))
regions = [region.strip() for region in config.get('settings', 'regions_to_use').split(',')]
instance_type = config.get('settings', 'instance_type')

s3 = boto3.resource('s3')
s3_client = boto3.client('s3')


def extract_value(pattern, content):
    return match[1] if (match := re.search(pattern, content)) else None


def get_aws_credentials_from_file(filename='credentials.txt'):
    with open(filename, 'r') as f:
        content = f.read()

    aws_access_key_id_pattern = r'export AWS_ACCESS_KEY_ID="([^"]+)"'
    aws_secret_access_key_pattern = r'export AWS_SECRET_ACCESS_KEY="([^"]+)"'
    aws_session_token_pattern = r'export AWS_SESSION_TOKEN="([^"]+)"'

    return {
        'AWS_ACCESS_KEY_ID': extract_value(aws_access_key_id_pattern, content),
        'AWS_SECRET_ACCESS_KEY': extract_value(
            aws_secret_access_key_pattern, content
        ),
        'AWS_SESSION_TOKEN': extract_value(aws_session_token_pattern, content),
    }


# Usage example:
aws_credentials = get_aws_credentials_from_file()


def cancel_spot_requests_and_terminate_instances(region_name):
    ec2 = boto3.client('ec2', region_name=region_name)

    # Fetch all active/open spot instance requests
    spot_requests = ec2.describe_spot_instance_requests(
        Filters=[{
            'Name': 'state',
            'Values': ['open', 'active']
        }]
    )['SpotInstanceRequests']

    if not spot_requests:
        print(f"No spot instance requests found for region {region_name}.")
        return

    request_ids = [request['SpotInstanceRequestId'] for request in spot_requests]

    # Extract the instance IDs of the spot requests to terminate those instances
    instance_ids = [request['InstanceId'] for request in spot_requests if 'InstanceId' in request]

    # Cancel spot instance requests
    ec2.cancel_spot_instance_requests(SpotInstanceRequestIds=request_ids)
    print(f"Canceled {len(request_ids)} spot instance requests in {region_name}.")

    # Terminate instances associated with the spot requests
    if instance_ids:
        ec2.terminate_instances(InstanceIds=instance_ids)
        print(f"Terminated {len(instance_ids)} instances associated with spot requests in {region_name}.")


def main():
    for region in regions:
        cancel_spot_requests_and_terminate_instances(region)


if __name__ == "__main__":
    main()
