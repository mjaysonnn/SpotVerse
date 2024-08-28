import base64
import configparser
import re
import time
from decimal import Decimal

import boto3

# Initialize the parser and read the ini file
config = configparser.ConfigParser()
config.read('./conf.ini')
regions_string = config.get('settings', 'regions_to_use')
target_regions = [region.strip() for region in regions_string.split(',')]

SLEEP_TIME_SPOT_REQUEST = int(config.get('settings', 'sleep_time_for_spot_request'))
complete_bucket_name = config.get('settings', 'complete_s3_bucket_name')
interrupt_s3_bucket_name = config.get('settings', 'interrupt_s3_bucket_name')
sleep_time = int(config.get('settings', 'sleep_time'))
factor = Decimal(config.getfloat('settings', 'spot_price_factor'))
instance_type = config.get('settings', 'instance_type')
key_name = config.get('settings', 'key_name')
spot_tracking_s3_bucket_name = config.get('settings', 'spot_tracking_s3_bucket_name')
Region_DynamodbForSpotPrice = config.get('settings', 'Region_DynamodbForSpotPrice')
on_demand_price = float(config.get('settings', 'on_demand_price'))

print(f"Target_regions: {target_regions}")
print(f"Factor from conf.ini: {factor}")
print(f"sleep_time: {sleep_time}")
print(f"instance_type: {instance_type}")
print(f"key_name: {key_name}")
print(f"complete_bucket_name: {complete_bucket_name}")
print(f"interrupt_bucket_name: {interrupt_s3_bucket_name}")
print("SLEEP_TIME_SPOT_REQUEST: ", SLEEP_TIME_SPOT_REQUEST)
print(f"spot_status_bucket_name: {spot_tracking_s3_bucket_name}")
print(f"Region_DynamodbForSpotPrice: {Region_DynamodbForSpotPrice}")
print(f"on_demand_price: {on_demand_price}")

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb', region_name=Region_DynamodbForSpotPrice)
table = dynamodb.Table('SpotPriceCostTable')


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
                echo "Checking if file $CHECK_KEY exists in bucket {spot_tracking_s3_bucket_name}..."
                if aws s3api head-object --bucket "{spot_tracking_s3_bucket_name}" --key "$CHECK_KEY" 2>/dev/null; then
                    echo "File $CHECK_KEY exists in bucket. No further action required."
                    aws s3api delete-object --bucket "{spot_tracking_s3_bucket_name}" --key "$CHECK_KEY"
                else
                    echo "File $CHECK_KEY does not exist in bucket {spot_tracking_s3_bucket_name}. Skipping..."
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


def handle_spot_request_status(ec2_client, request_id, region):
    """
    Waits for the spot instance request to be fulfilled and handles various states.
    """
    try:
        response = ec2_client.describe_spot_instance_requests(SpotInstanceRequestIds=[request_id])
        state = response['SpotInstanceRequests'][0]['State']

        # Active State
        if state == 'active':
            instance_id = response['SpotInstanceRequests'][0]['InstanceId']
            save_spot_request_to_s3(s3_client, spot_tracking_s3_bucket_name, 'successful', request_id, region)
            print(f"Spot request {request_id} is active with instance ID: {instance_id}.")
            print(f"Saved to S3 bucket {spot_tracking_s3_bucket_name} with successful folder .")
            return 'active', instance_id

        elif state == 'open':
            save_spot_request_to_s3(s3_client, spot_tracking_s3_bucket_name, 'open', request_id, region)
            print(f"Spot request {request_id} is open. Saved to S3.")
            return 'open', request_id

        elif state == 'failed':
            print(f"Spot request {request_id} has failed.")
            # save_spot_request_to_s3(s3_client, spot_tracking_s3_bucket_name, 'failed', request_id, region)
            # print(f"Saved to S3 bucket {spot_tracking_s3_bucket_name} with failed folder .")
            ec2_client.cancel_spot_instance_requests(SpotInstanceRequestIds=[request_id])
            return 'failed', None

        elif state == 'cancelled':
            print(f"Spot request {request_id} has been cancelled already. No further action required.")
            # save_spot_request_to_s3(s3_client, spot_tracking_s3_bucket_name, 'failed', request_id, region)
            # print(f"Saved to S3 bucket {spot_tracking_s3_bucket_name} with failed folder .")
            return 'cancelled', None

        elif state in ['closed', 'marked-for-termination']:
            print(f"Spot request {request_id} is {state}. No further action required.")
            return state, None

        else:
            # save_spot_request_to_s3(s3_client, spot_tracking_s3_bucket_name, 'failed', request_id, region)
            # print(f"Saved to S3 bucket {spot_tracking_s3_bucket_name} with failed folder .")
            print(f"Spot request {request_id} is in an unexpected state: {state}.")
            return state, None

    except Exception as e:
        print(f"Error while handling spot request {request_id}: {e}")
        return 'error', None


def move_to_folder(request_id, region, source_folder, destination_folder):
    """
    Moves an S3 object from the source folder to the destination folder.

    Parameters:
    - request_id (str): ID of the spot instance request.
    - region (str): AWS region of the request.
    - source_folder (str): Source folder (or prefix) within the S3 bucket.
    - destination_folder (str): Destination folder (or prefix) within the S3 bucket.
    """
    source_key = f"{source_folder}/{region}|{request_id}.txt"
    destination_key = f"{destination_folder}/{region}|{request_id}.txt"

    # Log the action
    print(f"Moving {source_key} to {destination_key} in S3 bucket {spot_tracking_s3_bucket_name}...")

    # Copy the object to the destination folder
    s3_client.copy_object(
        Bucket=spot_tracking_s3_bucket_name,
        CopySource={'Bucket': spot_tracking_s3_bucket_name, 'Key': source_key},
        Key=destination_key
    )

    # Log the successful move
    print(f"Moved {source_key} to {destination_key} in S3 bucket {spot_tracking_s3_bucket_name}...")

    # Delete the original object from the source folder
    s3_client.delete_object(Bucket=spot_tracking_s3_bucket_name, Key=source_key)


def batch_launch_spot_instance(aws_credentials, number_of_spot_instances):
    user_data_encoded = generate_user_data_script(aws_credentials, sleep_time, complete_bucket_name)

    response = table.scan()

    items = response.get('Items', [])
    if not items:
        raise Exception("NoItemsAvailable: No items found in the response.")

    available_items = [item for item in items if item['region'] in target_regions]
    if not available_items:
        raise Exception("NoItemsAvailable: No items available in the specified target regions.")

    sorted_items = sorted(available_items, key=lambda x: float(x['price']))
    active_instance_count = 0

    for item in sorted_items:

        current_spot_request_ids = []

        region = item['region']
        availability_zone = item['availability_zone']
        spot_price = str(factor * item['price'])

        print(f"region: {region}")
        print(f"Availability zone: {availability_zone}")
        print(f"Original spot price: {str(item['price'])}")
        print(f"Factor: {factor}")
        print(f"New spot price: {spot_price}")

        ec2_client = boto3.client('ec2', region_name=region)
        ami_id = get_values_from_file('ami_ids.txt').get(region)
        security_group_ids = [get_values_from_file('security_group_ids.txt').get(region)]

        remaining_instances = number_of_spot_instances - active_instance_count

        print(f"Using On-Demand price: {on_demand_price}")
        try:
            response = ec2_client.request_spot_instances(
                # SpotPrice=spot_price,
                SpotPrice=str(on_demand_price),
                InstanceCount=remaining_instances,
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
            current_spot_request_ids.extend([x['SpotInstanceRequestId'] for x in response['SpotInstanceRequests']])

        except Exception as e:
            # If there's an error, print or log the error and continue to the next item
            print(f"Error occurred: {e}. Moving to the next item.")
            continue

        print(f"Sleep for {SLEEP_TIME_SPOT_REQUEST} seconds...")
        time.sleep(SLEEP_TIME_SPOT_REQUEST)

        for spot_request_id in current_spot_request_ids:
            status, result = handle_spot_request_status(ec2_client, spot_request_id, region)

            if status in ['active', 'open']:
                print(f"Status: {status}")
                type_of_result = 'Instance ID' if result.startswith('i') else 'Spot Request ID'
                print(f"Processed request {spot_request_id} successfully with {type_of_result}: {result}")
                active_instance_count += 1
            else:
                print(f"Spot request {spot_request_id} not successful with status {status}. Moving to the next item.")

            if active_instance_count >= number_of_spot_instances:
                # Once the required number of instances are successfully requested, break out of the loop.
                return

    raise Exception(
        "NoItemsAvailable: No items were successful after iterating through all options. -> retrying in 1 hour")


def list_request_ids_in_open_folder(bucket_name, folder):
    """
    Retrieve all filenames in the specified folder of an S3 bucket.

    Parameters:
    - bucket_name (str): The name of the S3 bucket.
    - folder (str): The folder name (prefix) within the bucket.

    Returns:
    - list: List of filenames within the specified folder.
    """
    s3_client = boto3.client('s3')

    # Ensure folder name ends with a "/"
    if not folder.endswith('/'):
        folder += '/'

    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=folder)
    filenames = []

    # Extract filenames from the response
    if 'Contents' in response:
        filenames.extend(item['Key'] for item in response['Contents'] if not item['Key'].startswith(f"{folder}open/"))

    # If there is "open/", exclude open/ in filenames
    if "open/" in filenames:
        filenames.remove("open/")

    return filenames


def organize_filenames(filenames):
    """
    Organize filenames into a dictionary with region as key and
    associated spot request IDs as a list of values.

    Parameters:
    - filenames (list): List of filenames in the format {region}|{spot_request_id}.txt.

    Returns:
    - dict: Dictionary with regions as keys and associated spot request IDs (without the .txt extension) as values.
    """
    organized_data = {}

    for filename in filenames:
        # Extracting region and spot_request_id from the filename
        # Also, remove any folder prefixes (e.g., "open/")
        parts = filename.split('/')[-1].split('|')

        # Safety check to ensure we have both region and spot_request_id
        if len(parts) == 2:
            region, request_with_extension = parts
            request_id = request_with_extension.replace('.txt', '')

            # Organize the data
            if region not in organized_data:
                organized_data[region] = []
            organized_data[region].append(request_id)

    return organized_data


import boto3


def get_spot_request_state_with_metadata(request_id, region):
    """
    Fetch the state of a given spot request ID and its check_count metadata from S3.

    :param request_id: The ID of the spot instance request.
    :param region: The AWS region where the request was made.
    :param bucket_name: The name of the S3 bucket.
    :param folder: The folder in the S3 bucket where the request is stored.
    :return: A tuple of the state of the spot request and the check_count metadata.
    """
    # Create an EC2 client
    ec2_client = boto3.client('ec2', region_name=region)
    # Create an S3 client
    s3_client = boto3.client('s3', region_name=region)

    # Initialize check_count to zero
    check_count = 0

    # Try to fetch the state of the spot request from EC2
    try:
        response = ec2_client.describe_spot_instance_requests(SpotInstanceRequestIds=[request_id])
        state = response['SpotInstanceRequests'][0].get('State') if response.get('SpotInstanceRequests') else None
    except Exception as e:
        print(f"Error fetching state for spot request ID {request_id}. Error: {e}")
        state = None

    # If the request is open, then retrieve the check_count metadata from S3
    if state == 'open':
        try:
            s3_object_key = f"open/{region}|{request_id}.txt"
            s3_response = s3_client.head_object(Bucket=spot_tracking_s3_bucket_name, Key=s3_object_key)
            # Extract check_count metadata if it exists
            check_count = int(s3_response['Metadata'].get('check_count', 0))
        except Exception as e:
            print(f"Error retrieving metadata for spot request ID {request_id} from S3. Error: {e}")

    # Return the state and check_count
    return state, check_count


def increment_check_count(request_id, region, check_count):
    """
    Increment the check_count metadata for the spot request object in S3.

    :param s3_client: The boto3 client for S3.
    :param bucket_name: The name of the S3 bucket.
    :param folder: The folder in the S3 bucket where the request is stored.
    :param request_id: The ID of the spot instance request.
    :param region: The AWS region where the request was made.
    :param check_count: The current check count to be incremented.
    :return: None
    """
    # Increment the check count
    new_check_count = check_count + 1

    # Generate the S3 object key
    s3_object_key = f"open/{region}|{request_id}.txt"

    # Copy the object to itself in S3, updating the metadata
    try:
        s3_client.copy_object(
            Bucket=spot_tracking_s3_bucket_name,
            CopySource={'Bucket': spot_tracking_s3_bucket_name, 'Key': s3_object_key},
            Key=s3_object_key,
            Metadata={'check_count': str(new_check_count)},
            MetadataDirective='REPLACE'
        )
        print(f"Incremented check_count to {new_check_count} for spot request {request_id}.")
    except Exception as e:
        print(f"Error incrementing check_count for spot request {request_id}. Error: {e}")


def lambda_handler(event, context):  # We don't need the event and context parameters in this case.
    try:
        open_request_ids = list_request_ids_in_open_folder(spot_tracking_s3_bucket_name, "open")
        print(f"Retrieved open request IDs from S3: {open_request_ids}")

        organized_spot_request_ids = organize_filenames(open_request_ids)
        print(f"Organized request IDs by region: {organized_spot_request_ids}")
        print(f"Number of regions with open request IDs: {len(organized_spot_request_ids)}")
        print(f"Total number of open request IDs: {sum(len(v) for v in organized_spot_request_ids.values())}")

        launch_count = 0  # Count of spot requests to be launched for this region

        for region, request_ids in organized_spot_request_ids.items():
            print(f"Processing request IDs for region: {region}")

            for request_id in request_ids:
                try:
                    current_state, check_count = get_spot_request_state_with_metadata(request_id, region)
                    print()
                    print(f"State for request ID {request_id}: {current_state}")

                    if current_state == 'active':
                        move_to_folder(request_id, region, 'open', 'successful')
                        print(f"Moved request ID {request_id} to 'successful' folder.")

                    elif current_state == 'open':
                        print(f"Request ID {request_id} is still open. Checking check count: {check_count}")
                        if check_count >= 3:
                            # Cancel and re-request the spot instance
                            print(f"Since the count is {check_count}, "
                                  f"canceling and incrementing check count for request ID {request_id}.")
                            ec2_client = boto3.client('ec2', region_name=region)
                            ec2_client.cancel_spot_instance_requests(SpotInstanceRequestIds=[request_id])
                            move_to_folder(request_id, region, 'open', 'failed')
                            launch_count += 1

                        else:
                            increment_check_count(request_id, region, check_count)
                            print(f"Incremented check count for request ID {request_id}.")

                    elif current_state in ['failed', 'terminated']:
                        launch_count += 1
                        print(f"State for request ID {request_id} is {current_state}. Moving to 'failed' folder.")
                        move_to_folder(request_id, region, 'open', 'failed')

                    elif current_state is None:  # Explicit check for None
                        launch_count += 1
                        print(f"State for request ID {request_id} is None. Moving to 'failed' folder.")
                        move_to_folder(request_id, region, 'open', 'failed')

                    else:
                        launch_count += 1
                        print(f"State for request ID {request_id} is {current_state}. No action required.")

                except Exception as inner_e:
                    if "InvalidSpotInstanceRequestID.NotFound" in str(inner_e):
                        move_to_folder(request_id, region, 'open', 'failed')
                        print(f"Error: Request ID {request_id} not found. Deleted from 'open' folder.")
                    else:
                        # If the error is of some other kind, print it
                        print(f"Error processing request ID {request_id}: {inner_e}")
        print(f"Deleted {launch_count} request IDs from 'open' folder.")

        if launch_count > 0:
            print(f"{launch_count} new spot requests to be launched.")
            print(f"Launching {launch_count} spot instances for the following regions: {target_regions}")
            aws_credentials = get_aws_credentials_from_file()
            batch_launch_spot_instance(aws_credentials, launch_count)

        else:
            print("No new spot requests to be launched.")

        if not open_request_ids:
            print("No Request IDs found in 'open' folder.")

    except Exception as e:
        print(f"Error in lambda handler: {e}")
        raise e
