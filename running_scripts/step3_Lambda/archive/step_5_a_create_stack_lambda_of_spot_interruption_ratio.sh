#!/bin/bash

# Source the conda initialization script
source /Users/mj/opt/anaconda3/etc/profile.d/conda.sh# Now activate your environment
conda activate MultiCloudGalaxy

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

################################    #################################   #################################

# Initialize Global Variables
INITIAL_DIR="$PWD"
BUCKET_PREFIX=$(awk -F "=" '/lambda_deployment_bucket_name/ {print $2}' ../conf.ini | tr -d ' ')
FILENAME="cloudformation_template_for_lambda_spot_interruption_ratio.yaml"
STACK_NAME=$(awk -F "=" '/stack_for_lambda_for_spot_interruption_ratio/ {print $2}' ../conf.ini | tr -d ' ')
DESIRED_STATUS="CREATE_COMPLETE"
DESIRED_STATUS_FOR_UPDATE="UPDATE_COMPLETE"

LAMBDA_CODE_DIRECTORY="lambda_codes/lambda_spot_interruption_ratio_inserter"
LAMBDA_ZIP_FILE="lambda_spot_interruption_ratio_inserter_$(printf "%04d" $((RANDOM % 10000))).zip"

regions_string=$(awk -F "=" '/^default_region_for_lambda_for_spot_interruption_ratio[[:space:]]*=[[:space:]]*/ {print $2}' ../conf.ini | tr -d ' ')
REGIONS=($(echo "$regions_string" | tr "," " "))

echo "Regions: ${REGIONS[@]}"

echo "Preparing to execute python scripts"
declare -a scripts=("step_2_a_create_and_copy_security_group.py"
  "step_2_b_find_linux_ami_2_in_all_regions.py"
  "step_2_c_import_public_key_in_all_regions.py"
  "step_2_e_copy_aws_credentials.py")
# Always execute createStack_step2d_CopyConfIniFileToLambdaFolders.py
echo "Always executing step_2_d_copy_conf_ini.py..."
python3 step_2_d_copy_conf_ini.py
echo -n "Do you want to execute the remaining scripts? [yes/no]: "
read answer
case $answer in
[Yy]*)
  for script in "${scripts[@]}"; do
    echo "Executing $script..."
    python3 $script
  done
  ;;
[Nn]*)
  echo "Remaining scripts will not be executed. Continuing with the rest of the script..."
  ;;
*)
  echo "Please answer yes or no. Exiting..."
  exit
  ;;
esac
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
