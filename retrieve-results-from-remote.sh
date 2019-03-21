#!/bin/bash

# Parse flags
while getopts i:l: option
do
case "${option}"
in
i) ssh_public_key=${OPTARG};;
l) local_dir=${OPTARG};;
esac
done

# Fill in defaults
if [[ "${ssh_public_key}" = "" ]]
then
    ssh_public_key=~/.ssh/seng533-project-key-pair.pem
fi

if [[ "${local_dir}" = "" ]]
then
    local_dir=.
fi

load_balancer_dns=$(aws ec2 describe-instances --filters Name=instance-id,Values=i-015d0fb8593d8f75b --query Reservations[0].Instances[0].PublicDnsName --output text)
remote_dir=/home/ubuntu/load-generator-scripts-seng533

rsync -av --progress -e "ssh -i ${ssh_public_key}" \
       ubuntu@${load_balancer_dns}:${remote_dir}/results/* \
       ${local_dir}/results