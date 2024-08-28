#!/bin/bash

# Single Region Deployment Script for CloudWatch Event Rule and Lambda Function for Step Function for Open Spot Status

CONDA_BASE=$(conda info --base)
source "$CONDA_BASE/etc/profile.d/conda.sh"

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
  exit 1
}

# Function to extract a value from the conf.ini file
get_config_value() {
  local key=$1
  local config_file=$(find_config_file)

  if [[ -f "$config_file" ]]; then
    awk -F "=" "/^$key[[:space:]]*=[[:space:]]*/ {print \$2}" "$config_file" | tr -d ' '
  else
    echo "Error: Configuration file not found." >&2
    exit 1
  fi
}

# Deploy stack (create or update) to the specified region
deploy_stack_to_region() {
  local REGION=$1
  local STATE_MACHINE_ARN=$(get_config_value "StateMachineArnForLambdaOpenStatus-$REGION")
  echo "Step Function ARN for region $REGION: $STATE_MACHINE_ARN"

  if aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" &>/dev/null; then
    echo "Stack $STACK_NAME exists in region $REGION. Updating..."
    aws cloudformation update-stack \
      --stack-name "$STACK_NAME" \
      --template-body file://"$FILENAME" \
      --capabilities CAPABILITY_NAMED_IAM \
      --region "$REGION" \
      --parameters ParameterKey=Region,ParameterValue="$REGION" ParameterKey=StateMachineArn,ParameterValue="$STATE_MACHINE_ARN"
    check_stack_status "$REGION" "UPDATE_COMPLETE"
  else
    echo "Creating new stack $STACK_NAME in region $REGION..."
    aws cloudformation create-stack \
      --stack-name "$STACK_NAME" \
      --template-body file://"$FILENAME" \
      --capabilities CAPABILITY_NAMED_IAM \
      --region "$REGION" \
      --parameters ParameterKey=Region,ParameterValue="$REGION" ParameterKey=StateMachineArn,ParameterValue="$STATE_MACHINE_ARN"
    check_stack_status "$REGION" "CREATE_COMPLETE"
  fi
}

# Monitor stack status until the desired status is reached
check_stack_status() {
  local REGION=$1
  local DESIRED_STATUS=$2

  echo "Starting to monitor the stack status in region: $REGION..."

  while true; do
    local CURRENT_STATUS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query "Stacks[0].StackStatus" --output text)

    if [ "$CURRENT_STATUS" == "$DESIRED_STATUS" ]; then
      echo "Stack in region: $REGION has reached the desired status: $DESIRED_STATUS"
      break
    else
      echo "Current status in region: $REGION: $CURRENT_STATUS. Awaiting $DESIRED_STATUS..."
      sleep 5
    fi
  done

  echo "Monitoring for region: $REGION finished."
}

####################################################################################################

# Variables
#default_region_string=$(awk -F "=" '/^Region_LambdaForCheckingSpotRequest[[:space:]]*=[[:space:]]*/ {print $2}' ../conf.ini | tr -d ' ')
default_region_string=$(get_config_value "Region_LambdaForCheckingSpotRequest")
REGIONS=($(echo "$default_region_string" | tr "," " "))

FILENAME="template_CloudWatchForLambdaForStepFunctionForOpenStatus.yaml"
STACK_NAME=$(get_config_value "StackName_CloudWatchForOpenSpot")

echo "Regions: ${REGIONS[@]}"

for REGION in "${REGIONS[@]}"; do
  echo "Deploying stack to region: $REGION"
  deploy_stack_to_region "$REGION"
done
