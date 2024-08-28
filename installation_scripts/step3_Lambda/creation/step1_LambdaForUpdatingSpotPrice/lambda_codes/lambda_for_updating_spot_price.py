import configparser
from datetime import datetime, timedelta
from decimal import Decimal

import boto3

config = configparser.ConfigParser()
config.read('./conf.ini')

table_name = "SpotPriceCostTable"
region_for_db = config.get('settings', 'Region_DynamodbForSpotPrice')
dynamodb = boto3.resource('dynamodb', region_name=region_for_db)
table = dynamodb.Table(table_name)
instance_type = config.get('settings', 'instance_type')

print(f"Instance type: {instance_type}")


def lambda_handler(event, context):
    print("Lambda execution started")

    ec2_client_global = boto3.client('ec2')
    ec2_regions = [region['RegionName'] for region in ec2_client_global.describe_regions()['Regions']]
    print(f"Found EC2 regions: {ec2_regions}")

    # Calculate start time as 1 hour ago
    start_time = datetime.utcnow() - timedelta(hours=1)

    for region_name in ec2_regions:
        print(f"Processing region: {region_name}")
        ec2_client = boto3.client('ec2', region_name=region_name)

        paginator = ec2_client.get_paginator('describe_spot_price_history')
        page_iterator = paginator.paginate(
            InstanceTypes=[instance_type],
            ProductDescriptions=['Linux/UNIX'],
            StartTime=start_time
        )

        latest_prices = {}

        for page in page_iterator:
            for item in page['SpotPriceHistory']:
                az_value = item.get('AvailabilityZone', 'ALL_AZs')

                # If this AZ is not in our dictionary or if the timestamp is newer than the existing one
                if az_value not in latest_prices or item['Timestamp'] > latest_prices[az_value]['timestamp']:
                    latest_prices[az_value] = {
                        'timestamp': item['Timestamp'],
                        'price': Decimal(str(item['SpotPrice']))
                    }

        # Insert the latest prices into DynamoDB
        for az, details in latest_prices.items():
            print(f"Inserting/updating data for availability zone: {az} in region: {region_name}")

            table.put_item(
                Item={
                    'availability_zone': az,
                    'timestamp': details['timestamp'].strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'price': details['price'],
                    'region': region_name  # This will just be a regular attribute now
                }
            )

    print("Lambda execution completed")
    return "Lambda execution completed"
