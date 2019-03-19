#!/bin/bash

aws autoscaling update-auto-scaling-group \
    --region us-west-1 \
    --auto-scaling-group-name PicSiteASG \
    --min-size 0 \
    --max-size 0 \
    --desired-capacity 0
