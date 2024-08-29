#!/bin/bash

# Multi-Region Lambda Deployment Script

# Function to Zip and Upload Lambda Code to S3
zip_and_upload() {
  cd "$LAMBDA_CODE_DIRECTORY" || {
    echo "Directory $LAMBDA_CODE_DIRECTORY not found!"
    exit 1
  }
  echo "Zipping the Python file..."
  zip -r "$LAMBDA_ZIP_FILE" . -x "*$LAMBDA_ZIP_FILE"
  echo "Uploading the zip file to the S3 bucket..."
  aws s3 cp "$LAMBDA_ZIP_FILE" "s3://$1/"
  rm "$LAMBDA_ZIP_FILE"
  cd "$INITIAL_DIR" || exit
}

# Function to Handle CloudFormation Stack Creation and Updates
manage_cloudformation_stack() {
  REGION=$1
  STATUS_TO_CHECK=$2
  OPERATION=$3
  PARAMS="--stack-name $STACK_NAME --template-body file://$FILENAME --capabilities CAPABILITY_NAMED_IAM --region $REGION --parameters ParameterKey=LambdaCodeBucket,ParameterValue=$4 ParameterKey=LambdaCodeS3Key,ParameterValue=$LAMBDA_ZIP_FILE"

  if [ "$OPERATION" == "create" ]; then
    aws cloudformation create-stack $PARAMS
  else
    aws cloudformation update-stack $PARAMS
  fi

  echo "Monitoring stack status in region: $REGION..."
  while true; do
    CURRENT_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region "$REGION" --query "Stacks[0].StackStatus" --output text)
    if [ "$CURRENT_STATUS" == "$STATUS_TO_CHECK" ]; then
      echo "Stack in region: $REGION has reached the desired status: $STATUS_TO_CHECK"
      break
    else
      echo "Current status in region: $REGION: $CURRENT_STATUS. Awaiting $STATUS_TO_CHECK..."
      sleep 10
    fi
  done
  echo "Monitoring for region: $REGION finished."
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

################################################################    #################################   #################################
# Initialize Global Variables
INITIAL_DIR="$PWD"

BUCKET_PREFIX=$(get_config_value "lambda_deployment_bucket_name")
FILENAME="template_LambdaForNewSpotInstance.yaml" # Assuming this is static and doesn't need fetching
STACK_NAME=$(get_config_value "StackName_LambdaForNewSpotInstance")
DESIRED_STATUS="CREATE_COMPLETE"            # Assuming static value
DESIRED_STATUS_FOR_UPDATE="UPDATE_COMPLETE" # Assuming static value
regions_string=$(get_config_value "regions_to_use")

# Verify if the variables were set
if [ -z "$BUCKET_PREFIX" ] || [ -z "$STACK_NAME" ] || [ -z "$regions_string" ]; then
  echo "Error: Failed to retrieve configuration values from conf.ini"
  exit 1
fi

REGIONS=($(echo "$regions_string" | tr "," " "))
echo "Regions: ${REGIONS[@]}"

LAMBDA_CODE_DIRECTORY="lambda_codes"
LAMBDA_ZIP_FILE="lambda_new_spot_instance_$(printf "%04d" $((RANDOM % 10000))).zip"

#
#echo "Preparing to execute python scripts"
#
#declare -a scripts=("createStack_step2a_CreateAndCopySecurityGroup.py"
#  "createStack_step2b_FindLinuxAMI.py"
#  "createStack_step2c_ImportKeyPair.py"
#  "createStack_step2e_CopyCredentialsToLambdaFolders.py")
#
#
## Always execute createStack_step2d_CopyConfIniFileToLambdaFolders.py
#echo "Always executing step_2_d_copy_conf_ini.py..."
##$PYTHON_CMD createStack_step2d_CopyConfIniFileToLambdaFolders.py
#python3 createStack_step2d_CopyConfIniFileToLambdaFolders.py
#
#echo "Scripts to be executed:"
#for script in "${scripts[@]}"; do
#    echo "$script"
#done
#echo -n "Do you want to execute the remaining scripts? [yes/no]: "
#
#read answer
#
#case $answer in
#[Yy]*)
#  for script in "${scripts[@]}"; do
#    echo "Executing $script..."
##    $PYTHON_CMD $script
#     python3 $script
#  done
#  ;;
#[Nn]*)
#  echo "Remaining scripts will not be executed. Continuing with the rest of the script..."
#  ;;
#*)
#  echo "Please answer yes or no. Exiting..."
#  exit
#  ;;
#esac

# Iterating over each region, creating bucket name, and calling `zip_and_upload`
for REGION in "${REGIONS[@]}"; do
  EACH_REGION_BUCKET_NAME="$BUCKET_PREFIX-$REGION"
  zip_and_upload "$EACH_REGION_BUCKET_NAME"
done

# Pause and wait for user input.
#echo "Check if $LAMBDA_ZIP_FILE files in $BUCKET_PREFIX are shown. Press any key to continue..."
#read -r

# Handle CloudFormation Stacks Across All Specified Regions
for REGION in "${REGIONS[@]}"; do
  echo "Managing stack for region: $REGION..."
  EACH_REGION_BUCKET_NAME="$BUCKET_PREFIX-$REGION"
  STACK_EXISTS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region "$REGION" 2>&1 || true)
  if [[ $STACK_EXISTS =~ "does not exist" ]]; then
    echo "Stack does not exist in region: $REGION. Creating..."
    manage_cloudformation_stack "$REGION" "$DESIRED_STATUS" "create" "$EACH_REGION_BUCKET_NAME"
  else
    echo "Stack already exists in region: $REGION. Updating..."
    manage_cloudformation_stack "$REGION" "$DESIRED_STATUS_FOR_UPDATE" "update" "$EACH_REGION_BUCKET_NAME"
  fi
done
