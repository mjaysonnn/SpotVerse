#!/bin/bash

# This is for the Lambda layer that contains the spotinfo executable

source /Users/mj/opt/anaconda3/etc/profile.d/conda.sh
conda activate MultiCloudGalaxy

# Extract configurations from conf.ini

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

#================================================================ =================================================================

aws_region=$(get_config_value 'Region_LambdaForInterruptionRatio')

echo "Starting the script to prepare and deploy the spotinfo Lambda layer..."

# Source the conda initialization script to setup the environment

# Check if spotinfo executable exists
if [ ! -f layer/bin/spotinfo ]; then
  echo "Spotinfo executable not found. Downloading..."
  wget https://github.com/alexei-led/spotinfo/releases/download/1.0.7/spotinfo_linux_amd64 -O spotinfo
  chmod +x spotinfo

  mkdir -p layer/bin
  mv spotinfo layer/bin/
else
  echo "Spotinfo executable already exists. Skipping download."
fi

# Change to the layer directory or exit if it fails
cd layer || (echo "Failed to change to layer directory" && exit)
# If the zip file doesn't exist, create it
if [ ! -f spotinfo_layer.zip ]; then
  echo "Creating the zip file for the Lambda layer..."
  zip -r spotinfo_layer.zip .
else
  echo "Zip file already exists. Skipping zip creation."
fi

# Publish the layer version to AWS Lambda in the specified region and capture the new version ARN
echo "Publishing the Lambda layer in region $aws_region..."
layer_version_arn=$(aws lambda publish-layer-version \
  --layer-name spotinfo-layer \
  --zip-file fileb://spotinfo_layer.zip \
  --query 'LayerVersionArn' \
  --output text \
  --region $aws_region)

echo "Layer Version ARN: $layer_version_arn"

# Update the Lambda function configuration with the new layer version in the specified region
echo "Updating Lambda function configuration with the new layer version in region $aws_region..."
aws lambda update-function-configuration \
  --function-name "lambda_spot_interruption_ratio_inserter" \
  --layers $layer_version_arn \
  --region $aws_region

echo "Script completed successfully!"
