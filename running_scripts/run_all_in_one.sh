#!/bin/bash

#CONDA_BASE=$(conda info --base)
#source "$CONDA_BASE/etc/profile.d/conda.sh"

# List of scripts to be executed in order
declare -a scripts=(
  "step1_S3Buckets/creation/step1_S3ForCompleteAndInterruption.py"
  "step1_S3Buckets/creation/step2_S3ForOpenStatus.py"
  "step1_S3Buckets/creation/step3_S3ForStoringLambda.sh"
  "step2_IAMAndDynamoDB/creation/step1_DynamoForSpotPrice.sh"
  "step2_IAMAndDynamoDB/creation/step2_IAMForAdmin.sh"
  "step2_IAMAndDynamoDB/creation/step3_DynamoForSpotInterruptionRatio.sh"
  "step2_IAMAndDynamoDB/creation/step4_DynamoForSpotPlacementScore.sh"

  "step3_Lambda/creation/step1_LambdaForUpdatingSpotPrice/step1_CopyConfIniFileToLambdaFolders.py"
  "step3_Lambda/creation/step1_LambdaForUpdatingSpotPrice/step2_createStack_LambdaForUpdatingSpotPrice.sh"

  "step3_Lambda/creation/step2_LambdaForNewSpotInstance/step1_CreateAndCopySecurityGroup.py"
  "step3_Lambda/creation/step2_LambdaForNewSpotInstance/step2_FindLinuxAMI.py"
  "step3_Lambda/creation/step2_LambdaForNewSpotInstance/step3_ImportKeyPair.py"
  "step3_Lambda/creation/step2_LambdaForNewSpotInstance/step4_CopyConfIniFileToLambdaFolders.py"
  "step3_Lambda/creation/step2_LambdaForNewSpotInstance/step5_CopyCredentialsToLambdaFolders.py"
  "step3_Lambda/creation/step2_LambdaForNewSpotInstance/step6_LambdaForNewSpotInstance.sh"

  "step3_Lambda/creation/step3_LambdaForCheckingSpotRequest/step1_CreateAndCopySecurityGroup.py"
  "step3_Lambda/creation/step3_LambdaForCheckingSpotRequest/step2_FindLinuxAMI.py"
  "step3_Lambda/creation/step3_LambdaForCheckingSpotRequest/step3_CopyConfIniFileToLambdaFolders.py"
  "step3_Lambda/creation/step3_LambdaForCheckingSpotRequest/step4_CopyCredentialsToLambdaFolders.py"
  "step3_Lambda/creation/step3_LambdaForCheckingSpotRequest/step5_LambdaForCheckingSpotRequest.sh"

  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step1_CreateAndCopySecurityGroup.py"        # Single
  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step2_FindLinuxAMI.py"                      # Single
  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step4_CopyConfIniFileToLambdaFolders.py"    # Single
  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step5_CopyCredentialsToLambdaFolders.py"    # Single
  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step6_SpotInterruptionRatio.sh"             # Single
  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step7_MakeLayerForSpotInterruptionRatio.sh" # Single

  "step3_Lambda/creation/step5_SpotPlacementScore/step1_CreateAndCopySecurityGroup.py"     # Single
  "step3_Lambda/creation/step5_SpotPlacementScore/step2_FindLinuxAMI.py"                   # Single
  "step3_Lambda/creation/step5_SpotPlacementScore/step4_CopyConfIniFileToLambdaFolders.py" # Single
  "step3_Lambda/creation/step5_SpotPlacementScore/step5_CopyCredentialsToLambdaFolders.py" # Single
  "step3_Lambda/creation/step5_SpotPlacementScore/step6_SpotPlacementScore.sh"             # Single

  "step4_StepFunctions/creation/step1_StepFunctionForNewSpotInstance.sh"
  "step4_StepFunctions/creation/step2_StepFunctionForOpenStatus.sh"

  "step5_CloudWatch/creation/step1_CloudWatchForLambdaForUpdatingSpotPrice.sh"
  "step5_CloudWatch/creation/step2_CloudWatchForLambdaForNewSpotInstance.sh"
  "step5_CloudWatch/creation/step3_CloudWatchForLambdaForStepFunctionForOpenStatus.sh"
  "step5_CloudWatch/creation/step4_CloudWatchForSpotInterruptionRatio.sh"
  "step5_CloudWatch/creation/step5_CloudWatchForSpotPlacementScore.sh"

)

# Save the current working directory
ORIGINAL_DIR="$PWD"

# For each script in the array
for script in "${scripts[@]}"; do
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
    echo
  else
    echo "===================================== Execution failed for $script, exiting. ====================================="
    exit 1
  fi

  # Change back to the original directory
  cd "$ORIGINAL_DIR"
done
