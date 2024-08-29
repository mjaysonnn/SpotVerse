import os
import configparser

# Path to AWS configuration
aws_directory = os.path.join(os.path.expanduser('~'), '.aws')
credentials_file = os.path.join(aws_directory, 'credentials')
config_file = os.path.join(aws_directory, 'config')

# Using configparser to parse the ini files
config = configparser.ConfigParser()
config.read([credentials_file, config_file])

# Writing to credentials.txt in the desired format
with open('credentials.txt', 'w') as output:
    if 'default' in config:
        if 'aws_access_key_id' in config['default']:
            output.write(f'export AWS_ACCESS_KEY_ID="{config["default"]["aws_access_key_id"]}"\n')
        if 'aws_secret_access_key' in config['default']:
            output.write(f'export AWS_SECRET_ACCESS_KEY="{config["default"]["aws_secret_access_key"]}"\n')
        # if 'aws_session_token' in config['default']:
        #     output.write(f'export AWS_SESSION_TOKEN="{config["default"]["aws_session_token"]}"\n')
