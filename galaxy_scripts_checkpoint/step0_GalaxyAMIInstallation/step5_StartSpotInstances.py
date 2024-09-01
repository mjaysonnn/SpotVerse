import base64
import concurrent.futures
import configparser
import itertools
import json
import os
import sys
import time
from typing import List

import boto3
import botocore
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from colorama import Fore, init

inst_id = None

import re

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


def auto_color_print(text):
    """
    Print text in a different color each time.
    :param text:
    """
    colors = [Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.MAGENTA, Fore.CYAN]
    if not hasattr(auto_color_print, "color_cycle"):
        # create an iterator that cycles through the colors
        auto_color_print.color_cycle = itertools.cycle(colors)
    color = next(auto_color_print.color_cycle)
    print(f"{color}{text}{Fore.RESET}")


def extract_value(pattern, content):
    """
    Extract a value from a string using a regular expression pattern.
    :param pattern:
    :param content:
    :return:
    """
    return match[1] if (match := re.search(pattern, content)) else None


def get_aws_credentials_from_file(filename='./credentials.txt'):
    """
    Get AWS credentials from a file.
    :param filename:
    :return:
    """
    with open(filename, 'r') as f:
        content = f.read()

    aws_access_key_id_pattern = r'export AWS_ACCESS_KEY_ID="([^"]+)"'
    aws_secret_access_key_pattern = r'export AWS_SECRET_ACCESS_KEY="([^"]+)"'
    # aws_session_token_pattern = export AWS_SESSION_TOKEN="([^"]+)"'

    return {
        'AWS_ACCESS_KEY_ID': extract_value(aws_access_key_id_pattern, content),
        'AWS_SECRET_ACCESS_KEY': extract_value(aws_secret_access_key_pattern, content),
        # 'AWS_SESSION_TOKEN': extract_value(aws_session_token_pattern, content),
    }


def count_open_spot_requests(ec2_client, request_ids):
    """
    Count the number of open (not yet fulfilled) spot requests.
    """
    open_request_count = 0
    try:
        response = ec2_client.describe_spot_instance_requests(SpotInstanceRequestIds=request_ids)
        for request in response['SpotInstanceRequests']:
            state = request['State']
            if state == 'open':
                open_request_count += 1
    except botocore.exceptions.ClientError as e:
        print(f"Error counting open spot requests: {str(e)}")

    return open_request_count


def upload_request_to_s3(request_ids, bucket_name, region, state_type, check_count=0):
    """
    Upload the spot request IDs to the specified S3 bucket.
    """

    # Loop through each request ID and upload them individually
    for request_id in request_ids:
        object_name = f"{state_type}/{region}|{request_id}.txt"
        # Initialize metadata if the state type is "open"
        metadata = {'check_count': str(check_count)} if state_type == "open" else None

        try:
            # If the state type is "open", include the metadata
            if state_type == "open":
                s3_client.put_object(Bucket=bucket_name, Key=object_name, Body=request_id, Metadata=metadata)
                print(
                    f"Spot request {request_id} (Region: {region}) saved to {state_type} folder in S3 bucket "
                    f"{bucket_name} with check count {check_count}.")
            else:
                # For other state types, upload without metadata
                s3_client.put_object(Bucket=bucket_name, Key=object_name, Body=request_id)

            print(f"Successfully uploaded {request_id} to S3 bucket {bucket_name} with key {object_name}.")
        except botocore.exceptions.ClientError as e:
            print(f"Error uploading {request_id} to S3: {str(e)}")


def count_spot_requests_by_state(ec2_client, request_ids):
    """
    Count the number of active (fulfilled) and open spot requests.
    Also, return the request IDs that are in the 'open' state.
    """
    active_count = 0
    open_count = 0
    failed_count = 0
    successful_request_ids = []
    open_request_ids = []  # List to collect request IDs that are in the 'open' state
    failed_request_ids = []  # List to collect request IDs that are in the 'failed' state

    try:
        response = ec2_client.describe_spot_instance_requests(SpotInstanceRequestIds=request_ids)

        # Iterate through all spot requests to count active and open states
        for request in response['SpotInstanceRequests']:
            # print(request['State'])
            if request['State'] == 'active':
                active_count += 1
                successful_request_ids.append(request['SpotInstanceRequestId'])
            elif request['State'] == 'open':
                open_count += 1
                print("Appending open request ID to the list")
                open_request_ids.append(request['SpotInstanceRequestId'])  # Add open request ID to the list
            elif request['State'] in ['cancelled', 'failed', 'closed']:
                failed_request_ids.append(request['SpotInstanceRequestId'])
                failed_count += 1
            else:
                failed_request_ids.append(request['SpotInstanceRequestId'])
                failed_count += 1

        if successful_request_ids:
            print(f"Successful request IDs: {successful_request_ids}")
            print("Uploading successful request IDs to S3...")
            upload_request_to_s3(successful_request_ids, spot_tracking_s3_bucket_name,
                                 region_for_s3_for_checking_spot_request,
                                 "successful")

        if open_request_ids:
            print(f"Open request IDs: {open_request_ids}")
            print("Uploading open request IDs to S3...")
            upload_request_to_s3(open_request_ids, spot_tracking_s3_bucket_name,
                                 region_for_s3_for_checking_spot_request, "open")

        if failed_request_ids:
            print(f"Failed request IDs: {failed_request_ids}")
            print("Uploading failed request IDs to S3...")
            upload_request_to_s3(failed_request_ids, spot_tracking_s3_bucket_name,
                                 region_for_s3_for_checking_spot_request,
                                 "failed")

    except botocore.exceptions.ClientError as e:
        print(f"Error counting spot requests: {str(e)}")

    return active_count, open_count, failed_count, open_request_ids


def get_request_counts_by_state(ec2_client, request_ids):
    """
    Count the number of spot requests based on their state (active, open, terminated).
    """
    successful_count = 0
    open_count = 0
    terminated_count = 0

    try:
        response = ec2_client.describe_spot_instance_requests(SpotInstanceRequestIds=request_ids)
        for request in response['SpotInstanceRequests']:
            state = request['State']
            if state == 'active':
                successful_count += 1
            elif state == 'open':
                open_count += 1
            elif state == 'cancelled':
                terminated_count += 1
    except botocore.exceptions.ClientError as e:
        print(f"Error fetching spot requests: {str(e)}")

    return successful_count, open_count, terminated_count


def cancel_open_spot_requests(ec2_client, request_ids):
    """
    Cancel open (unfulfilled) spot requests.
    """
    try:
        response = ec2_client.describe_spot_instance_requests(SpotInstanceRequestIds=request_ids)
        for request in response['SpotInstanceRequests']:
            state = request['State']
            if state == 'open':
                request_id = request['SpotInstanceRequestId']
                ec2_client.cancel_spot_instance_requests(SpotInstanceRequestIds=[request_id])
                print(f"Canceled open spot request with ID: {request_id}")
    except botocore.exceptions.ClientError as e:
        print(f"Error canceling open spot requests: {str(e)}")


def launch_spot_instance(ec2_client, spot_price, ami_id, inst_type, key_name, security_group_ids, selected_az,
                         number_of_instances):
    """
    Launch a spot instance with the specified parameters.
    """
    global inst_id

    user_data_script = f"""#!/bin/bash

                export AWS_ACCESS_KEY_ID="{aws_credentials['AWS_ACCESS_KEY_ID']}"
                export AWS_SECRET_ACCESS_KEY="{aws_credentials['AWS_SECRET_ACCESS_KEY']}"

                # Initializing the log
                echo "Starting script" >/var/log/user-data.log                

                # Appending all standard output and error messages to the log file
                exec > >(tee -a /var/log/user-data.log) 2>&1                                
                
                # Set the HOME environment variable
                export HOME=/home/ec2-user
                                
                # This is where you can add your custom user data script
                git config --global --add safe.directory /home/ec2-user/galaxy
                ./home/ec2-user/galaxy/run.sh > /dev/null 2>&1 &
                echo "Running the Galaxy server in the background..."
                
                echo "Sleeping for 5 minutes to allow the server to start..."
                sleep 300
                
                cd /home/ec2-user/ngs_analysis || exit
                ./run_all_batches.sh

                echo "Retrieving the instance ID using ec2-metadata..."
                INSTANCE_ID=$(ec2-metadata -i | cut -d " " -f 2)
                echo "Instance ID retrieved: $INSTANCE_ID"

                # Get the Spot Instance Request ID
                SPOT_REQUEST_ID=$(aws ec2 describe-instances --instance-id $INSTANCE_ID --query "Reservations[0].Instances[0].SpotInstanceRequestId" --output text)
                echo "Spot Instance Request ID retrieved: $SPOT_REQUEST_ID"

                # Get the region from the Availability Zone
                REGION=$(ec2-metadata -z | cut -d " " -f 2 | sed 's/.$//')
                echo "Region retrieved: $REGION"

                # Check if the file exists in the spot_check_interruption bucket
                CHECK_KEY="open/${{REGION}}|${{SPOT_REQUEST_ID}}.txt"
                echo "Checking if file $CHECK_KEY exists in bucket {spot_tracking_s3_bucket_name}..."
                if aws s3api head-object --bucket "{spot_tracking_s3_bucket_name}" --key "$CHECK_KEY" 2>/dev/null; then
                    echo "File $CHECK_KEY exists in bucket. No further action required."
                    aws s3api delete-object --bucket "{spot_tracking_s3_bucket_name}" --key "$CHECK_KEY"
                else
                    echo "File $CHECK_KEY does not exist in bucket {spot_tracking_s3_bucket_name}. Skipping..."
                fi

                # Retrieve instance details and spot price information
                INSTANCE_TYPE=$(ec2-metadata -t | cut -d " " -f 2)
                AVAILABILITY_ZONE=$(ec2-metadata -z | cut -d " " -f 2)
                LAUNCH_TIME=$(aws ec2 describe-instances \
                  --instance-id $INSTANCE_ID \
                  --query "Reservations[0].Instances[0].LaunchTime" \
                  --output text)
                CURRENT_SPOT_PRICE=$(aws ec2 describe-spot-price-history \
                  --instance-types $INSTANCE_TYPE \
                  --availability-zone $AVAILABILITY_ZONE \
                  --product-descriptions "Linux/UNIX" \
                  --max-results 1 \
                  --query "SpotPriceHistory[0].SpotPrice" \
                  --output text)
                CURRENT_TIME=$(date --utc +'%Y-%m-%dT%H:%M:%S+00:00')

                # Write the information to a file
                echo "Instance ID: $INSTANCE_ID" > /tmp/instance_info.txt
                echo "Availability Zone: $AVAILABILITY_ZONE" >> /tmp/instance_info.txt
                echo "Instance Launch Time: $LAUNCH_TIME" >> /tmp/instance_info.txt
                echo "Current Time: $CURRENT_TIME" >> /tmp/instance_info.txt
                echo "Current Spot Price: $CURRENT_SPOT_PRICE" >> /tmp/instance_info.txt

                KEY="$INSTANCE_ID.txt"

                echo "Checking if bucket {complete_bucket_name} exists..."
                if aws s3api head-bucket --bucket "{complete_bucket_name}" &>/dev/null; then
                  echo "Bucket {complete_bucket_name} exists"
                else
                  echo "Bucket {complete_bucket_name} does not exist. Creating..."
                  aws s3api create-bucket --bucket "{complete_bucket_name}"
                  echo "Bucket {complete_bucket_name} created."
                fi

                echo "Uploading the file with the name $INSTANCE_ID.txt to the S3 bucket {complete_bucket_name}..."
                aws s3api put-object --bucket {complete_bucket_name} --key $KEY --body /tmp/instance_info.txt
                rm -f /tmp/instance_info.txt
                echo "Upload completed. Please check the S3 bucket for the file."

                echo "Terminating instance $INSTANCE_ID"
                aws ec2 terminate-instances --instance-ids $INSTANCE_ID

                """

    # Base64 encode the user data script
    user_data_encoded = base64.b64encode(user_data_script.encode()).decode()

    print(f"Using On Demand Price: {on_demand_price}")
    # Request spot instance
    spot_response = ec2_client.request_spot_instances(
        # SpotPrice=spot_price,
        SpotPrice=str(on_demand_price),
        InstanceCount=number_of_instances,
        Type="one-time",  # can be "one-time" or "persistent"
        LaunchSpecification={
            "ImageId": ami_id,
            "InstanceType": inst_type,
            "KeyName": key_name,
            "SecurityGroupIds": security_group_ids,
            "Placement": {
                "AvailabilityZone": selected_az  # Replace with your desired availability zone
            },
            'UserData': user_data_encoded
        }
    )

    request_ids = [request['SpotInstanceRequestId'] for request in spot_response['SpotInstanceRequests']]

    # Initial delay
    print(f"Waiting 20 seconds for checking {number_of_instances} spot requests")
    time.sleep(20)

    while True:

        try:
            # Count the number of open spot requests
            n_active, n_open, n_failed, open_request_ids = count_spot_requests_by_state(ec2_client, request_ids)
            active_and_open_request = n_active + n_open
            print(f"Active: {n_active}, Open: {n_open}")

            if active_and_open_request == number_of_instances:
                print("All spot requests fulfilled.")
                return n_active, n_open, n_failed, open_request_ids

            else:
                print(
                    f"waiting another 60 seconds to see if  {number_of_instances - active_and_open_request} "
                    f"could change to active or open...")
                time.sleep(60)  # Wait for 1 minute before checking again

        except botocore.exceptions.ClientError as e:
            if "InvalidSpotInstanceRequestID.NotFound" not in str(e):
                # Some other error occurred, you might want to handle it differently or re-raise it
                raise e

            print("Spot instance request IDs not found yet, waiting for a bit and retrying...")
            time.sleep(60)

        # Get counts for each state
        n_active, n_open, n_failed, open_request_ids = count_spot_requests_by_state(ec2_client, request_ids)
        return n_active, n_open, n_failed, open_request_ids


def get_instance_public_ip(ec2_client, ec2_instance_id):
    """
    Get the public IP address of a specific EC2 instance.
    """

    response = ec2_client.describe_instances(InstanceIds=[ec2_instance_id])

    return response['Reservations'][0]['Instances'][0]['PublicIpAddress']


def get_values_from_file(filename):
    """Reads key-value pairs from a file and returns a dictionary."""
    values = {}
    # make dir with "../multi_region_scripts/"
    filename = f"./{filename}"
    with open(filename, 'r') as f:
        for line in f:
            key, value = line.strip().split(' ')
            values[key] = value
    return values


def cancel_spot_requests_and_terminate_instances(region_name):
    """
    Cancel spot requests and terminate instances in the specified region.
    :param region_name:  Name of the region
    :return:  None
    """
    ec2 = boto3.client('ec2', region_name=region_name)

    # Fetch all active/open spot instance requests
    spot_requests = ec2.describe_spot_instance_requests(
        Filters=[{
            'Name': 'state',
            'Values': ['open', 'active']
        }]
    )['SpotInstanceRequests']

    if not spot_requests:
        print(f"No spot instance requests found for region {region_name}.")
        return

    request_ids = [request['SpotInstanceRequestId'] for request in spot_requests]

    # Extract the instance IDs of the spot requests to terminate those instances
    instance_ids = [request['InstanceId'] for request in spot_requests if 'InstanceId' in request]

    # Cancel spot instance requests
    ec2.cancel_spot_instance_requests(SpotInstanceRequestIds=request_ids)
    print(f"Canceled {len(request_ids)} spot instance requests in {region_name}.")

    # Terminate instances associated with the spot requests
    if instance_ids:
        ec2.terminate_instances(InstanceIds=instance_ids)
        print(f"Terminated {len(instance_ids)} instances associated with spot requests in {region_name}.")


def bucket_exists(bucket_name):
    """
    Check if the bucket exists.
    """
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError:
        return False


def empty_bucket(bucket_name):
    """
    Empty all contents of the specified S3 bucket.
    """

    if not bucket_exists(bucket_name):
        print(f"Error: Bucket {bucket_name} does not exist!")
        sys.exit(1)

    bucket = s3.Bucket(bucket_name)
    # Delete all objects in the bucket
    for obj in bucket.objects.all():
        obj.delete()

    print(f"Bucket {bucket_name} has been emptied!")


def delete_bucket(bucket_name):
    """
    Delete the specified S3 bucket.
    """

    bucket = s3.Bucket(bucket_name)
    bucket.delete()
    print(f"Bucket {bucket_name} has been deleted!")


def create_bucket(bucket_name):
    """
    Create the specified S3 bucket.
    :param bucket_name:
    """
    try:
        s3.create_bucket(Bucket=bucket_name)
    except Exception as e:
        print(f"Error creating bucket {bucket_name}. Error: {e}")
        sys.exit(1)


def monitor_failed_requests(ec2_client, open_request_ids):
    """
    Monitors the provided spot instance request IDs for any failed requests.
    Returns the failed spot request IDs.

    Parameters:
    - ec2_client: the EC2 client
    - open_request_ids: the list of open request IDs to monitor

    Returns:
    - A list of failed spot request IDs
    """
    failed_request_ids = []
    print("Wait for 3 minutes to see if any spot requests failed...")
    time.sleep(180)

    try:
        response = ec2_client.describe_spot_instance_requests(SpotInstanceRequestIds=open_request_ids)
        failed_request_ids.extend(
            request['SpotInstanceRequestId']
            for request in response['SpotInstanceRequests']
            if request['State'] == 'failed'
        )
    except botocore.exceptions.ClientError as e:
        print(f"Error monitoring spot requests: {str(e)}")

    return failed_request_ids


def get_user_input(prompt: str) -> bool:
    """Utility function to simplify user yes/no input."""
    return input(prompt).lower() == 'yes'


def empty_spot_bucket(bucket_name, folder_name):
    """
    empty the specified S3 bucket.
    """
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    for obj in bucket.objects.filter(Prefix=folder_name):
        if obj.key != folder_name:
            obj.delete()


def print_info(details: dict):
    """
    Print details in a formatted way.

    :param details: Dictionary containing the information to print.
    """
    for key, value in details.items():
        print(f"{key}: {value}")


def update_spot_price_table():
    # Update DynamoDB table
    auto_color_print("Updating Spot Price table...")
    lambda_client = boto3.client('lambda', region_name=Region_DynamodbForSpotPrice)
    function_name = "lambda_for_updating_spot_price"
    payload = {"key": "value"}  # Okay to send an empty payload
    response = lambda_client.invoke(FunctionName=function_name, InvocationType='RequestResponse',
                                    Payload=bytes(json.dumps(payload), encoding='utf-8'))
    response_payload = json.loads(response['Payload'].read())
    print("Updated Spot Price Table : ", response_payload)
    print("Give some time to update Spot Price Table")
    time.sleep(5)


def update_interruption_table():
    # Update Spot Placement Score DynamoDB table
    # This is to prevent the Cloudwatch not being able to trigger the lambda function. Remove this if not needed
    auto_color_print("Updating DynamoDB table...")
    lambda_client = boto3.client('lambda', region_name=Region_DynamoDBForStabilityScore)
    function_name = "lambda_spot_interruption_ratio_inserter"
    payload = {"key": "value"}  # Okay to send an empty payload
    response = lambda_client.invoke(FunctionName=function_name, InvocationType='RequestResponse',
                                    Payload=bytes(json.dumps(payload), encoding='utf-8'))
    response_payload = json.loads(response['Payload'].read())
    print("Updated Interruption Frequency Table: ", response_payload)
    print("Give some time to update Interruption Frequency Table")
    time.sleep(5)


def update_spot_sps_table():
    # Update Spot Placement Score DynamoDB table
    # This is to prevent the Cloudwatch not being able to trigger the lambda function. Remove this if not needed
    auto_color_print("Updating SPS table...")
    lambda_client = boto3.client('lambda', region_name=Region_DynamoDBForSpotPlacementScore)
    function_name = "lambda_spot_placement_score_inserter"
    payload = {"key": "value"}  # Okay to send an empty payload
    response = lambda_client.invoke(FunctionName=function_name, InvocationType='RequestResponse',
                                    Payload=bytes(json.dumps(payload), encoding='utf-8'))
    response_payload = json.loads(response['Payload'].read())
    print("Updated SPS Table: ", response_payload)
    print("Give some time to update SPS Table")
    time.sleep(5)


def get_user_input(prompt):
    """Function to get user input with a prompt."""
    response = input(prompt)
    return response.lower() != 'no'


def empty_buckets():
    """
    Empty the specified S3 buckets.
    """
    # Prompting for creating or emptying buckets, indicating continuation unless "no" is input
    # Prompting individually for creating or emptying each bucket
    for bucket_name in [complete_bucket_name, interrupt_s3_bucket_name]:
        # Check and create bucket if it doesn't exist
        if not bucket_exists(bucket_name):
            print(f"Bucket {bucket_name} does not exist. Creating it...")
            create_bucket(bucket_name)
        else:
            # Ask to empty the bucket if it already exists
            if get_user_input(f"Do you want to empty bucket {bucket_name}? Type 'no' to skip: "):
                empty_bucket(bucket_name)

    # Asking if the user wants to empty specific folders, with creation of the bucket if it doesn't exist
    if get_user_input(f"Do you want to empty folders in {spot_tracking_s3_bucket_name}? Type 'no' to skip: "):
        if not bucket_exists(spot_tracking_s3_bucket_name):
            print(f"Bucket {spot_tracking_s3_bucket_name} does not exist. Creating it...")
            create_bucket(spot_tracking_s3_bucket_name)

        for folder_name in ['open/', 'successful/', 'failed/']:
            empty_spot_bucket(spot_tracking_s3_bucket_name, folder_name)


def cancel_spot_requests():
    """
    Check if the user wants to cancel spot requests, empty/create buckets, and empty spot request folder
    """

    if get_user_input("Do you want to cancel spot requests and terminate instances? Type 'no' to skip: "):
        for region in preferred_regions:
            cancel_spot_requests_and_terminate_instances(region)


def fetch_spot_price_data(suitable_regions: List[str] = None) -> dict:
    """
    Fetch spot price data from DynamoDB.
    If there are suitable regions, fetch data for those regions.
    Otherwise, fetch data for the region specified in region_for_s3_for_checking_spot_request.

    :param suitable_regions: List of regions that are considered suitable for spot instances.
    :return: Dictionary of responses for the specified regions.
    """
    response_dict = {}
    print("Fetching DynamoDB Spot Price Data...")

    dynamodb = boto3.resource('dynamodb', region_name=Region_DynamodbForSpotPrice)
    table = dynamodb.Table('SpotPriceCostTable')

    # Determine the regions to query for spot price data
    if suitable_regions:
        regions_to_query = suitable_regions
    else:
        regions_to_query = [region_for_s3_for_checking_spot_request]

    # Fetch data for the specified regions (suitable or fallback region)
    for region in regions_to_query:
        print(f"Fetching data for region/availability zone: {region}")
        response = table.scan(FilterExpression=Attr('availability_zone').begins_with(region))
        response_dict[region] = response

    return response_dict


def filter_items_by_regions(items, regions):
    """Filter items based on specified regions."""
    return [item for item in items if item['region'] in regions]


def calculate_instance_distribution(n_of_inst_to_launch, number_of_regions):
    """Calculate how many instances to launch per region and handle any remainder."""
    instances_per_region, remainder = divmod(n_of_inst_to_launch, number_of_regions)
    return instances_per_region, remainder


def fetch_ami_and_security_group_ids(region):
    """Fetch AMI and security group IDs for the specified region."""
    ami_ids = get_values_from_file("ami_ids.txt")
    ami_id = ami_ids.get(region)

    security_group_ids_map = get_values_from_file("security_group_ids.txt")
    security_group_id = security_group_ids_map.get(region)

    return ami_id, [security_group_id]


def calculate_instances_to_request(region, instances_per_region, remainder, regions_received_extra_instance):
    """Determine the number of instances to request for a region."""
    if remainder > 0 and region not in regions_received_extra_instance:
        instances_to_request = instances_per_region + 1
        remainder -= 1
        regions_received_extra_instance.add(region)
    else:
        instances_to_request = instances_per_region
    return instances_to_request, remainder


def launch_all_spot_instances(response_dict):
    """
    Launch spot instances for the specified regions.
    """
    total_regions = len(response_dict)
    print(f"Total regions: {total_regions}")
    instances_per_region, remainder = divmod(number_of_instances_to_launch, total_regions)
    print(f"Instances per region: {instances_per_region}, Remainder: {remainder}")
    regions_received_extra_instance = set()
    key_name = 'xxay_m1'

    for region, response in response_dict.items():
        ec2_client = boto3.client('ec2', region_name=region)
        ami_id, security_group_ids = fetch_ami_and_security_group_ids(region)

        active_request_count = 0  # Count for active spot requests
        open_request_count = 0  # Count for open spot requests
        open_request_ids_global = []

        if 'Items' not in response or not response['Items']:
            print(f"No items found in the table for region: {region}.")
            continue

        sorted_items = sorted(response['Items'], key=lambda x: float(x['price']))
        instances_to_request = instances_per_region

        # Handle the remainder
        if remainder > 0 and region not in regions_received_extra_instance:
            instances_to_request += 1
            remainder -= 1
            regions_received_extra_instance.add(region)

        while instances_to_request > 0:  # Loop until all instances are launched
            for item in sorted_items:
                region = item['region']
                spot_price = str(item['price'])
                availability_zone = item['availability_zone']

                auto_color_print(f"Attempting with Availability Zone: {availability_zone}, "
                                 f"Price: {spot_price}, Region: {region}")

                print_info({"Original spot price": str(item['price']),
                            "Updated spot price": spot_price, "Region": region,
                            "AMI ID": ami_id, "Security Group ID": security_group_ids,
                            "Instance type": instance_type, "Key name": key_name,
                            "Spot price": spot_price, "Number of instances to launch": instances_to_request})

                # Spot Price is not actually used but on-demand price is used
                n_active, n_open, n_failed, open_request_ids = launch_spot_instance(
                    ec2_client, spot_price, ami_id, instance_type, key_name,
                    security_group_ids, availability_zone, instances_to_request
                )

                open_request_ids_global.extend(open_request_ids)
                active_request_count += n_active
                open_request_count += n_open
                instances_to_request -= (n_active + n_open)  # Decrement the number of active/open instances

                print(f"Number of Active requests: {n_active}, Number of Open requests: {n_open}")
                print(f"Number of Failed requests: {n_failed}")
                print(f"Open request IDs: {open_request_ids}")
                print(f"Successful requests: {active_request_count}, Open requests: {open_request_count}")

                if instances_to_request == 0:  # Break the loop if all instances are launched
                    print("All spot requests have been successfully fulfilled (active or open).")
                    break

            if instances_to_request > 0:
                print(f"Still {instances_to_request} more requests are needed. Retrying in other AZs...")

        if instances_to_request > 0:
            print(f"Could not fulfill all requests for region: {region}.")

    print("Completed launching spot instances across all regions.")


def fetch_all_sps_scores(region_name) -> dict:
    """
    Fetch all SPS scores from the SpotPlacementScoreTable and return a dictionary with regions as keys.

    :return: A dictionary with regions as keys and the highest SPS score as values.
    """
    dynamodb = boto3.resource('dynamodb',
                              region_name=region_name)  # Replace with the correct region
    table = dynamodb.Table('SpotPlacementScoreTable')

    print("Fetching all SPS scores from SpotPlacementScoreTable...")

    try:
        # Scan the entire table once and then process
        response = table.scan()
        items = response.get('Items', [])
        sps_scores = {}

        if items:
            for item in items:
                region = item['Region']
                sps_score = int(item['SPS'])

                if region in sps_scores:
                    sps_scores[region] = max(sps_scores[region], sps_score)
                else:
                    sps_scores[region] = sps_score

            print(f"Fetched SPS scores: {sps_scores}")
        else:
            print("No items found in SpotPlacementScoreTable.")

        return sps_scores

    except Exception as e:
        print(f"Error fetching SPS scores: {e}")
        return {}


def fetch_all_interruption_free_scores(region_name) -> dict:
    """
    Fetch all Interruption_free_scores from the SpotInterruptionRatioTable and return a dictionary with regions as keys.

    :return: A dictionary with regions as keys and the Interruption_free_score as values.
    """
    dynamodb = boto3.resource('dynamodb',
                              region_name=region_name)  # Replace with the correct region
    table = dynamodb.Table('SpotInterruptionRatioTable')

    print("Fetching all Interruption_free_scores from SpotInterruptionRatioTable...")

    try:
        # Scan the entire table once and then process
        response = table.scan()
        items = response.get('Items', [])
        interruption_scores = {}

        if items:
            for item in items:
                region = item['Region']
                score = int(item['Interruption_free_score'])

                interruption_scores[region] = score

            print(f"Fetched Interruption Free Scores: {interruption_scores}")
        else:
            print("No items found in SpotInterruptionRatioTable.")

        return interruption_scores

    except Exception as e:
        print(f"Error fetching Interruption Free Scores: {e}")
        return {}


def evaluate_regions_for_spot_instances(preferred_region_list, region_for_sps, region_for_interruption):
    """
    Evaluate each preferred region to decide if it's better to use spot instances or on-demand instances.

    :param preferred_region_list: A list of preferred regions to evaluate.
    :param region_for_sps: The region used to fetch SPS scores.
    :param region_for_interruption: The region used to fetch Interruption scores.
    :return: A list of regions that are good for spot instances (Total Score >= 4), sorted by total score.
    """
    suitable_regions = []

    # Fetch scores for all regions
    sps_scores = fetch_all_sps_scores(region_for_sps)
    interruption_scores = fetch_all_interruption_free_scores(region_for_interruption)

    for region in preferred_region_list:
        # Access the scores for each region separately
        print(f"Evaluating region: {region}")
        spot_placement_score = sps_scores.get(region, 0)
        stability_score = interruption_scores.get(region, 0)
        total_score = spot_placement_score + stability_score
        print(f"Region: {region}, SPS: {spot_placement_score}, Stability: {stability_score}, Total: {total_score}")

        if total_score >= 4:
            print(f"Region {region} is good for spot instances (Total Score: {total_score}).")
            suitable_regions.append((region, total_score))
        else:
            print(f"Region {region} is excluded due to low total score (Total Score: {total_score}).")

    # Sort the suitable regions by total score in descending order
    suitable_regions.sort(key=lambda x: x[1], reverse=True)

    # Pick the top 4 regions if there are more than 4
    if len(suitable_regions) > 4:
        suitable_regions = suitable_regions[:4]

    if not suitable_regions:
        print("None of the regions are suitable for spot instances.")
        print("It is recommended to try using on-demand instances.")

    # Return only the region names from the sorted list
    return [region for region, score in suitable_regions]


def run_parallel_updates():
    """
    Run multiple update functions in parallel using a ThreadPoolExecutor.

    This function will execute `update_spot_price_table`, `update_spot_sps_table`,
    and `update_interruption_table` concurrently. It will also handle any exceptions
    that occur during the execution of these functions.
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(update_spot_price_table),
            executor.submit(update_spot_sps_table),
            executor.submit(update_interruption_table)
        ]

        # Wait for all threads to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()  # This will raise an exception if the thread raised one
            except Exception as e:
                print(f"An error occurred: {e}")


# ============================================================ Main ===================================================

# Initialize the parser and read the conf.ini file
config = configparser.ConfigParser()
conf_file_path = find_config_file()
config_path = str(conf_file_path)
config.read(config_path)
complete_bucket_name = config.get('settings', 'complete_s3_bucket_name')
interrupt_s3_bucket_name = config.get('settings', 'interrupt_s3_bucket_name')
sleep_time = int(config.get('settings', 'sleep_time'))
number_of_instances_to_launch = int(config.get('settings', 'number_of_spot_instances'))
preferred_regions = [region.strip() for region in config.get('settings', 'regions_to_use').split(',')]
# factor = Decimal(config.getfloat('settings', 'spot_price_factor'))
region_for_s3_for_checking_spot_request = (config.get('settings', 'Region_S3ForCheckingSpotRequest'))
instance_type = config.get('settings', 'instance_type')
spot_tracking_s3_bucket_name = config.get('settings', 'spot_tracking_s3_bucket_name')
Region_DynamodbForSpotPrice = config.get('settings', 'Region_DynamodbForSpotPrice')
on_demand_price = float(config.get('settings', 'on_demand_price'))
available_regions = [region.strip() for region in config.get('settings', 'available_regions').split(',')]
Region_DynamoDBForSpotPlacementScore = config.get('settings', 'Region_DynamoForSpotPlacementScore')
Region_DynamoDBForStabilityScore = config.get('settings', 'Region_DynamoForSpotInterruptionRatio')
print(f"Complete bucket name: {complete_bucket_name}")
print(f"Interrupt bucket name: {interrupt_s3_bucket_name}")
print(f"Sleep time: {sleep_time}")
print(f"Number of spot instances: {number_of_instances_to_launch}")
print(f"Preferred regions: {preferred_regions}")
print(f"Region to for s3 of checking spot request : {region_for_s3_for_checking_spot_request}")
print(f"Instance type: {instance_type}")
print(f"Spot tracking S3 bucket name: {spot_tracking_s3_bucket_name}")
print(f"Spot Price DynamoDB Region: {Region_DynamodbForSpotPrice}")
print(f"Spot Placement Score DynamoDB Region: {Region_DynamoDBForSpotPlacementScore}")
print(f"Stability Score DynamoDB Region: {Region_DynamoDBForStabilityScore}")
print(f"On-demand price: {on_demand_price}")
print(f"Available regions: {available_regions}")

# exit()

confirmation = input("Are the variables correct? Type 'no' to exit, or anything else to continue: ")
if confirmation.lower() == 'no':
    print("Exiting as requested...")
    exit()
else:
    print("Continuing with the process...")

# Initialize the S3 client, colored print, and other variables
s3 = boto3.resource('s3')
s3_client = boto3.client('s3')
init()  # initialize colorama, it's for colored print
auto_color_print("Copying AWS credentials...")  # Get AWS credentials from the file
os.system("python3 step0_CopyAWSCredentials.py")
aws_credentials = get_aws_credentials_from_file()
print("AWS credentials copied.")


def main():
    """
    Main function.
    """

    # cancel_spot_requests()
    # empty_buckets()

    # run_parallel_updates()

    # Check if preferred_regions is actually a list containing 'None' or is NoneType
    # if preferred_regions is None or preferred_regions == ['None']:
    #     suitable_regions = evaluate_regions_for_spot_instances(available_regions, Region_DynamoDBForSpotPlacementScore,
    #                                                            Region_DynamoDBForStabilityScore)
    #     print(f"No preferred regions specified. Using available regions: {suitable_regions}")
    # else:
    #     suitable_regions = evaluate_regions_for_spot_instances(preferred_regions, Region_DynamoDBForSpotPlacementScore,
    #                                                            Region_DynamoDBForStabilityScore)
    #     print(f"Suitable regions from preferred regions: {suitable_regions}")

    suitable_regions = preferred_regions
    response_dict: dict = fetch_spot_price_data(suitable_regions)

    launch_all_spot_instances(response_dict)


print("Process completed.")

if __name__ == "__main__":
    main()
