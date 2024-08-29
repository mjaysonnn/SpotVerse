#!/bin/bash

# CloudFormation stack details

STACK_NAME=$(awk -F "=" '/stack_for_cloudwatch_for_spot_interruption_ratio/ {print $2}' ../conf.ini | tr -d ' ')

#REGION="us-east-1"
REGION=$(awk -F "=" '/dynamodb_region/ {print $2}' ../conf.ini | tr -d ' ')

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
