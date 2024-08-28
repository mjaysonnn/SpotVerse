#!/bin/bash

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

#########################M ain Script ######################################

# Variables
STACK_NAME=$(get_config_value "StackName_LambdaForOpenStatus")
regions_string=$(get_config_value "Region_LambdaForCheckingSpotRequest")

REGIONS=($(echo "$regions_string" | tr "," " "))
echo "Regions: ${REGIONS[@]}"

for REGION in "${REGIONS[@]}"; do

  echo "Executing for region: $REGION..."

  # Fetch the current status of the stack
  STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION 2>&1)

  # Check if the stack exists
  if [[ $STACK_STATUS == *"does not exist"* ]]; then
    echo "Stack $STACK_NAME does not exist in region: $REGION. Skipping..."
    continue
  fi

  echo "Deleting CloudFormation stack: $STACK_NAME in region: $REGION..."
  aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION

  while true; do
    # Fetch the current status of the stack
    STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION 2>&1)

    # Check if the stack does not exist or there's an error indicating that it's deleted
    if [[ $STACK_STATUS == *"does not exist"* ]]; then
      echo "Stack $STACK_NAME in region: $REGION has been deleted."
      break
    elif [[ $STACK_STATUS == *"DELETE_IN_PROGRESS"* ]]; then
      echo "Stack $STACK_NAME in region: $REGION deletion is in progress..."
    elif [[ $STACK_STATUS == *"DELETE_FAILED"* ]]; then
      echo "Stack $STACK_NAME in region: $REGION deletion failed!"
      exit 1
    else
      echo "Stack $STACK_NAME in region: $REGION is in an unexpected state: $STACK_STATUS"
      exit 1
    fi

    sleep 10 # Wait for 10 seconds before checking again
  done

  echo "Deletion for region: $REGION finished."

done
