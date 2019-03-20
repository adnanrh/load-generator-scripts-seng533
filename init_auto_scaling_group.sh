#!/bin/bash

aws autoscaling update-auto-scaling-group \
    --region us-west-1 \
    --auto-scaling-group-name PicSiteASG \
    --min-size 1 \
    --max-size 5 \
    --desired-capacity 1