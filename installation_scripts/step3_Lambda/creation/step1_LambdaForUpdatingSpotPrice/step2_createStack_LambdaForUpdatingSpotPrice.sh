#!/bin/bash

# Single Lambda Deployment Script for Updating Spot Price

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

# Extract configurations from conf.ini
get_config_value() {
  local config_file=$(find_config_file)

  awk -F "=" "/$1/ {print \$2}" "$config_file" | tr -d ' '
}

# Monitor Stack Status until it reaches the desired state
monitor_stack_status() {
  local stack=$1
  local desired_status=$2
  local region=$3

  echo "Monitoring stack: $stack for status: $desired_status in region: $region..."

  while true; do
    CURRENT_STATUS=$(aws cloudformation describe-stacks --stack-name "$stack" --region "$region" --query "Stacks[0].StackStatus" --output text)

    if [ "$CURRENT_STATUS" == "$desired_status" ]; then
      echo "Stack $stack has reached the desired status: $desired_status"
      break
    else
      echo "Current status: $CURRENT_STATUS. Waiting for $desired_status..."
      sleep 10
    fi
  done
}

############################################    MAIN SCRIPT    ############################################


INITIAL_DIR="$PWD"
SOURCE_BUCKET_PREFIX=$(get_config_value 'lambda_deployment_bucket_name')
REGION=$(get_config_value 'Region_LambdaForUpdatingSpotPrice')
BUCKET_NAME_WITH_REGION="$SOURCE_BUCKET_PREFIX-$REGION"

FILENAME="LambdaForUpdatingSpotPrice.yaml"
STACK_NAME=$(get_config_value 'StackName_LambdaForUpdatingSpotPrice')

LAMBDA_CODE_DIRECTORY="lambda_codes"
LAMBDA_ZIP_FILE="lambda_for_update_spot_price_$(printf "%04d" $((RANDOM % 10000))).zip"

echo "Lambda Code Directory: $LAMBDA_CODE_DIRECTORY"

# Zip and upload Lambda function to S3
cd "$LAMBDA_CODE_DIRECTORY" || {
  echo "Failed to change directory to $LAMBDA_CODE_DIRECTORY. Exiting."
  exit 1
}

zip -r "$LAMBDA_ZIP_FILE" . -x "$LAMBDA_ZIP_FILE"
aws s3 cp "$LAMBDA_ZIP_FILE" "s3://$BUCKET_NAME_WITH_REGION/"
rm "$LAMBDA_ZIP_FILE"
cd "$INITIAL_DIR" || {
  echo "Failed to change back to the initial directory. Exiting."
  exit 1
}

# Check if the stack already exists
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &>/dev/null; then
  echo "Stack already exists. Updating..."

  aws cloudformation update-stack \
    --stack-name "$STACK_NAME" \
    --template-body file://"$FILENAME" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --parameters \
    ParameterKey=LambdaSourceBucket,ParameterValue="$BUCKET_NAME_WITH_REGION" \
    ParameterKey=LambdaCodeS3Key,ParameterValue="$LAMBDA_ZIP_FILE"

  monitor_stack_status "$STACK_NAME" "UPDATE_COMPLETE" "$REGION"
else
  echo "Stack does not exist. Creating..."

  aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body file://"$FILENAME" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --parameters \
    ParameterKey=LambdaSourceBucket,ParameterValue="$BUCKET_NAME_WITH_REGION" \
    ParameterKey=LambdaCodeS3Key,ParameterValue="$LAMBDA_ZIP_FILE"

  monitor_stack_status "$STACK_NAME" "CREATE_COMPLETE" "$REGION"
fi

echo "Script execution completed."
