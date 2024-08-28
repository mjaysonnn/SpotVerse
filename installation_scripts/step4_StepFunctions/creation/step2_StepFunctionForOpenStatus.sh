#!/bin/bash

# Single Region Deployment Script for Step Function for Open Spot Instance
CONDA_BASE=$(conda info --base)
source "$CONDA_BASE/etc/profile.d/conda.sh"

# Function to fetch account ID
fetch_account_id() {
  aws sts get-caller-identity --query Account --output text
}

# Function to create or update stack
deploy_stack() {
  local region=$1

  echo "Deploying to region: $region"

  if aws cloudformation describe-stacks --region "$region" --stack-name "$STACK_NAME" &>/dev/null; then
    echo "Stack exists, attempting update..."
    update_stack "$region"
  else
    echo "Stack does not exist, creating..."
    create_stack "$region"
  fi
}

# Function to create stack
create_stack() {
  local region=$1

  aws cloudformation create-stack \
    --region "$region" \
    --template-body file://"$TEMPLATE_FILE" \
    --stack-name "$STACK_NAME" \
    --parameters ParameterKey=AccountID,ParameterValue="$ACCOUNT_ID" ParameterKey=Region,ParameterValue="$region" ParameterKey=StateMachineName,ParameterValue="$STATE_MACHINE_NAME" \
    --capabilities CAPABILITY_IAM

  echo "Waiting for stack creation to complete..."
  aws cloudformation wait stack-create-complete --region "$region" --stack-name "$STACK_NAME"
}

# Function to update stack
update_stack() {
  local region=$1

  if ! aws cloudformation update-stack \
    --region "$region" \
    --template-body file://"$TEMPLATE_FILE" \
    --stack-name "$STACK_NAME" \
    --parameters ParameterKey=AccountID,ParameterValue="$ACCOUNT_ID" ParameterKey=Region,ParameterValue="$region" ParameterKey=StateMachineName,ParameterValue="$STATE_MACHINE_NAME" \
    --capabilities CAPABILITY_IAM 2>&1 | grep -q "No updates are to be performed"; then

    echo "Waiting for stack update to complete..."
    aws cloudformation wait stack-update-complete --region "$region" --stack-name "$STACK_NAME"
  else
    echo "No updates to perform for stack in region: $region"
  fi
}

# Function to update conf.ini with StateMachine ARN
update_conf_with_arn() {
  local region=$1
  local conf_file=$(find_config_file)

  local state_machine_arn=$(aws cloudformation describe-stacks --region "$region" --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='StateMachineArn'].OutputValue" --output text)
  arn_name_variable="StateMachineArnForLambdaOpenStatus-$region"
  echo "$arn_name_variable=$state_machine_arn"
  echo "Updating conf.ini file with $state_machine_arn for region $region"
  python3 update_arn_to_conf.py "$conf_file" "$arn_name_variable" "$state_machine_arn"

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

############################################    MAIN SCRIPT    ############################################

ACCOUNT_ID=$(fetch_account_id)
echo "Account ID: $ACCOUNT_ID"

# Configuration Variables
TEMPLATE_FILE="template_StepFunctionForOpenStatus.yaml"
STATE_MACHINE_NAME="StepFunctionForOpenStatus"

STACK_NAME=$(get_config_value "StackName_StepFunctionForOpenStatus")
default_region_string=$(get_config_value "Region_LambdaForCheckingSpotRequest")

REGIONS=($(echo "$default_region_string" | tr "," " "))

echo "Regions: ${REGIONS[@]}"

for REGION in "${REGIONS[@]}"; do
  deploy_stack "$REGION"
  update_conf_with_arn "$REGION"
done
