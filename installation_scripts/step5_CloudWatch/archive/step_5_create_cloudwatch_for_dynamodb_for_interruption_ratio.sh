#!/bin/bash

# Function to check the stack status
check_stack_status() {
  local desired_status=$1

  echo "Starting to monitor the stack status in region: $REGION..."

  while true; do
    # Check the current status of the stack
    CURRENT_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region "$REGION" --query "Stacks[0].StackStatus" --output text)

    if [ "$CURRENT_STATUS" == "$desired_status" ]; then
      echo "Stack in region: $REGION has reached the desired status: $desired_status"
      break
    else
      echo "Current status in region: $REGION: $CURRENT_STATUS. Awaiting $desired_status..."
      sleep 10 # Pause for 10 seconds before checking again
    fi
  done

  echo "Monitoring for region: $REGION finished."
}

create_or_update_stack() {
  if aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" &>/dev/null; then
    echo "Stack $STACK_NAME already exists, updating..."

    # Try to update the stack
    UPDATE_OUTPUT=$(aws cloudformation update-stack --stack-name "$STACK_NAME" --template-body file://"$FILENAME" --capabilities CAPABILITY_NAMED_IAM --region "$REGION" 2>&1)

    # Check if the update initiated successfully
    if echo "$UPDATE_OUTPUT" | grep -q "No updates are to be performed"; then
      echo "No updates needed for stack $STACK_NAME."
    else
      check_stack_status "$DESIRED_STATUS_UPDATE"
    fi

  else
    echo "Creating new stack $STACK_NAME..."
    aws cloudformation create-stack --stack-name "$STACK_NAME" --template-body file://"$FILENAME" --capabilities CAPABILITY_NAMED_IAM --region "$REGION"
    check_stack_status "$DESIRED_STATUS_CREATE"
  fi
}

######################  MAIN  ######################

# CloudFormation stack details
FILENAME="cloudformation_for_cloudwatch_for_dynamodb_for_spot_interruption_ratio.yaml"
STACK_NAME=$(awk -F "=" '/stack_for_cloudwatch_for_spot_interruption_ratio/ {print $2}' ../conf.ini | tr -d ' ')
DESIRED_STATUS_CREATE="CREATE_COMPLETE"
DESIRED_STATUS_UPDATE="UPDATE_COMPLETE"

REGION=$(awk -F "=" '/dynamodb_region/ {print $2}' ../conf.ini | tr -d ' ')

# Main execution
create_or_update_stack
