"""
Single region deployment script

This script is used to create S3 buckets for the experiment.
S3 Buckets are used for storing spot instances that are open, successful or failed.
The bucket names are saved to ../conf.ini.

"""
import configparser
import random
from pathlib import Path

import boto3


class CaseSensitiveConfigParser(configparser.ConfigParser):
    def optionxform(self, optionstr):
        return optionstr


def initialize_s3_client():
    """
    Initialize an S3 client.
    """
    return boto3.client('s3')


def generate_bucket_name(prefix, experiment_region='us-east-1'):
    """
    Generate a unique bucket name.
    """
    return f"{prefix}-{random.randint(1000, 9999)}-{experiment_region}"


def create_bucket(s3_client, bucket_name, region):
    """
    Create a bucket with versioning enabled.
    """
    try:
        if region == 'us-east-1':  # 'us-east-1' does not require LocationConstraint
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )

        # Enable versioning for the created bucket
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )

        # Creating the necessary folders for tracking spot requests
        folders = ['open', 'successful', 'failed']
        for folder in folders:
            s3_client.put_object(Bucket=bucket_name, Key=f"{folder}/")

        print(
            f"Bucket {bucket_name} created successfully with versioning enabled and folders set up in region {region}.")
    except Exception as e:
        print(f"Error creating bucket {bucket_name}. Error: {e}")
        exit(1)


def save_to_config(config_path, spot_tracking_bucket_name, region):
    """
    Save the bucket name to ../conf.ini.
    """
    config = CaseSensitiveConfigParser()
    config.read(config_path)

    if not config.has_section('settings'):
        config.add_section('settings')

    config['settings']['spot_tracking_s3_bucket_name'] = spot_tracking_bucket_name

    with open(config_path, 'w') as configfile:
        config.write(configfile)
    print(f"Bucket name {spot_tracking_bucket_name} saved to {config_path}.")


def get_access_key_id():
    session = boto3.Session(profile_name='default')
    credentials = session.get_credentials()
    return credentials.access_key


def get_regions_from_config(config):
    """
    Get the list of regions from the config.
    """
    regions_str = config.get('settings', 'regions')
    return [region.strip() for region in regions_str.split(',')]


def display_and_confirm_access_key():
    actual_access_key = get_access_key_id()
    print(f"Access Key ID: {actual_access_key}")
    input("Press Enter to continue...")


def load_configurations(config_path):
    config = configparser.ConfigParser()
    config.read(config_path)
    return config


def print_details(default_region, experiment_default_region):
    print(f"Default region: {default_region}")
    print(f"Experiment default region: {experiment_default_region}")


def create_spot_tracking_bucket(default_region, experiment_default_region):
    print(f"Creating bucket for region: {default_region}")
    bucket_name = generate_bucket_name("mj-spotrequestcheck", experiment_default_region)
    s3_client = initialize_s3_client()
    create_bucket(s3_client, bucket_name, default_region)
    return bucket_name


def save_bucket_name_to_config(config_path, bucket_name, default_region):
    # Assuming that save_to_config has been modified to accept bucket_name and default_region as parameters
    save_to_config(config_path, bucket_name, default_region)


def find_config_file(filename='conf.ini'):
    current_dir = Path(__file__).resolve().parent
    while current_dir != current_dir.parent:
        config_file = current_dir / filename
        if config_file.is_file():
            print(f"Config file found at {config_file}")
            return config_file
        current_dir = current_dir.parent
    return None


def main():
    """
    Main function to set up S3 buckets for spot tracking.
    """
    # Display AWS Access Key ID and wait for user confirmation
    display_and_confirm_access_key()

    # Load configurations from the specified path
    conf_file_path = find_config_file()
    config_path = str(conf_file_path)
    config = load_configurations(config_path)

    # Get default and experiment regions
    default_region = "us-east-1"
    experiment_default_region = config.get('settings', 'suffix_for_s3')

    # Print details
    print_details(default_region, experiment_default_region)

    # Generate bucket name and create the bucket in the specified region
    spot_tracking_bucket_name = create_spot_tracking_bucket(default_region, experiment_default_region)

    # Save the generated bucket name to configuration
    save_bucket_name_to_config(config_path, spot_tracking_bucket_name, default_region)


if __name__ == "__main__":
    main()
