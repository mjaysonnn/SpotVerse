import configparser
from pathlib import Path

import boto3


class CaseSensitiveConfigParser(configparser.ConfigParser):
    def optionxform(self, optionstr):
        return optionstr


def load_from_config(config_path):
    """
    Load the bucket names from ../conf.ini.
    :param config_path:
    :return: dictionary of bucket names
    """
    config = CaseSensitiveConfigParser()
    config.read(config_path)

    if not config.has_section('settings'):
        raise ValueError("Config file does not contain a 'settings' section")

    return config.get('settings', 'lambda_deployment_bucket_name'),


def find_config_file(filename='conf.ini'):
    current_dir = Path(__file__).resolve().parent
    while current_dir != current_dir.parent:
        config_file = current_dir / filename
        if config_file.is_file():
            print(f"Config file found at {config_file}")
            return config_file
        current_dir = current_dir.parent
    return None


conf_file_path = find_config_file()
config_path = str(conf_file_path)
lambda_deployment_bucket_name = load_from_config(config_path)

# Initialize a session using Amazon S3
s3 = boto3.client('s3')

# List all bucket names starting with specified prefix
buckets = [bucket['Name'] for bucket in s3.list_buckets()['Buckets']
           if bucket['Name'].startswith(lambda_deployment_bucket_name)]

print(f"Found {len(buckets)} buckets to delete.")

# Iterate over each bucket
for bucket in buckets:
    print(f"Processing bucket: {bucket}")

    # Delete all object versions
    print(f"Listing and deleting object versions for bucket {bucket}...")
    versions = s3.list_object_versions(Bucket=bucket).get('Versions', [])
    for version in versions:
        key = version['Key']
        version_id = version['VersionId']
        s3.delete_object(Bucket=bucket, Key=key, VersionId=version_id)

    # Delete all delete markers
    print(f"Listing and deleting delete markers for bucket {bucket}...")
    delete_markers = s3.list_object_versions(Bucket=bucket).get('DeleteMarkers', [])
    for marker in delete_markers:
        key = marker['Key']
        version_id = marker['VersionId']
        s3.delete_object(Bucket=bucket, Key=key, VersionId=version_id)

    # Delete the bucket
    print(f"Deleting the bucket {bucket}...")
    s3.delete_bucket(Bucket=bucket)

    print(f"Bucket {bucket} processed.")
    print("---------------------------------------------------")
