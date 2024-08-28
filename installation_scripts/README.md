# Installation Scripts (On AWS)

Make sure aws cli is installed and configured with the right permissions.

aws configure  # Make sure you have the right permissions

Example is us-west-2 and us-east-1

Generate the key pair for the instances through IAM in AWS console.

You need access for the following services:
- EC2
- S3
- Lambda
- DynamoDB
- CloudWatch
- EventBridge


```bash

Update preferred regions in conf.ini

preferred_regions = us-east-1, us-west-2
```
Run scripts. It will prompt you to hit yes or enter to continue.

./run_all_in_one.sh
```bash