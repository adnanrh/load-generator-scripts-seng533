#!/bin/bash

# Parse flags
while getopts i:r: option
do
case "${option}"
in
i) ssh_public_key=${OPTARG};;
r) local_results_dir=${OPTARG};;
esac
done

# Fill in defaults
if [[ "${ssh_public_key}" = "" ]]
then
    ssh_public_key=~/.ssh/seng533-project-key-pair.pem
fi

if [[ "${local_results_dir}" = "" ]]
then
    local_results_dir=./results_remote_lb
fi

# Determine if we are running on an EC2 instance
curl --connect-timeout 1 http://169.254.169.254/latest/meta-data/public-ipv4 &> /dev/null
if [[ "${?}" = "0" ]]
then
    echo "This script should not be run from an EC2 instance. Please run this from your local machine."
    exit 0
fi

# Get load generator DNS name
load_generator_dns=$(aws ec2 describe-instances \
    --filters Name=instance-id,Values=i-015d0fb8593d8f75b Name=instance-state-name,Values=running \
    --query Reservations[0].Instances[0].PublicDnsName \
    --output text)

if [[ "${load_generator_dns}" = "None" ]]
then
    echo "Could not fetch load generator DNS. Please check that it is running!"
    exit 1
fi

# Expected results directory path on load generator
remote_results_dir=/home/ubuntu/load-generator-scripts-seng533/results

# Retrieve remote results
rsync -av --progress -e "ssh -i ${ssh_public_key}" \
       ubuntu@${load_generator_dns}:${remote_results_dir}/* \
       ${local_results_dir}
