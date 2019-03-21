#!/bin/bash

min_size=1
max_size=5
desired_capacity=1

echo "Initializing auto scaling group size (min-size=${min_size}, max-size=${max_size}, desired-capacity=${desired_capacity})..."

aws autoscaling update-auto-scaling-group \
    --region us-west-1 \
    --auto-scaling-group-name PicSiteASG \
    --min-size ${min_size} \
    --max-size ${max_size} \
    --desired-capacity ${desired_capacity}

echo "Done initializing auto scaling group size (min-size=${min_size}, max-size=${max_size}, desired-capacity=${desired_capacity})."
