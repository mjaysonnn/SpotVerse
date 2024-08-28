#!/bin/bash

# Multiple regions are supported. The script will deploy the CloudFormation template to each region.

CONDA_BASE=$(conda info --base)
source "$CONDA_BASE/etc/profile.d/conda.sh"

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

get_config_value() {
  local config_file=$(find_config_file)

  awk -F "=" "/$1/ {print \$2}" "$config_file" | tr -d ' '
}

deploy_regions() {
  for region in "${regions[@]}"; do
    echo "Deploying CloudFormation template for $region..."
    stack_name="${s3_creation_stack_name_prefix}-$region"
    echo "Stack name: $stack_name"

    aws cloudformation deploy \
      --template-file "$DIR/$s3_bucket_template" \
      --stack-name "$stack_name" \
      --parameter-overrides BucketPrefix="$lambda_deployment_zip_bucket" \
      --region "$region"
  done
}

check_stack_status() {
  local stack_name="$1"
  local region="$2"

  while true; do
    status=$(aws cloudformation describe-stacks --stack-name "$stack_name" --region "$region" --query "Stacks[0].StackStatus" --output text)
    echo "Status of $stack_name: $status"

    [[ "$status" =~ (CREATE_COMPLETE|ROLLBACK_COMPLETE|CREATE_FAILED) ]] && break
    sleep 5
  done
}

############################################## MAIN ##############################################

# Store the directory of the script to access related files.
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR" || exit  # Ensure the script's directory is the current working directory

# Fetch and assign configuration values.
lambda_deployment_zip_bucket=$(get_config_value 'lambda_deployment_bucket_name')
s3_creation_stack_name_prefix=$(get_config_value 'StackName_S3ForStoringLambdaCodes')
s3_bucket_template="template_step3_S3ForStoringLambdaCodes.yaml"

#regions_string=$(awk -F "=" '/^regions_to_use[[:space:]]*=[[:space:]]*/ {print $2}' ../../conf.ini | tr -d ' ')
regions_string=$(get_config_value 'regions_to_use')

regions=($(echo "$regions_string" | tr "," " "))
echo "Deploying to regions: ${regions[@]}"

deploy_regions

for region in "${regions[@]}"; do
  check_stack_status "${s3_creation_stack_name_prefix}-$region" "$region"
done

echo "Done"
