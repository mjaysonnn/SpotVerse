""" Download all contents of an S3 bucket to a local folder. """
import configparser
import os
from pathlib import Path
import boto3


def find_config_file(filename='conf.ini'):
    """ Find the configuration file in the parent directories of the current file. """
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

# Fetch configurations
complete_bucket_name = config.get('settings', 'complete_s3_bucket_name')
interrupt_s3_bucket_name = config.get('settings', 'interrupt_s3_bucket_name')

# Display fetched bucket names
print(f"complete_bucket_name: {complete_bucket_name}")
print(f"interrupt_bucket_name: {interrupt_s3_bucket_name}")


class S3Downloader:
    """
    Class to download all contents of an S3 bucket to a local folder.
    """

    def __init__(self, aws_region):
        self.s3_client = boto3.client('s3', region_name=aws_region)

    def download_bucket(self, bucket_name):
        """
        Download all contents of an S3 bucket to a folder in the 'data' directory named after the bucket.

        :param bucket_name: str, Name of the S3 bucket.
        """
        # Ensure the 'data' folder exists
        data_folder = os.path.join(os.getcwd(), 'data')
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)

        # Set the local folder path within the 'data' folder
        local_folder = os.path.join(data_folder, bucket_name)

        if not os.path.exists(local_folder):
            os.makedirs(local_folder)

        objects = self.s3_client.list_objects(Bucket=bucket_name)

        if 'Contents' not in objects:
            print(f"No objects available in bucket: {bucket_name}")
            return

        for obj in objects['Contents']:
            file_key = obj['Key']
            file_local_path = os.path.join(local_folder, file_key)

            # Ensure local folder structure exists
            if '/' in file_key:
                file_folder = os.path.dirname(file_local_path)
                os.makedirs(file_folder, exist_ok=True)

            # Download the file
            self.s3_client.download_file(bucket_name, file_key, file_local_path)


# Usage
aws_region = 'us-east-1'  # If you made bucket in a different region, change this

# Initialize downloader
downloader = S3Downloader(aws_region)

# Download bucket contents
downloader.download_bucket(complete_bucket_name)
downloader.download_bucket(interrupt_s3_bucket_name)
