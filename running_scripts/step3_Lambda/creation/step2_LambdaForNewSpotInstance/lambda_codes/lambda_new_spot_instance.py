import base64
import configparser
import json
import os
import random
import re
import time
from datetime import datetime
from datetime import timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr

# Initialize the parser and read the ini file
config = configparser.ConfigParser()
config.read('./conf.ini')
regions_string = config.get('settings', 'regions_to_use')
target_regions = [region.strip() for region in regions_string.split(',')]

SLEEP_TIME_SPOT_REQUEST = 30  # seconds
complete_bucket_name = config.get('settings', 'complete_s3_bucket_name')
interrupt_s3_bucket_name = config.get('settings', 'interrupt_s3_bucket_name')
sleep_time = int(config.get('settings', 'sleep_time'))
number_of_spot_instances = 1
factor = Decimal(config.getfloat('settings', 'spot_price_factor'))
instance_type = config.get('settings', 'instance_type')
key_name = config.get('settings', 'key_name')
spot_status_s3_bucket_name = config.get('settings', 'spot_tracking_s3_bucket_name')
Region_DynamodbForSpotPrice = config.get('settings', 'Region_DynamodbForSpotPrice')
on_demand_price = float(config.get('settings', 'on_demand_price'))
Region_DynamoDBForSpotPlacementScore = config.get('settings', 'Region_DynamoForSpotPlacementScore')
Region_DynamoDBForStabilityScore = config.get('settings', 'Region_DynamoForSpotInterruptionRatio')

print(f"Configured target regions: {target_regions}")
print(f"target_regions: {target_regions}")
# print(f"Factor from conf.ini: {factor}")
print(f"sleep_time: {sleep_time}")
print(f"number_of_spot_instances: {number_of_spot_instances}")
print(f"instance_type: {instance_type}")
print(f"key_name: {key_name}")
print(f"complete_bucket_name: {complete_bucket_name}")
print(f"interrupt_bucket_name: {interrupt_s3_bucket_name}")
print("SLEEP_TIME_SPOT_REQUEST: ", SLEEP_TIME_SPOT_REQUEST)
print(f"spot_status_bucket_name: {spot_status_s3_bucket_name}")
print(f"Region_DynamodbForSpotPrice: {Region_DynamodbForSpotPrice}")
print(f"on_demand_price: {on_demand_price}")

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb', region_name=Region_DynamodbForSpotPrice)
table = dynamodb.Table('SpotPriceCostTable')
ec2_client = boto3.client('ec2')
region_for_lambda_env = os.environ['AWS_REGION']


def check_object_exists_in_s3(s3_client, bucket_name, object_key):
    try:
        s3_client.head_object(Bucket=bucket_name, Key=object_key)
        return True
    except Exception as e:
        return False


def extract_value(pattern, content):
    return match[1] if (match := re.search(pattern, content)) else None


def get_aws_credentials_from_file(filename='credentials.txt'):
    with open(filename, 'r') as f:
        content = f.read()

    aws_access_key_id_pattern = r'export AWS_ACCESS_KEY_ID="([^"]+)"'
    aws_secret_access_key_pattern = r'export AWS_SECRET_ACCESS_KEY="([^"]+)"'

    return {
        'AWS_ACCESS_KEY_ID': extract_value(aws_access_key_id_pattern, content),
        'AWS_SECRET_ACCESS_KEY': extract_value(aws_secret_access_key_pattern, content),
    }


def add_instance_id_to_s3(instance_id, s3_client, event):
    termination_time = event.get('time', None)
    region = event.get('region', 'N/A')

    try:

        # Fetch instance details
        ec2_client = boto3.client('ec2', region_name=region)
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        instance_details = response['Reservations'][0]['Instances'][0]

        availability_zone = instance_details['Placement']['AvailabilityZone']
        ec2_instance_type = instance_details['InstanceType']
        launch_time = instance_details['LaunchTime'].strftime('%Y-%m-%dT%H:%M:%SZ')  # Format launch time
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        # Get the current spot price for the instance type in its availability zone
        spot_price_response = ec2_client.describe_spot_price_history(
            InstanceTypes=[ec2_instance_type],
            AvailabilityZone=availability_zone,
            ProductDescriptions=['Linux/UNIX'],
            MaxResults=1
        )

        current_spot_price = spot_price_response['SpotPriceHistory'][0]['SpotPrice']

        # Prepare the data to be written to S3
        data = (
            f"Instance ID: {instance_id}\n"
            f"Region: {region}\n"
            f"Availability Zone: {availability_zone}\n"
            f"Instance Type: {ec2_instance_type}\n"
            f"Instance Launch Time: {launch_time}\n"
            f"Spot Interruption Warning Time: {termination_time}\n"
            f"Current Spot Price: {current_spot_price}"
        )

    except Exception as e:
        # In case of any exception, prepare data with instance_id, termination_time, resources, and region
        print(f"An error occurred: {str(e)}. Uploading Instance ID, Termination Time, Resources, and Region...")
        termination_time = event.get('time', 'N/A')
        resources = ', '.join(event.get('resources', []))
        data = (
            f"Instance ID: {instance_id}\n"
            f"Region: {region}\n"
            f"Spot Interruption Warning Time: {termination_time}\n"
            f"Resources: {resources}"
        )

    try:
        buckets = [bucket['Name'] for bucket in s3_client.list_buckets()['Buckets']]
        if interrupt_s3_bucket_name not in buckets:
            print(f"Bucket '{interrupt_s3_bucket_name}' does not exist. Creating it...")
            s3_client.create_bucket(Bucket=interrupt_s3_bucket_name)
            print(f"Bucket '{interrupt_s3_bucket_name}' created successfully.")
        else:
            print(f"Bucket '{interrupt_s3_bucket_name}' already exists.")

        object_key = f'{instance_id}.txt'
        s3_client.put_object(Bucket=interrupt_s3_bucket_name, Key=object_key, Body=data.encode('utf-8'))
        print("Data:", data)
        print(f"Uploaded instance details for {instance_id} to S3 bucket {interrupt_s3_bucket_name}.")

    except Exception as e:
        print(f"An error occurred during S3 operations: {str(e)}")


def get_values_from_file(filename):
    values = {}
    with open(f"./{filename}", 'r') as f:
        for line in f:
            key, value = line.strip().split(' ')
            values[key] = value
    return values


def generate_user_data_script(aws_credentials, sleep_time, complete_bucket_name):
    script = f"""#!/bin/bash

                # Exporting AWS credentials for use in subsequent AWS CLI commands
                export AWS_ACCESS_KEY_ID="{aws_credentials['AWS_ACCESS_KEY_ID']}"
                export AWS_SECRET_ACCESS_KEY="{aws_credentials['AWS_SECRET_ACCESS_KEY']}"

                # Initializing the log file to capture the output of this script
                echo "Starting script" >/var/log/user-data.log

                # Redirecting all stdout and stderr to the log file for debugging purposes
                exec > >(tee -a /var/log/user-data.log) 2>&1

                # Placeholder sleep command for testing purposes
                # You can remove or replace this line with actual script logic in production
                echo "Sleeping for {sleep_time} seconds..."
                sleep {sleep_time}

                # Retrieve the instance ID using the ec2-metadata command
                echo "Retrieving the instance ID using ec2-metadata..."
                INSTANCE_ID=$(ec2-metadata -i | cut -d " " -f 2)
                echo "Instance ID retrieved: $INSTANCE_ID"

                # Retrieve the Spot Instance Request ID associated with this instance
                SPOT_REQUEST_ID=$(aws ec2 describe-instances --instance-id $INSTANCE_ID --query "Reservations[0].Instances[0].SpotInstanceRequestId" --output text)
                echo "Spot Instance Request ID retrieved: $SPOT_REQUEST_ID"

                # Extract the region from the Availability Zone using ec2-metadata
                REGION=$(ec2-metadata -z | cut -d " " -f 2 | sed 's/.$//')
                echo "Region retrieved: $REGION"

                # Check if the specific file exists in the S3 bucket for spot instance interruptions
                CHECK_KEY="open/${{REGION}}|${{SPOT_REQUEST_ID}}.txt"
                echo "Checking if file $CHECK_KEY exists in bucket {spot_status_s3_bucket_name}..."
                if aws s3api head-object --bucket "{spot_status_s3_bucket_name}" --key "$CHECK_KEY" 2>/dev/null; then
                    echo "File $CHECK_KEY exists in bucket. No further action required."
                    aws s3api delete-object --bucket "{spot_status_s3_bucket_name}" --key "$CHECK_KEY"
                else
                    echo "File $CHECK_KEY does not exist in bucket {spot_status_s3_bucket_name}. Skipping..."
                fi

                # Retrieve instance details such as instance type, availability zone, and launch time
                INSTANCE_TYPE=$(ec2-metadata -t | cut -d " " -f 2)
                AVAILABILITY_ZONE=$(ec2-metadata -z | cut -d " " -f 2)
                LAUNCH_TIME=$(aws ec2 describe-instances \
                  --instance-id $INSTANCE_ID \
                  --query "Reservations[0].Instances[0].LaunchTime" \
                  --output text)
                # Fetch the current spot price for the instance type in the specific availability zone
                CURRENT_SPOT_PRICE=$(aws ec2 describe-spot-price-history \
                  --instance-types $INSTANCE_TYPE \
                  --availability-zone $AVAILABILITY_ZONE \
                  --product-descriptions "Linux/UNIX" \
                  --max-results 1 \
                  --query "SpotPriceHistory[0].SpotPrice" \
                  --output text)
                CURRENT_TIME=$(date --utc +'%Y-%m-%dT%H:%M:%S+00:00')

                # Write all the retrieved information to a temporary file
                echo "Instance ID: $INSTANCE_ID" > /tmp/instance_info.txt
                echo "Availability Zone: $AVAILABILITY_ZONE" >> /tmp/instance_info.txt
                echo "Instance Launch Time: $LAUNCH_TIME" >> /tmp/instance_info.txt
                echo "Current Time: $CURRENT_TIME" >> /tmp/instance_info.txt
                echo "Current Spot Price: $CURRENT_SPOT_PRICE" >> /tmp/instance_info.txt

                # Define the S3 object key as the instance ID followed by .txt
                KEY="$INSTANCE_ID.txt"

                # Check if the S3 bucket for completed instance information exists, create it if not
                echo "Checking if bucket {complete_bucket_name} exists..."
                if aws s3api head-bucket --bucket "{complete_bucket_name}" &>/dev/null; then
                  echo "Bucket {complete_bucket_name} exists"
                else
                  echo "Bucket {complete_bucket_name} does not exist. Creating..."
                  aws s3api create-bucket --bucket "{complete_bucket_name}"
                  echo "Bucket {complete_bucket_name} created."
                fi

                # Upload the instance information file to the S3 bucket
                echo "Uploading the file with the name $INSTANCE_ID.txt to the S3 bucket {complete_bucket_name}..."
                aws s3api put-object --bucket {complete_bucket_name} --key $KEY --body /tmp/instance_info.txt
                # Remove the temporary file after uploading
                rm -f /tmp/instance_info.txt
                echo "Upload completed. Please check the S3 bucket for the file."

                # Terminate the instance after completing all tasks
                echo "Terminating instance $INSTANCE_ID"
                aws ec2 terminate-instances --instance-ids $INSTANCE_ID

                """
    # Return the generated script, base64 encoded for use in the EC2 user data
    return base64.b64encode(script.encode()).decode()


def save_spot_request_to_s3(s3_client, bucket_name, folder, request_id, region, check_count=0):
    """
    Save the spot request ID to the specified folder in the bucket with region information in the filename.
    Include the check count in the object's metadata.
    """
    try:
        s3_key = f"{folder}/{region}|{request_id}.txt"
        metadata = {'check_count': str(check_count)}
        s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=request_id, Metadata=metadata)
        print(
            f"Spot request {request_id} (Region: {region}) saved to {folder} in S3 bucket {bucket_name} with check count {check_count}.")
    except Exception as e:
        print(
            f"Error saving spot request {request_id} (Region: {region}) to {folder} in S3 bucket {bucket_name}. Error: {e}")


def check_spot_request_and_save_open_request_to_s3(ec2_inst_client, request_id, region):
    """
    Waits for the spot instance request to be fulfilled and handles various states.
    """
    try:
        response = ec2_inst_client.describe_spot_instance_requests(SpotInstanceRequestIds=[request_id])
        state = response['SpotInstanceRequests'][0]['State']

        # Active State
        if state == 'active':
            instance_id = response['SpotInstanceRequests'][0]['InstanceId']
            save_spot_request_to_s3(s3_client, spot_status_s3_bucket_name, 'successful', request_id, region)
            print(f"Spot request {request_id} is active with instance ID: {instance_id}.")
            print(f"Saved to S3 bucket {spot_status_s3_bucket_name} with successful folder .")
            return 'active', instance_id

        elif state == 'open':
            save_spot_request_to_s3(s3_client, spot_status_s3_bucket_name, 'open', request_id, region)
            print(f"Spot request {request_id} is open. Saved to S3.")
            return 'open', request_id

        elif state == 'failed':
            print(f"Spot request {request_id} has failed.")
            ec2_inst_client.cancel_spot_instance_requests(SpotInstanceRequestIds=[request_id])
            return 'failed', None

        elif state == 'cancelled':
            print(f"Spot request {request_id} has been cancelled already. No further action required.")
            return 'cancelled', None

        elif state in ['closed', 'marked-for-termination']:
            print(f"Spot request {request_id} is {state}. No further action required.")
            return state, None

        else:
            print(f"Spot request {request_id} is in an unexpected state: {state}.")
            return state, None

    except Exception as e:
        print(f"Error while handling spot request {request_id}: {e}")
        return 'error', None


import random
import boto3

import random
import boto3

def launch_spot_instance(aws_credentials, target_regions, table):
    print("Starting the launch_spot_instance function...")

    user_data_encoded = generate_user_data_script(aws_credentials, sleep_time, complete_bucket_name)
    print(f"Generated user data script: {user_data_encoded[:50]}...")  # Display the first 50 characters for brevity

    print("Scanning the DynamoDB table for available items...")
    response = table.scan()

    items = response.get('Items', [])
    print(f"Scanned items: {items}")
    if not items:
        print("No items found in the table.")
        raise Exception("NoItemsAvailable: No items found in the response.")

    available_items = [item for item in items if item['region'] in target_regions]
    print(f"Filtered available items based on target regions: {available_items}")

    # Evaluate regions based on SPS and Interruption Free Scores
    print("Evaluating regions based on SPS and Interruption Free Scores...")
    suitable_regions = evaluate_regions_for_spot_instances(target_regions)
    print(f"Suitable regions: {suitable_regions}")
    if not suitable_regions:
        print("No suitable regions found after evaluation.")
        raise Exception("No suitable regions based on SPS and Interruption Free scores.")

    # Filter available items to only include those in suitable regions
    available_items = [item for item in available_items if item['region'] in suitable_regions]
    print(f"Available items after filtering by suitable regions: {available_items}")
    if not available_items:
        print("No items available in the suitable regions.")
        raise Exception("NoItemsAvailable: No items available in the suitable regions.")

    # Randomly select one of the suitable regions
    selected_region = random.choice(suitable_regions)
    print(f"Randomly selected region: {selected_region}")

    # Filter available items to only include those in the selected region
    region_specific_items = [item for item in available_items if item['region'] == selected_region]
    print(f"Items in the selected region: {region_specific_items}")

    # Sort the items within the selected region by price
    sorted_items = sorted(region_specific_items, key=lambda x: float(x['price']))
    print(f"Sorted items by price in the selected region: {sorted_items}")

    # Select the best-priced item within the selected region
    selected_region_item = sorted_items[0]  # Since it's sorted, the first item will have the lowest price
    region = selected_region_item['region']
    availability_zone = selected_region_item['availability_zone']

    print(f"Selected region: {region}")
    print(f"Selected availability zone: {availability_zone}")

    print(f"Using On-Demand price: {on_demand_price}")
    ec2_instance_client = boto3.client('ec2', region_name=region)

    ami_id = get_values_from_file('ami_ids.txt').get(region)
    security_group_ids = [get_values_from_file('security_group_ids.txt').get(region)]

    print(f"AMI ID: {ami_id}")
    print(f"Security Group IDs: {security_group_ids}")

    try:
        print("Requesting spot instances...")
        response = ec2_instance_client.request_spot_instances(
            SpotPrice=str(on_demand_price),
            InstanceCount=number_of_spot_instances,
            Type="one-time",
            LaunchSpecification={
                "ImageId": ami_id,
                "InstanceType": instance_type,
                "KeyName": key_name,
                "SecurityGroupIds": security_group_ids,
                "Placement": {
                    "AvailabilityZone": availability_zone
                },
                'UserData': user_data_encoded
            }
        )
        print(f"Spot instance request response: {response}")

    except Exception as e:
        print(f"Error occurred during spot instance request: {e}")
        raise e

    print("Sleeping for 30 seconds to allow the spot request to process...")
    time.sleep(SLEEP_TIME_SPOT_REQUEST)

    spot_request_id = response['SpotInstanceRequests'][0]['SpotInstanceRequestId']
    print(f"Spot Request ID: {spot_request_id}")

    status, result = check_spot_request_and_save_open_request_to_s3(ec2_instance_client, spot_request_id, region)
    print(f"Spot request status: {status}")
    print(f"Result: {result}")

    if status in ['active', 'open']:
        print(f"Spot request was successful with status {status}.")
        type_of_result = 'Instance ID' if result.startswith('i') else 'Spot Request ID'
        print(f"Processed request {spot_request_id} successfully with {type_of_result}: {result}")
        return result
    else:
        print(f"Spot request {spot_request_id} was not successful with status {status}.")
        raise Exception("Spot request was not successful.")



def get_request_id_from_instance(instance_id):
    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        instance_details = response['Reservations'][0]['Instances'][0]
        return instance_details['SpotInstanceRequestId']
    except Exception as e:
        print(f"Error fetching request ID for instance {instance_id}: {str(e)}")
        return None


def fetch_highest_sps_score(region: str) -> int:
    """
    Fetch the highest SPS score for a given region from the SpotPlacementScoreTable.

    :param region: The region to fetch the score.
    :return: The highest SPS score as an integer.
    """
    dynamodb = boto3.resource('dynamodb',
                              region_name=Region_DynamoDBForSpotPlacementScore)  # Replace with the correct region
    table = dynamodb.Table('SpotPlacementScoreTable')

    print(f"Fetching the highest SPS score for region {region} from SpotPlacementScoreTable...")

    try:
        # Scan the table for the specific region
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('Region').eq(region)
        )
        items = response.get('Items', [])
        if items:
            # If there are multiple items, find the highest score
            highest_score = max(int(item['SPS']) for item in items)
            # print(f"Found items: {items}")
            print(f"Highest SPS Score: {highest_score}")
            return highest_score
        else:
            print(f"No matching items found for region: {region} in SpotPlacementScoreTable.")
            return 0

    except Exception as e:
        print(f"Error fetching SPS score for region {region}: {e}")
        return 0


def fetch_interruption_free_score(region: str) -> int:
    """
    Fetch the Interruption_free_score for a given region from the SpotInterruptionRatioTable.

    :param region: The region to fetch the score.
    :return: The Interruption_free_score as an integer.
    """
    dynamodb = boto3.resource('dynamodb',
                              region_name=Region_DynamoDBForStabilityScore)  # Replace with the correct region
    table = dynamodb.Table('SpotInterruptionRatioTable')

    print(f"Fetching Interruption_free_score for region {region} from SpotInterruptionRatioTable...")

    try:
        # Scan the table for the specific region
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('Region').eq(region)
        )
        items = response.get('Items', [])
        if items:
            # Since we assume Region is unique, take the score directly
            score = int(items[0]['Interruption_free_score'])
            # print(f"Found item: {items[0]}")
            print(f"Interruption Free Score: {score}")
            return score
        else:
            print(f"No matching items found for region: {region} in SpotInterruptionRatioTable.")
            return 0

    except Exception as e:
        print(f"Error fetching Interruption_free_score for region {region}: {e}")
        return 0


def evaluate_regions_for_spot_instances(preferred_region_list):
    """
    Evaluate each preferred region to decide if it's better to use spot instances or on-demand instances.

    :param preferred_region_list: A list of preferred regions to evaluate.
    :return: A list of regions that are good for spot instances (Total Score >= 4).
    """
    suitable_regions = []

    for region in preferred_region_list:
        spot_placement_score = fetch_highest_sps_score(region)
        stability_score = fetch_interruption_free_score(region)
        total_score = spot_placement_score + stability_score

        if total_score >= 4:
            print(f"Region {region} is good for spot instances (Total Score: {total_score}).")
            suitable_regions.append(region)
        else:
            print(f"Region {region} is excluded due to low total score (Total Score: {total_score}).")

    if not suitable_regions:
        print("None of the regions are suitable for spot instances.")
        print("It is recommended to try using on-demand instances.")

    return suitable_regions


def lambda_handler(event, context):
    """
    This function is triggered by a CloudWatch event when a spot instance is about to be terminated.
    :param event:
    :param context:
    :return:
    """

    # Process the event here
    print("Spot interruption event:", event)
    if instance_id := event.get('detail', {}).get('instance-id'):

        request_id = get_request_id_from_instance(instance_id)

        object_key_check = f'open/{region_for_lambda_env}|{request_id}.txt'
        exists = check_object_exists_in_s3(s3_client, spot_status_s3_bucket_name, object_key_check)

        if exists:
            print(f"Object {object_key_check} already exists in {spot_status_s3_bucket_name}")
            print(f"Deleting {object_key_check} from {spot_status_s3_bucket_name}...")
            s3_client.delete_object(Bucket=spot_status_s3_bucket_name, Key=object_key_check)

        else:
            print(f"Object {object_key_check} does not exist in {spot_status_s3_bucket_name}open/")

        aws_credentials = get_aws_credentials_from_file()
        add_instance_id_to_s3(instance_id, s3_client, event)
        launch_spot_instance(aws_credentials, target_regions, table)
    else:
        print("Instance-id not found in the event.")

    return {
        'statusCode': 200,
        'body': json.dumps('Spot interruption handled!')
    }
