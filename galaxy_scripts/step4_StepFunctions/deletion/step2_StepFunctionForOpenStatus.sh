#!/bin/bash

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

# ================ Main Script ================
# Configuration Variables
#STACK_NAME=$(awk -F "=" '/StackName_StepFunctionForOpenStatus/ {print $2}' ../conf.ini | tr -d ' ')
STACK_NAME=$(get_config_value "StackName_StepFunctionForOpenStatus")
# Fetching Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account ID: $ACCOUNT_ID"
# Fetching regions from conf.ini
#regions_string=$(awk -F "=" '/Region_LambdaForCheckingSpotRequest/ {print $2}' ../conf.ini | tr -d ' ')
regions_string=$(get_config_value "Region_LambdaForCheckingSpotRequest")
declare -a REGIONS=($(echo "$regions_string" | tr "," " "))
echo "Regions: ${REGIONS[@]}"

delete_stack() {
  local region=$1
  echo "Checking for stack in $region region..."

  # Check if the stack exists and initiate deletion
  if aws cloudformation describe-stacks --region "$region" --stack-name "$STACK_NAME" &>/dev/null; then
    echo "Stack $STACK_NAME exists in $region. Initiating deletion..."
    aws cloudformation delete-stack --region "$region" --stack-name "$STACK_NAME"

    # Wait for the stack to be deleted
    echo "Waiting for stack $STACK_NAME to be deleted in $region..."
    while aws cloudformation describe-stacks --region "$region" --stack-name "$STACK_NAME" &>/dev/null; do
      echo "Stack $STACK_NAME is still being deleted in $region..."
      sleep 10  # Wait for 10 seconds before checking again
    done

    echo "Stack $STACK_NAME deleted successfully in $region."
  else
    echo "Stack $STACK_NAME does not exist in $region. Skipping..."
  fi
}

# Initiate deletion of all found stacks
for region in "${REGIONS[@]}"; do
  delete_stack "$region" &
done

wait

echo "All stacks processed for deletion."