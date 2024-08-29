---

### **Setup on AWS:**

#### **1. AWS Configuration:**
   
**1.1** Security Group Setting:
   - Open the port `8080`,`22`  for incoming traffic.

**1.2** Import Key-Pair:
   - Ensure that you have the appropriate key-pair for secure access to your EC2 instance.

**1.3** Launch Instance:
   - Choose the `m5.xlarge` instance type.
   - Allocate `50GB` of memory.

---

### **Installation and Configuration on EC2:**

#### **2. Setting Up Galaxy:**

**2.1** Run the following script for Galaxy setup:

```bash

# Exporting AWS Credentials
export AWS_ACCESS_KEY_ID="<>>"
export AWS_SECRET_ACCESS_KEY="<>>" 

sudo yum update -y
sudo yum upgrade -y
sudo yum install git libxcrypt-compat python3-pip -y
pip install 'ruamel.yaml<=0.17.21,>=0.15.0'
pip install --upgrade awscli
pip3 install planemo 
pip3 install boto3

git clone -b release_22.05 https://github.com/galaxyproject/galaxy.git
cd galaxy
cp config/galaxy.yml.sample config/galaxy.yml

# Configure galaxy settings
sed -i '53c\    bind: "0.0.0.0:8080"' config/galaxy.yml
sed -i '1729c\  admin_users: <>>@gmail.com' config/galaxy.yml

# Start galaxy
sh run.sh
```

---

#### **3. Setting Up Data Analysis Workflow (In Another Terminal):**

**3.1** Use the following script:

```bash
echo "Installing Data Analysis Tools"
git clone https://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@github.com/mjaysonnn/ngs_analysis.git 

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

**4.2** Generate an API Key.

**4.3** Install Required Tools:
   
| Workflow | Author  | Revision |
|----------|---------|----------|
| FastQC   | devteam | 23       |
| MultiQC  | iuc     | 23       |
| Cutadapt | lparson | 34       |

**4.4** Setup API:

```bash
cd /home/ec2-user/ngs_analysis
NEW_API_KEY="6b645b8fb959716d77a4e09909a65b87"
sed -i "22s/--galaxy_user_key [a-z0-9]* /--galaxy_user_key $NEW_API_KEY /" run_all_batches.sh
cat run_all_batches.sh | grep --color -E $NEW_API_KEY
echo "API Key Updated"
```

**4.5** Stop Galaxy for Making New AMI:

---

#### **5. Create Amazon Machine Image (AMI)**:

- Navigate to the EC2 Dashboard on AWS Management Console.
- Select the instance you want to create an AMI of.
- From the "Actions" menu, select "Create Image".
- Fill in the image details and create the image.

---

Here’s the refactored section with the changes:

---

### **6. Using the New AMI Image:**
- Launch a new EC2 instance using the created AMI.
- In multi-region setups, you will need to copy the AMI to the other regions.
- Running `copy_ami_to_other_regions.py` would copy the AMI to the specified regions.
- Next, Refer to `scripts_for_running_galaxy.md` for starting up the Galaxy workload.

---
