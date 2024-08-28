import configparser
import json
import os
import subprocess
from decimal import Decimal

import boto3

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('SpotInterruptionRatioTable')

config = configparser.ConfigParser()
config.read('./conf.ini')
INSTANCE_TYPE = config.get('settings', 'instance_type')
print(f"INSTANCE_TYPE: {INSTANCE_TYPE}")

# Interruption mapping (reversed to transform label to numeric)
interruption_mapping = {
    ">20%": 1,
    "15-20%": 1.5,
    "10-15%": 2,
    "5-10%": 2.5,
    "<5%": 3
}


def download_file(url, local_filename):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename


# Function to change file permission to executable
def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2  # copy R bits to X
    os.chmod(path, mode)


def get_spotinfo():
    spotinfo_executable = '/opt/bin/spotinfo'

    command = [
        spotinfo_executable,
        '--type', INSTANCE_TYPE,
        '--region', 'all',
        '--output', 'json',
        '--sort', 'interruption'
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise Exception(f"Error executing spotinfo: {stderr.decode('utf-8')}")

    return json.loads(stdout)


def extract_relevant_info(data):
    results = []
    for entry in data:
        print(entry)
        label = entry['Range']['label']

        mapped_score = Decimal(interruption_mapping.get(label, 0))

        # Extract the spot price
        spot_price = entry.get('Price', 'Unknown')

        result = {
            'InstanceType': entry['Instance'],
            'Region': entry['Region'],
            'SavingsOverOnDemand': entry['Savings'],
            'Interruption_free_score': mapped_score or 'Unknown',
            'SpotPrice': Decimal(str(spot_price)) if spot_price != 'Unknown' else 'Unknown'

        }
        print(result)
        results.append(result)
    return results


def store_in_dynamodb(results):
    for item in results:
        table.put_item(Item=item)


def lambda_handler(event, context):
    data = get_spotinfo()
    if not data:
        return {
            'statusCode': 500,
            'body': 'Failed to get spotinfo data.'
        }

    results = extract_relevant_info(data)
    store_in_dynamodb(results)

    return {
        'statusCode': 200,
        'body': 'Data processed and stored successfully.'
    }
