AWSTemplateFormatVersion: '2010-09-09'
Description: |
  This CloudFormation template creates a Lambda function that is sourced
  from an S3 object. The function is set up with a specific handler and role, 
  and runs with a Python 3.11 runtime with a 60-second timeout.

Parameters:
  LambdaCodeBucket:
    Description: Name of the S3 bucket containing the Lambda function code.
    Type: String
    Default: mj-aws-lambda-code-us-east-1  # Default bucket name

  LambdaCodeS3Key:
    Description: S3 key for the Lambda function code.
    Type: String
    Default: lambda_check_open_spot_request.zip  # Default S3 key

Resources:
  MyLambdaFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: lambda_check_open_spot_request
      Handler: lambda_check_open_spot_request.lambda_handler
      Role: !Sub 'arn:aws:iam::${AWS::AccountId}:role/LambdaWithAdminAccess'
      Code:
        S3Bucket: !Ref LambdaCodeBucket
        S3Key: !Ref LambdaCodeS3Key
      Runtime: python3.11
      Timeout: 900