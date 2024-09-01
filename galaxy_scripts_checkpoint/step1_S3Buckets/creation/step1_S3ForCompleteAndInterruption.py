#!/usr/bin/python3

"""
Single region deployment script

This script is used to create S3 buckets for the experiment.
S3 Buckets are used for storing spot instances that are complete or interrupted.
Also, Setting Lambda Deployment S3 Bucket Name.
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
    :param experiment_region:
    :param prefix:
    :param region:
    :return:
    """
    return f"{prefix}-{random.randint(1000, 9999)}-{experiment_region}"


def create_bucket(s3_client, bucket_name, region):
    """
    Create a bucket with versioning enabled.
    :param s3_client:
    :param bucket_name:
    :param region:
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

        print(f"Bucket {bucket_name} created successfully with versioning enabled in region {region}.")
    except Exception as e:
        print(f"Error creating bucket {bucket_name}. Error: {e}")
        exit(1)


def save_to_config(config_path, bucket_names):
    """
    Save the bucket names to ../conf.ini.
    :param config_path:
    :param bucket_names:
    """
    config = CaseSensitiveConfigParser()
    config.read(config_path)

    if not config.has_section('settings'):
        config.add_section('settings')

    print("Saving Below Information to conf.ini")
    print(f"Interrupt S3 Bucket Name: {bucket_names['interrupt']}")
    print(f"Complete S3 Bucket Name: {bucket_names['complete']}")
    print(f"Lambda Deployment S3 Bucket Name: {bucket_names['lambda_deployment']}")
    print(f"Lambda Deployment Name would later be used when making bucket in step3 in this folder.")

    config['settings']['interrupt_s3_bucket_name'] = bucket_names['interrupt']
    config['settings']['complete_s3_bucket_name'] = bucket_names['complete']
    config['settings']['lambda_deployment_bucket_name'] = bucket_names['lambda_deployment']

    with open(config_path, 'w') as configfile:
        config.write(configfile)
    print(f"Bucket names saved to {config_path}.")


def get_access_key_id():
    # Create a session using your default AWS CLI profile
    session = boto3.Session(profile_name='default')

    # Get the AWS credentials from the session
    credentials = session.get_credentials()

    return credentials.access_key


def display_and_confirm_access_key():
    actual_access_key = get_access_key_id()
    print(f"Access Key ID: {actual_access_key}")
    input("Press Enter to continue...")


def generate_bucket_names(experiment_default_region):
    prefixes = {
        'interrupt': "xx-interruption",
        'complete': "xx-complete",
        'lambda_deployment': "xx-lambda-codes"
    }
    return {key: generate_bucket_name(prefix, experiment_default_region) for key, prefix in prefixes.items()}


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
    Main function to set up S3 buckets and configurations.
    """
    # Display AWS Access Key ID and wait for user confirmation
    display_and_confirm_access_key()

    # Read configurations
    conf_file_path = find_config_file()
    config_path = str(conf_file_path)
    config = configparser.ConfigParser()
    config.read(config_path)

    default_region = "us-east-1" # it's okay to use us-east-1 as default region
    experiment_default_region = config.get('settings', 'suffix_for_s3')

    # Generate bucket names
    bucket_names = generate_bucket_names(experiment_default_region)

    s3_client = initialize_s3_client()

    # Create the required S3 buckets
    for key in ['interrupt', 'complete']:
        create_bucket(s3_client, bucket_names[key], default_region)

    # Save the generated bucket names to configuration
    save_to_config(config_path, bucket_names)


if __name__ == "__main__":
    main()
