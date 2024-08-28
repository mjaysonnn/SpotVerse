import configparser
import sys


# Subclass ConfigParser to preserve case sensitivity
class CaseSensitiveConfigParser(configparser.ConfigParser):
    def optionxform(self, optionstr):
        return optionstr


def update_config(config_path, arn_name, arn):
    print(f"Updating {config_path} with {arn}...")

    # Initialize a case-sensitive parser and read the existing configuration
    config = CaseSensitiveConfigParser()
    config.read(config_path)

    # Section and key to update
    section = 'step-function-arn'
    key = f"{arn_name}"

    # Update the configuration
    if not config.has_section(section):
        print(f"Section {section} not found. Adding section to {config_path}...")
        config.add_section(section)
    elif config.has_option(section, key):
        print(f"Updating key {key} in {config_path}...")
    else:
        print(f"Adding key {key} to {config_path}...")

    # Update the ARN
    config[section][key] = arn

    # Write the updated configuration back to the file
    with open(config_path, 'w') as configfile:
        print(f"Writing to {config_path}...")
        config.write(configfile)


if __name__ == "__main__":
    # Retrieve command line arguments
    config_path = sys.argv[1]
    arn_name = sys.argv[2]
    arn = sys.argv[3]

    # Update the configuration
    update_config(config_path, arn_name, arn)
