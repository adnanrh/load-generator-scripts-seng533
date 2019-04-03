#!/bin/bash

min_size=${1:-1}
max_size=${2:-5}
desired_capacity=${3:-1}
asg_name=${4:-PicSiteASG}

echo "Setting auto scaling group size (min-size=${min_size}, max-size=${max_size}, desired-capacity=${desired_capacity}) for ${asg_name}..."

aws autoscaling update-auto-scaling-group \
    --region us-west-1 \
    --auto-scaling-group-name ${asg_name} \
    --min-size ${min_size} \
    --max-size ${max_size} \
    --desired-capacity ${desired_capacity}

echo "Done setting auto scaling group size (min-size=${min_size}, max-size=${max_size}, desired-capacity=${desired_capacity}) for ${asg_name}."
