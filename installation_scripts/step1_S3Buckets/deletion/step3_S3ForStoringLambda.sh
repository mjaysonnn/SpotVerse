#!/bin/bash

CONDA_BASE=$(conda info --base)
source "$CONDA_BASE/etc/profile.d/conda.sh"

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

# Function to delete a CloudFormation stack
delete_cfn_stack() {
  local stack_name=$1
  local region=${2:-} # Default to null (for no region)

  echo "Deleting CloudFormation stack: $stack_name..."
  aws cloudformation delete-stack --stack-name "$stack_name" ${region:+--region "$region"}
  aws cloudformation wait stack-delete-complete --stack-name "$stack_name" ${region:+--region "$region"}
  echo "Stack $stack_name deleted."
}

####################################################################################################
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"  # Ensure the script's directory is the current working directory

# Example of setting the regions_string variable using the get_config_value function
regions_string=$(get_config_value "regions_to_use")
if [[ -n "$regions_string" ]]; then
    echo "Regions to use: $regions_string"
else
    echo "Error: Failed to obtain regions from configuration." >&2
fi

# Example of setting the regions_string variable using the get_config_value function
regions_string=$(get_config_value "regions_to_use")
if [[ -n "$regions_string" ]]; then
    echo "Regions to use: $regions_string"
else
    echo "Error: Failed to obtain regions from configuration." >&2
fi

# Fetch and assign configurations
regions=($(echo "$regions_string" | tr "," " "))
echo regions: "${regions[@]}"

s3_creation_stack_name_prefix=$(get_config_value 'StackName_S3ForStoringLambdaCodes')

# Execute Python script to remove objects in buckets
echo "Removing all objects in the buckets..."
python3 remove_all_objects_in_buckets.py

# Delete CloudFormation stacks in specified regions
for region in "${regions[@]}"; do
  delete_cfn_stack "${s3_creation_stack_name_prefix}-$region" "$region"
done

echo "Done."
