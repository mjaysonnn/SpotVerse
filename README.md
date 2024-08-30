# SpotVerse

**SpotVerse** is a framework designed for deploying and managing workloads in multi-region on AWS Spot Instances, including both Galaxy and non-Galaxy workloads. The framework is highly flexible and can be adapted to deploy a wide variety of other workloads as well.

## Directory Structure
  
- **galaxy_scripts**: Contains the scripts specifically for deploying the Galaxy framework. It contains installation on Galaxy Framework and copying generated AMI to other regions. 


## Installation Guide (On AWS)

### Prerequisites

1. **AWS CLI Installation and Configuration**:
   - Ensure that the AWS CLI is installed and configured with the appropriate permissions.
   - Run the following command to configure your AWS CLI:
     ```bash
     aws configure
     pip install -r requirements.txt
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

### 1. **Setting Preferred Regions**:
   - Define the regions to use in the `conf.ini` file. You can specify multiple regions, a single region, or set it to `None`.
   - Example configuration for `conf.ini`:
     ```ini
     regions_to_use = us-east-1, us-west-2
     ```
   - **Recommendations**:
     - Recommend to include `us-east-1` as in preferred regions, since `us-east-1` is default regions for S3.
     - When specifying multiple regions, resources will be created in all the listed regions.
   - **Handling `None` or Missing Regions**:
     - If `regions_to_use` is set to `None` or not defined in `conf.ini`, the script will automatically select regions from the list of `available_regions`.

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

3. **Parsing the Output**:

- The following scripts will retrieve data from your S3 bucket, including both completed and interrupted instances. Using the AWS API, the scripts will then parse the fetched data, extracting details on instance types, start and end times, associated costs, and any interruptions that occurred. Finally, the scripts will calculate the total cost and total run time of these instances, providing a detailed analysis with Matplotlib.

```bash
cd step7_ParseAndAnalysis || exit

# Execute the Python scripts in the specified order
python3 step_0_download_bucket_and_object.py
python3 step_1_parse_data_and_save_all_info.py
python3 step_2_load_pickle_and_save_spot_price_history.py
python3 step_3_load_timestamp_and_get_total_cost.py
python3 step_4_instance_completion_analysis.py
python3 step_5_instance_interruption_analysis.py
```


### Cleanup

1. **Deleting All Resources**:
   - To delete all the resources created by the scripts, run the following command:
     ```bash
     ./delete_all_resources.sh
     ```

