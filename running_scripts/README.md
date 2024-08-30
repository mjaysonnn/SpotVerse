## Installation Guide (On AWS)

### Prerequisites

1. **AWS CLI Installation and Configuration**:
   - Ensure that the AWS CLI is installed and configured with the appropriate permissions.
   - Run the following command to configure your AWS CLI:
     ```bash
     aws configure
     ```
   - Ensure that the provided credentials have the necessary permissions.

2. **Required AWS Services**:
   - You will need access to the following AWS services:
     - EC2
     - S3
     - Lambda
     - DynamoDB
     - CloudWatch
     - EventBridge

3. **Key Pair Location**:
   - You must specify the key pair name in the `conf.ini` file.
   - Typically, the key pair is located at `~/.ssh/your-key-pair.pem`.

### Configuration

1. **Setting Up Regions**:
   - Define the regions to use in the `conf.ini` file. You can specify multiple regions or a single region.
   - Example configuration for `conf.ini`:
     ```ini
     regions_to_use = us-east-1, us-west-2
     ```
   - **Recommendations**:
     - Use `us-east-1` as the default region, especially for S3 buckets, DynamoDB, CloudWatch, and EventBridge, as these services are often initialized in `us-east-1`.
     - When specifying multiple regions, resources will be created in all the listed regions.

2. **Key Pair Configuration**:
   - Specify the key pair name in the `conf.ini` file.
   - Example configuration for `conf.ini`:
     ```ini
     key_pair_name = your-key-pair
     ```

3. **Instance Type and Number of Instances**:
   - Define the instance type and the number of instances to launch in the `conf.ini` file.
   - Example configuration for `conf.ini`:
     ```ini
     instance_type = m5.2xlarge
     number_of_instances = 3
     ```
   - These settings allow you to specify the EC2 instance type and the number of instances to run in each region.
   - **Note**: The example configuration includes a sleep time to simulate the instance startup. You can replace the sleep command with your actual startup script (in the EC2 script and Lambda code) to execute the necessary tasks.

### Execution

1. **Running the Scripts**:
   - To deploy the resources, execute the following script:
     ```bash
     ./run_all_in_one.sh
     ```
   - The script will prompt you for confirmation before proceeding. Press `yes` or `enter` to continue.
   - **Note**: If you are running Galaxy, you can skip the `step2_FindLinuxAMI.py` script, as you will be using the pre-configured Galaxy AMI.

2. **Launching Spot Instances**:
   - After deploying the initial resources, navigate to the directory containing the Spot Instance scripts:
     - Execute the following Python scripts sequentially to configure and launch your Spot Instances:
       ```bash
       cd step6_SpotInstance
       python3 step1_CreateAndCopySecurityGroup.py         
       python3 step2_FindLinuxAMI.py
       python3 step3_StartSpotInstances.py
       ```
   - During the execution of these steps, you may be prompted for additional inputs or confirmations. Follow the prompts as instructed, and the scripts will handle the rest.

### Cleanup

1. **Deleting All Resources**:
   - To delete all the resources created by the scripts, run the following command:
     ```bash
     ./delete_all_resources.sh
     ```
