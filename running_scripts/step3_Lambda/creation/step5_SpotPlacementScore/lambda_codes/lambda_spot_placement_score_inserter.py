"""
This lambda function is used to update the spot placement score table.
"""
import configparser
import os
import pickle
import pprint

import boto3

# Constants
FOLDER_NAME = './'  # Change to current directory since pickle files are in the Lambda package
OPTIMIZED_QUERIES_FILE = 'optimized_queries.pkl'
AZ_MAPPING_FILE = 'az_id_to_name_mapping.pkl'
DYNAMODB_TABLE_NAME = 'SpotPlacementScoreTable'

config = configparser.ConfigParser()
config.read('./conf.ini')
INSTANCE_TYPE = config.get('settings', 'instance_type')

config = configparser.ConfigParser()
config.read('./conf.ini')

region_for_db = config.get('settings', 'Region_DynamoForSpotPlacementScore')
dynamodb = boto3.resource('dynamodb', region_name=region_for_db)


def load_pickle(filename):
    """Load data from a pickle file."""
    filepath = os.path.join(FOLDER_NAME, filename)
    with open(filepath, 'rb') as file:
        return pickle.load(file)


def get_sps(optimized_queries):
    """Fetches spot placement scores for given queries."""
    session = boto3.session.Session()
    ec2 = session.client('ec2', region_name='us-east-1')

    sps_results = []
    for query in optimized_queries:
        response = ec2.get_spot_placement_scores(
            InstanceTypes=[INSTANCE_TYPE],
            TargetCapacity=1,
            SingleAvailabilityZone=True,
            RegionNames=list(query.keys())
        )
        sps_results.extend(
            {
                'InstanceType': INSTANCE_TYPE,
                'Region': info['Region'],
                'AvailabilityZoneId': info['AvailabilityZoneId'],
                'SPS': int(info['Score']),
            }
            for info in response['SpotPlacementScores']
        )
    return sps_results


def lambda_handler(event, context):
    optimized_queries = load_pickle(filename=OPTIMIZED_QUERIES_FILE)
    az_id_to_name = load_pickle(filename=AZ_MAPPING_FILE)

    # Print optimized queries
    pprint.pprint(optimized_queries)
    pprint.pprint(az_id_to_name)

    # Sanity Check
    total_values = sum(sum(query.values()) for query in optimized_queries)
    print(f"Total values in optimized queries: {total_values}")

    sps_results = get_sps(optimized_queries)

    # Map AvailabilityZoneId to its name
    for result in sps_results:
        result['availability_zone'] = az_id_to_name.get(result['AvailabilityZoneId'])

    # Print the results
    pprint.pprint(sps_results)

    # Insert the results into DynamoDB
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    for item in sps_results:
        table.put_item(Item=item)

    return {
        'statusCode': 200,
        'body': 'Process Completed'
    }
