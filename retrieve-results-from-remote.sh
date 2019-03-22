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

load_balancer_dns=$(aws ec2 describe-instances --filters Name=instance-id,Values=i-015d0fb8593d8f75b --query Reservations[0].Instances[0].PublicDnsName --output text)
remote_results_dir=/home/ubuntu/load-generator-scripts-seng533/results

rsync -av --progress -e "ssh -i ${ssh_public_key}" \
       ubuntu@${load_balancer_dns}:${remote_results_dir}/* \
       ${local_results_dir}