

### 1. **Create the Reboot Script for Running Galaxy and Workflow**


**Step 1.1:** Create a script file:

Note: You can put this script in startup script and lambda code to execute the tasks required.

```shell
sudo vim /home/ec2-user/reboot.sh
```

**Step 1.2:** Replace Credentials and Add the following  content to the script:

```bash
#!/bin/bash

export AWS_ACCESS_KEY_ID="<>>"
export AWS_SECRET_ACCESS_KEY="<>"

# Initializing the log
echo "Starting script" >/var/log/user-data.log

# Appending all standard output and error messages to the log file
exec > >(tee -a /var/log/user-data.log) 2>&1

# Set the home directory
export HOME=/home/ec2-user

# Navigate to the galaxy directory and configure git
cd /home/ec2-user/galaxy || exit
git config --global --add safe.directory /home/ec2-user/galaxy

# Launch the Galaxy application
echo "Starting Galaxy"
sh run.sh >/var/log/run.log 2>&1 &

# Allow the system to pause for 300 seconds or 5 minutes
echo "Starting sleep for 300 seconds"
sleep 300

# Navigate to the NGS_DataAnalysis_Scripts directory and start the analysis
cd /home/ec2-user/ngs_analysis || exit
echo "Starting ngs_analysis"
./run_all_batches.sh

# Send the complete notification to Cloud watch
echo "Sending complete notification to S3"
python3 /home/ec2-user/ngs_analysis/send_complete_log_to_s3.py

# Terminate the instance
INSTANCE_ID=$(ec2-metadata -i | cut -d " " -f 2)
echo "Terminating instance $INSTANCE_ID"
aws ec2 terminate-instances --instance-ids $INSTANCE_ID
```

**Step 1.3:** Save and close the file.

**Step 1.4:** Grant execute permissions to the script:

```shell
sudo chmod +x /home/ec2-user/reboot.sh
```

**Step 1.5:** Open the service file for editing:

```shell
sudo vim /etc/systemd/system/myscript.service
```

**Step 1.6:** Insert the following content:

```shell
[Unit]
Description=My Script on Reboot

[Service]
Type=simple
ExecStart=/home/ec2-user/reboot.sh

[Install]
WantedBy=multi-user.target
```

**Step 1.7:** Save and close the file.

**Step 1.8:** Reload the systemd manager configuration:

```shell
sudo systemctl daemon-reload
```

**Step 1.9:** Enable the service to start on boot:

```shell
sudo systemctl enable myscript.service
sudo systemctl status myscript.service
```


