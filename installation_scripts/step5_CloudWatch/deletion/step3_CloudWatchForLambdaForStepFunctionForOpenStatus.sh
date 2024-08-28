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

# CloudFormation stack details
#STACK_NAME=$(awk -F "=" '/StackName_CloudWatchForOpenSpot/ {print $2}' ../conf.ini | tr -d ' ')
STACK_NAME=$(get_config_value "StackName_CloudWatchForOpenSpot")
#REGION=$(awk -F "=" '/Region_LambdaForCheckingSpotRequest/ {print $2}' ../conf.ini | tr -d ' ')
REGION=$(get_config_value "Region_LambdaForCheckingSpotRequest")

echo "Deleting CloudFormation stack $STACK_NAME in region $REGION..."

#!/bin/bash

# Assuming REGION and STACK_NAME are already set

# Check if the stack exists
if aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" &>/dev/null; then
  echo "Stack $STACK_NAME exists. Deleting..."
  aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"

  echo "Waiting for stack to be deleted..."
  if aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"; then
    echo "Stack $STACK_NAME deleted successfully."
  else
    echo "Failed to delete stack $STACK_NAME or deletion timed out."
  fi
else
  echo "Stack $STACK_NAME does not exist in region $REGION."
fi

