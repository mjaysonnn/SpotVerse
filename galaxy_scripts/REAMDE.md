To run Galaxy workload, we need to have AMI that is pre-configured with Galaxy. 

ami_creation.md contains the steps to create an AMI with Galaxy installed.
copy_ami.md contains the steps to copy the AMI to other regions.

Then we can 
1. run Galaxy workload by using reboot script which is in scripts_for_running_galaxy.md.
2. Or use the ami_ids.txt file to use in running_scripts directory to run the Galaxy workflow where we can use user-data to run the Galaxy workflow.




```bash