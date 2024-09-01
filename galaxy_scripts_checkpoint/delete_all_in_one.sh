#!/bin/bash

# List of scripts to be executed, grouped by step
declare -a step1_scripts=(
    "step1_S3Buckets/deletion/step1_S3ForCompleteAndInterruption.py"
    "step1_S3Buckets/deletion/step2_S3ForOpenStatus.py"
    "step1_S3Buckets/deletion/step3_S3ForStoringLambda.sh"
)

declare -a step2_scripts=(
    "step2_IAMAndDynamoDB/deletion/step1_DynamoForSpotPrice.sh"
    "step2_IAMAndDynamoDB/deletion/step2_IAMForAdmin.sh"
    "step2_IAMAndDynamoDB/deletion/step3_DynamoForSpotInterruptionRatio.sh"
    "step2_IAMAndDynamoDB/deletion/step4_DynamoForSpotPlacementScore.sh"
    "step2_IAMAndDynamoDB/deletion/step5_DynamoForCheckpoint.sh"

)

declare -a step3_scripts=(
    "step3_Lambda/deletion/step1_LambdaForUpdatingSpotPrice/step1_LambdaForUpdatingSpotPrice.sh"
    "step3_Lambda/deletion/step2_LambdaForNewSpotInstance/deleteStack_step2_LambdaForNewSpotInstance.sh"
    "step3_Lambda/deletion/step3_LambdaForCheckingSpotRequest/deleteStack_step3_LambdaForCheckingSpotRequest.sh"
    "step3_Lambda/deletion/step4_LambdaForUpdatingSpotInterruptionRatio/deleteStack_SpotInterruptionRatio.sh"
    "step3_Lambda/deletion/step5_SpotPlacementScore/deleteStack_SpotPlacementScore.sh"
)

declare -a step4_scripts=(
    "step4_StepFunctions/deletion/step1_StepFunctionForNewSpotInstance.sh"
    "step4_StepFunctions/deletion/step2_StepFunctionForOpenStatus.sh"
)

declare -a step5_scripts=(
    "step5_CloudWatch/deletion/step1_CloudWatchForLambdaForUpdatingSpotPrice.sh"
    "step5_CloudWatch/deletion/step2_CloudWatchForLambdaForNewSpotInstance.sh"
    "step5_CloudWatch/deletion/step3_CloudWatchForLambdaForStepFunctionForOpenStatus.sh"
    "step5_CloudWatch/deletion/step4_CloudWatchForSpotInterruptionRatio.sh"
    "step5_CloudWatch/deletion/step5_CloudWatchForSpotPlacementScore.sh"
)

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

# Run the scripts step by step in reverse order
run_scripts_in_parallel "${step5_scripts[@]}"
run_scripts_in_parallel "${step4_scripts[@]}"
run_scripts_in_parallel "${step3_scripts[@]}"
run_scripts_in_parallel "${step2_scripts[@]}"
run_scripts_sequentially "${step1_scripts[@]}"

echo "All steps completed successfully."
