import shutil

# Define the source and destination file paths
source_file = '../../../step0_GalaxyAMIInstallation/credentials.txt'
output_file = 'lambda_codes/credentials.txt'

# Copy the file from the source to the destination
shutil.copy(source_file, output_file)
print("AMI Ids File copied successfully from step0_GalaxyAMIInstallation to lambda_codes.")

print("Script execution completed.")
