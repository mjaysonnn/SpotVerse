#!/bin/bash

# List of scripts to be executed, grouped by step
declare -a step1_scripts=(
  "step1_S3Buckets/creation/step1_S3ForCompleteAndInterruption.py"
  "step1_S3Buckets/creation/step2_S3ForOpenStatus.py"
  "step1_S3Buckets/creation/step3_S3ForStoringLambda.sh"
)

declare -a step2_scripts=(
  "step2_IAMAndDynamoDB/creation/step1_DynamoForSpotPrice.sh"
  "step2_IAMAndDynamoDB/creation/step2_IAMForAdmin.sh"
  "step2_IAMAndDynamoDB/creation/step3_DynamoForSpotInterruptionRatio.sh"
  "step2_IAMAndDynamoDB/creation/step4_DynamoForSpotPlacementScore.sh"
  "step2_IAMAndDynamoDB/creation/step5_DynamoForCheckpoint.sh"
)

# step3_scripts will be run sequentially
declare -a step3_scripts=(
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
  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step1_CreateAndCopySecurityGroup.py"
  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step2_FindLinuxAMI.py"
  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step4_CopyConfIniFileToLambdaFolders.py"
  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step5_CopyCredentialsToLambdaFolders.py"
  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step6_SpotInterruptionRatio.sh"
  "step3_Lambda/creation/step4_LambdaForUpdatingSpotInterruptionRatio/step7_MakeLayerForSpotInterruptionRatio.sh"
  "step3_Lambda/creation/step5_SpotPlacementScore/step1_CreateAndCopySecurityGroup.py"
  "step3_Lambda/creation/step5_SpotPlacementScore/step2_FindLinuxAMI.py"
  "step3_Lambda/creation/step5_SpotPlacementScore/step4_CopyConfIniFileToLambdaFolders.py"
  "step3_Lambda/creation/step5_SpotPlacementScore/step5_CopyCredentialsToLambdaFolders.py"
  "step3_Lambda/creation/step5_SpotPlacementScore/step6_SpotPlacementScore.sh"
)

declare -a step4_scripts=(
  "step4_StepFunctions/creation/step1_StepFunctionForNewSpotInstance.sh"
  "step4_StepFunctions/creation/step2_StepFunctionForOpenStatus.sh"
)

declare -a step5_scripts=(
  "step5_CloudWatch/creation/step1_CloudWatchForLambdaForUpdatingSpotPrice.sh"
  "step5_CloudWatch/creation/step2_CloudWatchForLambdaForNewSpotInstance.sh"
  "step5_CloudWatch/creation/step3_CloudWatchForLambdaForStepFunctionForOpenStatus.sh"
  "step5_CloudWatch/creation/step4_CloudWatchForSpotInterruptionRatio.sh"
  "step5_CloudWatch/creation/step5_CloudWatchForSpotPlacementScore.sh"
)

# Function to execute scripts in parallel and wait for all of them to complete
run_scripts_in_parallel() {
    local scripts=("$@")
    local pids=()

    # Save the current working directory
    ORIGINAL_DIR="$PWD"

    # For each script in the array
    for script in "${scripts[@]}"; do
        (
            # Change to the script's directory
            cd "$(dirname "$script")" || exit

            echo "===================================== Executing $script ====================================="

            # Check the file type and execute accordingly
            if [[ $script == *.py ]]; then
                python3 "$(basename "$script")"
            elif [[ $script == *.sh ]]; then
                bash "$(basename "$script")"
            else
                echo "Unknown script type: $script"
                exit 1
            fi

            if [ $? -eq 0 ]; then
                echo "===================================== $script executed successfully. ====================================="
            else
                echo "===================================== Execution failed for $script. ====================================="
                exit 1
            fi
        ) &
        pids+=($!)  # Store the process ID of the background job
    done

    # Wait for all background jobs to complete
    for pid in "${pids[@]}"; do
        wait $pid || exit 1
    done

    # Change back to the original directory
    cd "$ORIGINAL_DIR" || exit
}

# Function to execute scripts sequentially
run_scripts_sequentially() {
    local scripts=("$@")

    # Save the current working directory
    ORIGINAL_DIR="$PWD"

    # For each script in the array
    for script in "${scripts[@]}"; do
        echo "===================================== Executing $script ====================================="
        # Change to the script's directory
        cd "$(dirname "$script")" || exit

        # Check the file type and execute accordingly
        if [[ $script == *.py ]]; then
            python3 "$(basename "$script")"
        elif [[ $script == *.sh ]]; then
            bash "$(basename "$script")"
        else
            echo "Unknown script type: $script"
            exit 1
        fi

        if [ $? -eq 0 ]; then
            echo "===================================== $script executed successfully. ====================================="
            echo
        else
            echo "===================================== Execution failed for $script, exiting. ====================================="
            exit 1
        fi

        # Change back to the original directory
        cd "$ORIGINAL_DIR" || exit
    done
}

# Run the scripts step by step
run_scripts_sequentially "${step1_scripts[@]}"
run_scripts_in_parallel "${step2_scripts[@]}"
run_scripts_sequentially "${step3_scripts[@]}"
run_scripts_in_parallel "${step4_scripts[@]}"
run_scripts_in_parallel "${step5_scripts[@]}"

echo "All steps completed successfully."
