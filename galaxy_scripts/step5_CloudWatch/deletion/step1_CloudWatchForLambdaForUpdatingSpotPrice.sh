#!/bin/bash



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


#regions_string=$(awk -F "=" '/Region_DynamodbForSpotPrice/ {print $2}' ../conf.ini | tr -d ' ')
regions_string=$(get_config_value "Region_DynamodbForSpotPrice")
declare -a REGIONS=($(echo "$regions_string" | tr "," " "))
echo "Regions: ${REGIONS[@]}"

#STACK_NAME=$(awk -F "=" '/StackName_CloudWatchForSpotPrice/ {print $2}' ../conf.ini | tr -d ' ')
#REGION=$(awk -F "=" '/Region_DynamodbForSpotPrice/ {print $2}' ../conf.ini | tr -d ' ')
STACK_NAME=$(get_config_value "StackName_CloudWatchForSpotPrice")

for REGION in "${REGIONS[@]}"; do

  # Fetch Step Function ARN for the current region from conf.ini (you can remove this if it's not needed in deletion)
#  STATE_MACHINE_ARN=$(awk -F "=" "/StateMachineArnFor-$REGION/ {print \$2}" ../conf.ini | tr -d ' ')

  # Check if the stack exists in the current region
  STACK_EXISTS=$(aws cloudformation describe-stacks --region $REGION 2>/dev/null | grep $STACK_NAME)

  # If stack exists, delete it
  if [[ ! -z "$STACK_EXISTS" ]]; then
    echo "Stack $STACK_NAME exists in region $REGION. Deleting..."
    aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION

    echo "Waiting for stack to be deleted in region $REGION..."
    aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION
    echo "Stack $STACK_NAME in region $REGION deleted successfully."
  else
    echo "Stack $STACK_NAME does not exist in region $REGION. No deletion required."
  fi
done
