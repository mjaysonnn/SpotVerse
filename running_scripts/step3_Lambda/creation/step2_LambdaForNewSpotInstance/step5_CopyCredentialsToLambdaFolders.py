"""
Single Region Copy AWS Credentials to Lambda Folders
Be careful with the credential file as it contains sensitive information.
"""
import configparser
import os

# Path to AWS configuration
aws_directory = os.path.join(os.path.expanduser('~'), '.aws')
credentials_file = os.path.join(aws_directory, 'credentials')
config_file = os.path.join(aws_directory, 'config')

# Using configparser to parse the ini files
config = configparser.ConfigParser()
config.read([credentials_file, config_file])

# Output directory path
output_path_list = ['lambda_codes/credentials.txt']

print("Starting credentials export...")

for output_path in output_path_list:

    print(f"Writing to {output_path}")
    # Check if credentials and config files are read properly
    if not config.read([credentials_file, config_file]):
        print("ERROR: Failed to read the credentials or config file.")
    else:
        print(f"Successfully read credentials and config from: {credentials_file} and {config_file}")

    # Writing to credentials.txt in the desired format
    try:
        with open(output_path, 'w') as output:
            if 'default' in config:
                print("Found 'default' section in the credentials/config file.")

                # AWS_ACCESS_KEY_ID
                if 'aws_access_key_id' in config['default']:
                    output.write(f'export AWS_ACCESS_KEY_ID="{config["default"]["aws_access_key_id"]}"\n')
                    print("Written AWS_ACCESS_KEY_ID to output.")
                else:
                    print("WARNING: AWS_ACCESS_KEY_ID not found in 'default' section.")

                # AWS_SECRET_ACCESS_KEY
                if 'aws_secret_access_key' in config['default']:
                    output.write(f'export AWS_SECRET_ACCESS_KEY="{config["default"]["aws_secret_access_key"]}"\n')
                    print("Written AWS_SECRET_ACCESS_KEY to output.")
                else:
                    print("WARNING: AWS_SECRET_ACCESS_KEY not found in 'default' section.")

                # AWS_SESSION_TOKEN
                if 'aws_session_token' in config['default']:
                    output.write(f'export AWS_SESSION_TOKEN="{config["default"]["aws_session_token"]}"\n')
                    print("Written AWS_SESSION_TOKEN to output.")
                else:
                    print("WARNING: AWS_SESSION_TOKEN not found in 'default' section.")
            else:
                print("ERROR: 'default' section not found in the credentials/config file.")
    except FileNotFoundError:
        print(f"ERROR: The output path {output_path} does not exist.")
    except IOError:
        print(f"ERROR: Unable to write to {output_path}.")
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {str(e)}")

print("Export completed.")
