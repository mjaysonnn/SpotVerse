#!/bin/bash

# List of scripts to be executed in order
declare -a scripts=(
    "step1_S3Buckets/deletion/step1_S3ForCompleteAndInterruption.py"
    "step1_S3Buckets/deletion/step2_S3ForOpenStatus.py"
    "step1_S3Buckets/deletion/step3_S3ForStoringLambda.sh"

    "step2_IAMAndDynamoDB/deletion/step1_DynamoForSpotPrice.sh"
    "step2_IAMAndDynamoDB/deletion/step2_IAMForAdmin.sh"
    "step2_IAMAndDynamoDB/deletion/step3_DynamoForSpotInterruptionRatio.sh"
    "step2_IAMAndDynamoDB/deletion/step4_DynamoForSpotPlacementScore.sh"

    "step3_Lambda/deletion/step1_LambdaForUpdatingSpotPrice/step1_LambdaForUpdatingSpotPrice.sh"
    "step3_Lambda/deletion/step2_LambdaForNewSpotInstance/deleteStack_step2_LambdaForNewSpotInstance.sh"
    "step3_Lambda/deletion/step3_LambdaForCheckingSpotRequest/deleteStack_step3_LambdaForCheckingSpotRequest.sh"
    "step3_Lambda/deletion/step4_LambdaForUpdatingSpotInterruptionRatio/deleteStack_SpotInterruptionRatio.sh"
    "step3_Lambda/deletion/step5_SpotPlacementScore/deleteStack_SpotPlacementScore.sh"

    "step4_StepFunctions/deletion/step1_StepFunctionForNewSpotInstance.sh"
    "step4_StepFunctions/deletion/step2_StepFunctionForOpenStatus.sh"

    "step5_CloudWatch/deletion/step1_CloudWatchForLambdaForUpdatingSpotPrice.sh"
    "step5_CloudWatch/deletion/step2_CloudWatchForLambdaForNewSpotInstance.sh"
    "step5_CloudWatch/deletion/step3_CloudWatchForLambdaForStepFunctionForOpenStatus.sh"
    "step5_CloudWatch/deletion/step4_CloudWatchForSpotInterruptionRatio.sh"
    "step5_CloudWatch/deletion/step4_CloudWatchForSpotInterruptionRatio.sh"
)

# Save the current working directory
ORIGINAL_DIR="$PWD"

# For each script in the array, in reverse
for ((idx = ${#scripts[@]} - 1; idx >= 0; idx--)); do
  # Extract script path
  script="${scripts[idx]}"
  echo
  echo "===================================== Executing $script ====================================="
  # Change to the script's directory
  cd "$(dirname "$script")" || exit

  # Check the file type and execute accordingly
  if [[ $script == *.py ]]; then
    # If it's a Python script, use Python to execute it
    python3 "$(basename "$script")"
  elif [[ $script == *.sh ]]; then
    # If it's a Bash script, execute it directly
    bash "$(basename "$script")"
  else
    # Otherwise, print an error message
    echo "Unknown script type: $script"
    echo "Please add more file type checks as per your use-case."
    exit 1
  fi

  # Check if the script executed successfully
  if [ $? -eq 0 ]; then
    echo "===================================== $script executed successfully. ====================================="
  else
    echo "===================================== Execution failed for $script, exiting. ====================================="
    exit 1
  fi

  # Change back to the original directory
  cd "$ORIGINAL_DIR" || exit
done
