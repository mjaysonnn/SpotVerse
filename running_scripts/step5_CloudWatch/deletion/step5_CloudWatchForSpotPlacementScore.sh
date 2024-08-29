#!/bin/bash

# Description: This script deletes the CloudFormation stack for the CloudWatch alarm that monitors the Spot instance placement score.

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

# ========================================
STACK_NAME=$(get_config_value "StackName_CloudWatchForSpotPlacementScore")
REGION=$(get_config_value "Region_DynamoForSpotPlacementScore")

# Check if the stack exists
STACK_EXISTS=$(aws cloudformation describe-stacks --region $REGION | grep $STACK_NAME)

# If stack exists, delete it
if [[ ! -z "$STACK_EXISTS" ]]; then
  echo "Stack $STACK_NAME exists. Deleting..."
  aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION

  echo "Waiting for stack to be deleted..."
  aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION
  echo "Stack $STACK_NAME deleted successfully."
fi
