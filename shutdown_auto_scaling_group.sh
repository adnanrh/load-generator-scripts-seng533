#!/bin/bash

min_size=0
max_size=0
desired_capacity=0

echo "Shutting down auto scaling group size (min-size=${min_size}, max-size=${max_size}, desired-capacity=${desired_capacity})..."

aws autoscaling update-auto-scaling-group \
    --region us-west-1 \
    --auto-scaling-group-name PicSiteASG \
    --min-size ${min_size} \
    --max-size ${max_size} \
    --desired-capacity ${desired_capacity}

echo "Done shutting down auto scaling group size (min-size=${min_size}, max-size=${max_size}, desired-capacity=${desired_capacity})."

