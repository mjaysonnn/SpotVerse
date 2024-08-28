#!/bin/bash

SOURCE_BUCKET_PREFIX=$(awk -F "=" '/lambda_deployment_bucket_name/ {print $2}' ../conf.ini | tr -d ' ')
DEFAULT_REGION="us-east-1"
SOURCE_BUCKET_NAME="$SOURCE_BUCKET_PREFIX-$DEFAULT_REGION"

regions_string=$(awk -F "=" '/regions/ {print $2}' ../conf.ini | tr -d ' ')
declare -a REGIONS=($(echo "$regions_string" | tr "," " "))
echo "Regions: ${REGIONS[@]}"

# Variables
FILENAME="cloudwatch_spot_interruption.yaml"
STACK_NAME="CloudWatchSpotInterruption"
STACK_NAME=$(awk -F "=" '/stack_for_cloudwatch_for_spot_interrupted/ {print $2}' ../conf.ini | tr -d ' ')
DESIRED_STATUS="CREATE_COMPLETE"

for REGION in "${REGIONS[@]}"; do

  # Check if the stack exists in the current region
  STACK_EXISTS=$(aws cloudformation describe-stacks --region $REGION 2>/dev/null | grep $STACK_NAME)

  # If stack exists, delete it
  if [[ ! -z "$STACK_EXISTS" ]]; then
    echo "Stack $STACK_NAME exists in region $REGION. Deleting..."
    aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION

    echo "Waiting for stack to be deleted in region $REGION..."
    aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION
    echo "Stack $STACK_NAME in region $REGION deleted successfully."
  fi

  # Create a new stack in the current region
  echo "Creating new stack $STACK_NAME in region $REGION..."
  aws cloudformation create-stack --stack-name $STACK_NAME --template-body file://$FILENAME --capabilities CAPABILITY_NAMED_IAM --region $REGION --parameters ParameterKey=Region,ParameterValue=$REGION
  echo "Stack creation initiated for region $REGION. Please monitor its progress in the AWS CloudFormation console."

  echo "Starting to monitor the stack status in region: $REGION..."

  while true; do
    # Check the current status of the stack in the current region
    CURRENT_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region "$REGION" --query "Stacks[0].StackStatus" --output text)

    if [ "$CURRENT_STATUS" == "$DESIRED_STATUS" ]; then
      echo "Stack in region: $REGION has reached the desired status: $DESIRED_STATUS"
      break
    else
      echo "Current status in region: $REGION: $CURRENT_STATUS. Awaiting $DESIRED_STATUS..."
      sleep 10 # Pause for 10 seconds before checking again
    fi
  done

  echo "Monitoring for region: $REGION finished."
done


##!/bin/bash
#
#SOURCE_BUCKET_PREFIX=$(awk -F "=" '/lambda_deployment_bucket_name/ {print $2}' ../conf.ini | tr -d ' ')
#DEFAULT_REGION="us-east-1"
#SOURCE_BUCKET_NAME="$SOURCE_BUCKET_PREFIX-$DEFAULT_REGION"
#
#regions_string=$(awk -F "=" '/regions/ {print $2}' ../conf.ini | tr -d ' ')
#declare -a REGIONS=($(echo "$regions_string" | tr "," " "))
#echo "Regions: ${REGIONS[@]}"
#
## Variables
#FILENAME="cloudwatch_spot_interruption.yaml"
#STACK_NAME="CloudWatchSpotInterruption"
#DESIRED_STATUS="CREATE_COMPLETE"
#REGION="us-east-1"
#
## Check if the stack exists
#STACK_EXISTS=$(aws cloudformation describe-stacks --region $REGION | grep $STACK_NAME)
#
## If stack exists, delete it
#if [[ ! -z "$STACK_EXISTS" ]]; then
#  echo "Stack $STACK_NAME exists. Deleting..."
#  aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION
#
#  echo "Waiting for stack to be deleted..."
#  aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION
#  echo "Stack $STACK_NAME deleted successfully."
#fi
#
## Create a new stack
#echo "Creating new stack $STACK_NAME..."
#aws cloudformation create-stack --stack-name $STACK_NAME --template-body file://$FILENAME --capabilities CAPABILITY_NAMED_IAM --region $REGION
#echo "Stack creation initiated. Please monitor its progress in the AWS CloudFormation console."
#
#echo "Starting to monitor the stack status in region: $REGION..."
#
#while true; do
#  # Check the current status of the stack
#  CURRENT_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region "$REGION" --query "Stacks[0].StackStatus" --output text)
#
#  if [ "$CURRENT_STATUS" == "$DESIRED_STATUS" ]; then
#    echo "Stack in region: $REGION has reached the desired status: $DESIRED_STATUS"
#    break
#  else
#    echo "Current status in region: $REGION: $CURRENT_STATUS. Awaiting $DESIRED_STATUS..."
#    sleep 10 # Pause for 10 seconds before checking again
#  fi
#done
#
#echo "Monitoring for region: $REGION finished."
#
##aws cloudformation create-stack --stack-name $STACK_NAME --template-body file://$FILENAME --capabilities CAPABILITY_NAMED_IAM --region $REGION --parameters ParameterKey=LambdaSourceBucket,ParameterValue=$SOURCE_BUCKET_NAME
##aws cloudformation validate-template --template-body file://$FILENAME --region $REGION
#
##aws cloudformation create-stack --stack-name $STACK_NAME --template-body file://$FILENAME --capabilities CAPABILITY_NAMED_IAM --region $REGION
#
##aws cloudformation update-stack --stack-name $STACK_NAME --template-body file://$FILENAME --capabilities CAPABILITY_NAMED_IAM --region $REGION
