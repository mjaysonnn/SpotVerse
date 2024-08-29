#!/bin/bash

# Single region deployment script for DynamoDB for Spot Interruption Frequency


# Function to get stack status
get_stack_status() {
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].StackStatus" \
    --output text 2>/dev/null
}

# Function to monitor stack status
monitor_stack_status() {
  while true; do
    stack_status=$(get_stack_status)
    echo "Status of $STACK_NAME: $stack_status"

    case "$stack_status" in
    CREATE_COMPLETE | UPDATE_COMPLETE | CREATE_FAILED | UPDATE_FAILED | ROLLBACK_COMPLETE)
      break
      ;;
    *)
      sleep 5
      ;;
    esac
  done
}

# Function to create stack
create_stack() {
  aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body "file://$FILENAME" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"
}

# Function to update stack
update_stack() {
  aws cloudformation update-stack \
    --stack-name "$STACK_NAME" \
    --template-body "file://$FILENAME" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"
}

# Main function to create or update the stack
deploy_stack() {
  stack_status=$(get_stack_status)

  # Check if the stack exists
  if [[ -z "$stack_status" ]]; then
    echo "Stack does not exist, creating..."
    create_stack
  else
    echo "Stack exists, updating..."
    update_stack
  fi

  monitor_stack_status

  if [[ "$stack_status" == "CREATE_COMPLETE" ]] || [[ "$stack_status" == "UPDATE_COMPLETE" ]]; then
    echo "Stack $STACK_NAME has been deployed successfully!"
  else
    echo "Stack $STACK_NAME deployment failed!"
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


################################################################ ############################################

echo "Starting to deploy the stack for creating IAM (LambdaAdmin) and DynamoDB resources..."
echo "Since dynamodb is central service, it is deployed in us-east-1 region."

# Variables
FILENAME="template_step3_DynamoForSpotInterruptionRatio.yaml"
#STACK_NAME=$(awk -F "=" '/StackName_DynamoForSpotInterruptionRatio/ {print $2}' ../conf.ini | tr -d ' ')
STACK_NAME=$(get_config_value "StackName_DynamoForSpotInterruptionRatio")

# Fetch REGION from ../conf.ini
#REGION=$(awk -F "=" '/Region_DynamoForSpotInterruptionRatio/ {print $2}' ../conf.ini | tr -d ' ')
REGION=$(get_config_value "Region_DynamoForSpotInterruptionRatio")

# Check if STACK_NAME and REGION were retrieved successfully
if [ -z "$STACK_NAME" ]; then
  echo "Error: STACK_NAME not found in ../conf.ini"
  exit 1
fi

if [ -z "$REGION" ]; then
  echo "Error: REGION not found in ../conf.ini"
  exit 1
fi

# Display the retrieved values
echo "STACK_NAME: $STACK_NAME"
echo "REGION: $REGION"

deploy_stack
