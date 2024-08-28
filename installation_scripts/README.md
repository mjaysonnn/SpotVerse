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

# Put multiple regions or single region in conf.ini

regions_to_use = us-east-1, us-west-2

#Recommend to use a default region as us-east-1 since S3 bucket's default region is us-east-1


```
Run scripts. It will prompt you to hit yes or enter to continue.

./run_all_in_one.sh
```bash