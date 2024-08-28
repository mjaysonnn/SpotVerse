#!/bin/bash

# Single region deletion script for DynamoDB for Spot Interruption Frequency

# Function: monitor_stack_deletion_status
# Continuously checks the deletion status of a specified AWS CloudFormation stack.
monitor_stack_deletion_status() {
  while true; do
    # Retrieve the current status of the stack and suppre
    # ss error messages.
    stack_status=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].StackStatus" --output text 2>/dev/null)

    # Check if the stack is no longer present, indicating successful deletion.
    if [ $? -ne 0 ]; then
      echo "Stack $STACK_NAME has been deleted successfully!"
      break
    fi

    # Output the current status of the stack to the console.
    echo "Status of $STACK_NAME: $stack_status"

    # Check various potential statuses and act accordingly.
    case "$stack_status" in
    DELETE_COMPLETE)
      echo "Stack $STACK_NAME has been deleted successfully!"
      break
      ;;
    DELETE_FAILED)
      echo "Stack $STACK_NAME deletion failed!"
      break
      ;;
    # If the deletion is still in process, wait for 5 seconds before checking again.
    *)
      sleep 5
      ;;
    esac
  done
}

# Function: delete_stack
# Initiates the deletion of the specified AWS CloudFormation stack
# and monitors its status.
delete_stack() {
  # Initiate stack deletion.
  aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION

  # Notify that the deletion process has begun.
  echo "Initiated deletion for stack: $STACK_NAME"

  # Monitor the deletion status.
  monitor_stack_deletion_status
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

# =============================================================================

# Variables
# Extract the stack name from a configuration file.
STACK_NAME=$(get_config_value "StackName_DynamoForSpotInterruptionRatio")
REGION=$(get_config_value "Region_DynamoForSpotInterruptionRatio")

# Execute the delete_stack function.
delete_stack
