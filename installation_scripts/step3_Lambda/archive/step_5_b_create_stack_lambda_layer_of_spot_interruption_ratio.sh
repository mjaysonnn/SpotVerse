#!/bin/bash

echo "Starting the script to prepare and deploy the spotinfo Lambda layer..."

# Source the conda initialization script to setup the environment
echo "Sourcing the conda initialization script..."
source /Users/mj/opt/anaconda3/etc/profile.d/conda.sh# Now activate your environment
echo "Activating the MultiCloudGalaxy conda environment..."
conda activate MultiCloudGalaxy

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

# Publish the layer version to AWS Lambda and capture the new version ARN
echo "Publishing the Lambda layer..."
layer_version_arn=$(aws lambda publish-layer-version \
  --layer-name spotinfo-layer \
  --zip-file fileb://spotinfo_layer.zip \
  --query 'LayerVersionArn' \
  --output text)

echo "Layer Version ARN: $layer_version_arn"

# Update the Lambda function configuration with the new layer version
echo "Updating Lambda function configuration with the new layer version..."
aws lambda update-function-configuration \
  --function-name "lambda_spot_interruption_ratio_inserter" \
  --layers $layer_version_arn

echo "Script completed successfully!"
