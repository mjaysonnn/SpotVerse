#!/bin/bash

# This is for updating the Spot Interruption Frequency in DynamoDB.

source /Users/mj/opt/anaconda3/etc/profile.d/conda.sh
conda activate MultiCloudGalaxy

# Function to check the stack status
check_stack_status() {
  local stack_name=$1
  local desired_status=$2
  local region=$3

  echo "Starting to monitor the stack status in region: $region..."

  while true; do
    # Check the current status of the stack
    CURRENT_STATUS=$(aws cloudformation describe-stacks --stack-name "$stack_name" --region "$region" --query "Stacks[0].StackStatus" --output text)

    if [ "$CURRENT_STATUS" == "$desired_status" ]; then
      echo "Stack in region: $region has reached the desired status: $desired_status"
      break
    else
      echo "Current status in region: $region: $CURRENT_STATUS. Awaiting $desired_status..."
      sleep 10 # Pause for 10 seconds before checking again
    fi
  done

  echo "Monitoring for region: $region finished."
}

create_or_update_stack() {
  local stack_name=$1
  local file_name=$2
  local region=$3
  local status_create=$4
  local status_update=$5

  if aws cloudformation describe-stacks --region "$region" --stack-name "$stack_name" &>/dev/null; then
    echo "Stack $stack_name already exists, updating..."

    # Try to update the stack
    aws cloudformation update-stack --stack-name "$stack_name" --template-body file://"$file_name" --capabilities CAPABILITY_NAMED_IAM --region "$region" --parameters ParameterKey=LambdaFunctionRegion,ParameterValue="$region"

    check_stack_status "$stack_name" "$status_update" "$region"

  else
    echo "Creating new stack $stack_name..."
    aws cloudformation create-stack --stack-name "$stack_name" --template-body file://"$file_name" --capabilities CAPABILITY_NAMED_IAM --region "$region" --parameters ParameterKey=LambdaFunctionRegion,ParameterValue="$region"

    check_stack_status "$stack_name" "$status_create" "$region"
  fi
}

# Function to find the conf.ini file by searching up the directory tree
find_config_file() {
  local current_dir=$(pwd)
  local root_dir="/"

  while [[ "$current_dir" != "$root_dir" ]]; do
    if [[ -f "$current_dir/conf.ini" ]]; then
      echo "$current_dir/conf.ini"
      return
    fi
    current_dir=$(dirname "$current_dir")
  done

  echo "conf.ini not found." >&2
  return 1
}

# Function to extract a value from the conf.ini file
get_config_value() {
  local key=$1
  local config_file=$(find_config_file)

  if [[ -f "$config_file" ]]; then
    awk -F "=" "/^$key[[:space:]]*=[[:space:]]*/ {print \$2}" "$config_file" | tr -d ' '
  else
    echo "Error: Configuration file not found." >&2
    return 1
  fi
}


######################  MAIN  ######################
#REGION=$(awk -F "=" '/Region_DynamoForSpotInterruptionRatio/ {print $2}' ../conf.ini | tr -d ' ')
REGION=$(get_config_value "Region_DynamoForSpotInterruptionRatio")
# CloudFormation stack details
FILENAME="template_step4_CloudWatchForSpotInterruptionRatio.yaml"
#STACK_NAME=$(awk -F "=" '/StackName_CloudwatchForSpotInterruptionRatio/ {print $2}' ../conf.ini | tr -d ' ')
STACK_NAME=$(get_config_value "StackName_CloudwatchForSpotInterruptionRatio")
DESIRED_STATUS_CREATE="CREATE_COMPLETE"
DESIRED_STATUS_UPDATE="UPDATE_COMPLETE"

# Main execution
create_or_update_stack "$STACK_NAME" "$FILENAME" "$REGION" "$DESIRED_STATUS_CREATE" "$DESIRED_STATUS_UPDATE"
