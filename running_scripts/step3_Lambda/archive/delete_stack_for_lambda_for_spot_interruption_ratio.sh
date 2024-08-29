#!/bin/bash

INITIAL_DIR="$PWD"
echo "Initial directory: $INITIAL_DIR"

STACK_NAME=$(awk -F "=" '/stack_for_lambda_layer_for_spot_interruption_ratio/ {print $2}' ../conf.ini | tr -d ' ')

echo "Deleting CloudFormation stack: $STACK_NAME..."
aws cloudformation delete-stack --stack-name $STACK_NAME

while true; do
  # Fetch the current status of the stack
  STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME 2>&1)

  # Check if the stack does not exist or there's an error indicating that it's deleted
  if [[ $STACK_STATUS == *"does not exist"* ]]; then
    echo "Stack $STACK_NAME has been deleted."
    break
  elif [[ $STACK_STATUS == *"DELETE_IN_PROGRESS"* ]]; then
    echo "Stack $STACK_NAME deletion is in progress..."
  elif [[ $STACK_STATUS == *"DELETE_FAILED"* ]]; then
    echo "Stack $STACK_NAME deletion failed!"
    exit 1
  else
    echo "Stack $STACK_NAME is in an unexpected state: $STACK_STATUS"
    exit 1
  fi

  sleep 10 # Wait for 10 seconds before checking again
done
