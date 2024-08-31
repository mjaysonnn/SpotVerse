import configparser
from pathlib import Path

import boto3


class CaseSensitiveConfigParser(configparser.ConfigParser):
    def optionxform(self, optionstr):
        return optionstr


def initialize_s3_client(region_name=None):
    """
    Initialize an S3 client.
    :param region_name: AWS region name
    """
    return boto3.client('s3', region_name=region_name)


def bucket_exists(s3_client, bucket_name):
    """
    Check if a specified bucket exists.
    """
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except:
        return False


def delete_all_objects(s3_client, bucket_name):
    """
    Delete all objects (including all versions and delete markers) in a bucket.
    :param s3_client: Initialized S3 client
    :param bucket_name: Name of the bucket
    """
    print(f"Deleting all objects from {bucket_name}")

    while True:
        # Retrieve all versions of every object within the bucket
        versioned_objects = s3_client.list_object_versions(Bucket=bucket_name)

        if 'Versions' in versioned_objects:
            for version in versioned_objects['Versions']:
                s3_client.delete_object(Bucket=bucket_name, Key=version['Key'], VersionId=version['VersionId'])

        # Handle delete markers separately
        if 'DeleteMarkers' in versioned_objects:
            for delete_marker in versioned_objects['DeleteMarkers']:
                s3_client.delete_object(Bucket=bucket_name, Key=delete_marker['Key'],
                                        VersionId=delete_marker['VersionId'])

        # If there are no versions or delete markers, break out of the loop
        if not versioned_objects.get('Versions') and not versioned_objects.get('DeleteMarkers'):
            break


def delete_bucket(s3_client, bucket_name):
    """
    Delete a bucket.
    :param s3_client: Initialized S3 client
    :param bucket_name: Name of the bucket
    """
    try:
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"Bucket {bucket_name} deleted successfully.")
    except Exception as e:
        print(f"Error deleting bucket {bucket_name}. Error: {e}")


def get_bucket_names_from_config(config, region):
    """
    Get bucket names for a given region from the config.
    """

    return config.get('settings', "spot_tracking_s3_bucket_name")


def get_regions_from_config(config):
    """
    Get the list of regions from the config.
    """
    regions_str = config.get('settings', 'regions')
    return [region.strip() for region in regions_str.split(',')]


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
    Main function.
    """
    conf_file_path = find_config_file()
    config_path = str(conf_file_path)

    config = CaseSensitiveConfigParser()
    config.read(config_path)

    # Get the list of regions from the config
    # all_regions = get_regions_from_config(config)
    # print(f"Regions: {all_regions}")

    all_regions = ["us-east-1"]

    for region in all_regions:
        print(f"Deleting bucket for region: {region}")

        # Get the bucket name for the current region from the config
        bucket_name = get_bucket_names_from_config(config, region)

        s3_client = initialize_s3_client(region)

        if not bucket_exists(s3_client, bucket_name):
            print(f"Bucket {bucket_name} does not exist in region {region}. Skipping.")
            continue

        # Confirmation prompt
        user_input = input(f"Do you really want to delete {bucket_name}? [y/N]: ")

        if user_input.lower() == 'y':

            # Delete all objects and then the bucket
            delete_all_objects(s3_client, bucket_name)
            delete_bucket(s3_client, bucket_name)
        else:
            print(f"Skipping deletion of {bucket_name}")


if __name__ == "__main__":
    main()
