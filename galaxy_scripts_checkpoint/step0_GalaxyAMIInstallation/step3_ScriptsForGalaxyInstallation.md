---

### **Setup on AWS:**

#### **1. AWS Configuration:**
   
**1.1** Security Group Setting:
   - Open the port `8080`,`22`  for incoming traffic. (Galaxy-SG)

**1.2** Import Key-Pair:
   - Ensure that you have the appropriate key-pair for secure access to your EC2 instance.

**1.3** Launch Instance:
   - Choose the `m5.xlarge` instance type. # You can choose any instance type that suits your needs.
   - Allocate `50GB` of memory. # You can allocate more memory if you need it.

---

### **Installation and Configuration on EC2:**

#### **2. Setting Up Galaxy:**

**2.1** Run the following script for Galaxy setup:

```bash

# Exporting AWS Credentials
# Use credentials.txt generated from step0_CopyAWSCredentials.py
export AWS_ACCESS_KEY_ID="AKIAYG7SHZZKQXDR5EWF"
export AWS_SECRET_ACCESS_KEY="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"

# Update and upgrade the system packages
sudo yum update -y
sudo yum upgrade -y

# Install necessary packages
sudo yum install git libxcrypt-compat python3-pip -y

# Install the specific version of ruamel.yaml required by awscli
pip install 'ruamel.yaml<=0.17.21,>=0.15.0'

# Upgrade awscli within the virtual environment
pip install --upgrade awscli

# Install boto3 within the virtual environment
pip install boto3

# Install planemo within the virtual environment
pip install planemo

#deactivate # Deactivate the virtual environment

git clone -b release_22.05 https://github.com/galaxyproject/galaxy.git
cd galaxy
cp config/galaxy.yml.sample config/galaxy.yml

# Configure galaxy settings
sed -i '53c\    bind: "0.0.0.0:8080"' config/galaxy.yml
sed -i '1729c\  admin_users: mjs8612@gmail.com' config/galaxy.yml

# Start galaxy
sh run.sh
```

#### **3. Setting Up Data Analysis Workflow (In Another Terminal):**

**3.1** Use the following script:

```bash

#source venv/bin/activate

echo "Installing Data Analysis Tools"
git clone https://github.com/mjaysonnn/ngs_analysis.git

echo "Downloading Data"
echo "Downloading SRA-Toolkit & SRR25195166"
wget https://ftp-trace.ncbi.nlm.nih.gov/sra/sdk/3.0.7/sratoolkit.3.0.7-centos_linux64.tar.gz
tar -xzf sratoolkit.3.0.7-centos_linux64.tar.gz
./sratoolkit.3.0.7-centos_linux64/bin/prefetch SRR25195166
./sratoolkit.3.0.7-centos_linux64/bin/fastq-dump --split-files SRR25195166

echo "Splitting files"
echo "Downloading seqkit"
wget https://github.com/shenwei356/seqkit/releases/download/v2.5.1/seqkit_linux_amd64.tar.gz
tar -xzf seqkit_linux_amd64.tar.gz

# Splitting the data into batches
./seqkit split SRR25195166_1.fastq -p 50
./seqkit split SRR25195166_2.fastq -p 50

# Organizing the batches
for i in {1..10}; do mkdir batch$i; done

# Move the files into batches
echo "Created 10 batches"

for i in {001..010}; do
    mv "SRR25195166_1.fastq.split/SRR25195166_1.part_$i.fastq" batch1/
done

for i in {011..020}; do
    mv "SRR25195166_1.fastq.split/SRR25195166_1.part_$i.fastq" batch2/
done

for i in {021..030}; do
    mv "SRR25195166_1.fastq.split/SRR25195166_1.part_$i.fastq" batch3/
done

for i in {031..040}; do
    mv "SRR25195166_1.fastq.split/SRR25195166_1.part_$i.fastq" batch4/
done

for i in {041..050}; do
    mv "SRR25195166_1.fastq.split/SRR25195166_1.part_$i.fastq" batch5/
done

for i in {001..010}; do
    mv "SRR25195166_2.fastq.split/SRR25195166_2.part_$i.fastq" batch6/
done

for i in {011..020}; do
    mv "SRR25195166_2.fastq.split/SRR25195166_2.part_$i.fastq" batch7/
done

for i in {021..030}; do
    mv "SRR25195166_2.fastq.split/SRR25195166_2.part_$i.fastq" batch8/
done

for i in {031..040}; do
    mv "SRR25195166_2.fastq.split/SRR25195166_2.part_$i.fastq" batch9/
done

for i in {041..050}; do
    mv "SRR25195166_2.fastq.split/SRR25195166_2.part_$i.fastq" batch10/
done
echo "Moved all files to batches"

mkdir -p ngs_analysis/data
mv batch* ngs_analysis/data

echo "All files moved to ngs_analysis/data"
```

---

#### **4. Galaxy Configuration:**

**4.1** Register and Log into Galaxy.

Wait for step 2 to complete before proceeding to this step.

Register using email used in the `config/galaxy.yml` file.

go to preferences and generate an API key.

Manage API Key:


**4.2** Generate an API Key.

Copy the API key and save it for later use.

**4.3** Install Required Tools:

You should see an admin menu
   
| Workflow | Author  | Revision |
|----------|---------|----------|
| FastQC   | devteam | 23       |
| MultiQC  | iuc     | 23       |
| Cutadapt | lparson | 34       |

Wait for workflow installation to complete.

**4.4** Setup API:

```bash
cd /home/ec2-user/ngs_analysis || { echo "Failed to change directory. Exiting."; exit 1; }
echo "Changed directory to /home/ec2-user/ngs_analysis"

NEW_API_KEY="c301fc88be62c4241cc1a26ed2d2f478"
echo "Setting new API key: ${NEW_API_KEY}"

if grep -q "^galaxy_user_key=" conf.ini; then
    sed -i "/^galaxy_user_key=/c\galaxy_user_key=${NEW_API_KEY}" conf.ini
    echo "Updated existing galaxy_user_key in conf.ini"
else
    echo "galaxy_user_key=${NEW_API_KEY}" >> conf.ini
    echo "Added new galaxy_user_key to conf.ini"
fi

echo "API Key Updated successfully"

# Set up the AWS CLI (needed for DynamoDB)
aws configure 

```
**4.5** Stop Galaxy for Making New AMI:

#### **5. Create Amazon Machine Image (AMI)**:

- Navigate to the EC2 Dashboard on AWS Management Console.
- Select the instance you want to create an AMI of.
- From the "Actions" menu, select "Create Image".
- Fill in the image details and create the image.
- Take a note for the AMI ID. We would need this to copy to other regions.
- Wait for the AMI creation to complete.

### **6. Next Steps**
- Running `copy_ami_to_other_regions.py` would copy the AMI to the specified regions.


