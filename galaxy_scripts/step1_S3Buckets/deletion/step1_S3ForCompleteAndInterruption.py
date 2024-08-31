import configparser
import boto3
from botocore.exceptions import ClientError


class CaseSensitiveConfigParser(configparser.ConfigParser):
    def optionxform(self, optionstr):
        return optionstr


def initialize_s3_client(region_name):
    """
    Initialize an S3 client.
    :param region_name: AWS region name
    """
    return boto3.client('s3', region_name=region_name)


def delete_all_objects(s3_client, bucket_name):
    """
    Delete all objects (including all versions and delete markers) in a bucket.
    :param s3_client: Initialized S3 client
    :param bucket_name: Name of the bucket
    """
    print(f"Deleting all objects from {bucket_name}")

    try:
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

    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            print(f"Bucket {bucket_name} does not exist. Skipping deletion.")
        else:
            print(f"Error occurred while deleting objects from {bucket_name}. Error: {e}")
            raise e


def delete_bucket(s3_client, bucket_name):
    """
    Delete a bucket.
    :param s3_client: Initialized S3 client
    :param bucket_name: Name of the bucket
    """
    try:
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"Bucket {bucket_name} deleted successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            print(f"Bucket {bucket_name} does not exist. Skipping deletion.")
        else:
            print(f"Error deleting bucket {bucket_name}. Error: {e}")
            raise e


def load_from_config(config_path):
    """
    Load the bucket names from ../conf.ini.
    :param config_path: Path to the config file
    :return: dictionary of bucket names
    """
    config = CaseSensitiveConfigParser()
    config.read(config_path)

    if not config.has_section('settings'):
        raise ValueError("Config file does not contain a 'settings' section")

    return {
        'interrupt': config.get('settings', 'interrupt_s3_bucket_name'),
        'complete': config.get('settings', 'complete_s3_bucket_name'),
    }


def load_region_from_config(config_path):
    """
    Load the AWS region from ../conf.ini.
    :param config_path: Path to the config file
    :return: AWS region as string
    """
    config = CaseSensitiveConfigParser()
    config.read(config_path)

    if not config.has_section('settings'):
        raise ValueError("Config file does not contain a 'settings' section")

    return config.get('settings', 'region', fallback='us-east-1')


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


def main():
    """
    Main function.
    """
    conf_file_path = find_config_file()
    config_path = str(conf_file_path)

    region = "us-east-1"  # Assuming us-east-1 as the default region
    bucket_names = load_from_config(config_path)

    s3_client = initialize_s3_client(region)

    for bucket in bucket_names.values():
        # Confirmation prompt
        user_input = input(f"Do you really want to delete {bucket}? [y/N]: ")

        if user_input.lower() == 'y':
            delete_all_objects(s3_client, bucket)
            delete_bucket(s3_client, bucket)
        else:
            print(f"Skipping deletion of {bucket}")


if __name__ == "__main__":
    main()
