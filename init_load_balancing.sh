#!/bin/bash

# check if load balancer PicSiteAppLB already exists before creating anything else
load_balancer_arn_json=$(aws elbv2 describe-load-balancers --names PicSiteAppLB 2> /dev/null)
if ! [[ "${load_balancer_arn_json}" = "" ]]
then
    echo "Load balancer already exists with ARN: $(echo ${load_balancer_arn_json} | jq -r '.LoadBalancers[0].LoadBalancerArn')"
    echo "Will not create a new load balancer until it is deleted."
    exit
fi

# create load balancer PicSiteAppLB
load_balancer_arn=$(aws elbv2 create-load-balancer \
    --name "PicSiteAppLB" \
    --type application \
    --subnets "subnet-5ecdb207" "subnet-48f0ce2d" \
    | jq -r ".LoadBalancers[0].LoadBalancerArn")

if [[ "${?}" = "0" ]]
then
    echo "Created load balancer with ARN \"${load_balancer_arn}\""
else
    echo "Error encountered while creating load balancer"
    exit $?
fi

# create target group PicSiteTargetGroup for PicSiteAppLB
target_group_arn=$(aws elbv2 create-target-group \
    --name "PicSiteTargetGroup" \
    --protocol HTTP \
    --port 80 \
    --vpc-id vpc-52612337 \
    --target-type instance \
    | jq -r ".TargetGroups[0].TargetGroupArn")

if [[ "${?}" = "0" ]]
then
    echo "Created target group with ARN \"${target_group_arn}\""
else
    echo "Error encountered while creating target group. Recommend running teardown script"
    exit $?
fi

# create listener for PicSiteAppLB to forward traffic to PicSiteTargetGroup
aws elbv2 create-listener \
    --load-balancer-arn ${load_balancer_arn} \
    --protocol HTTP --port 80 \
    --default-actions Type=forward,TargetGroupArn=${target_group_arn} \
    > /dev/null

if [[ "${?}" = "0" ]]
then
    echo "Created listener for load balancer PicSiteAppLB pointing to PicSiteTargetGroup"
else
    echo "Error encountered while creating listener for load balancer. Recommend running teardown script"
    exit $?
fi

# attach PicSiteTargetGroup to PicSiteASG
aws autoscaling attach-load-balancer-target-groups \
    --auto-scaling-group-name PicSiteASG \
    --target-group-arns "${target_group_arn}"

if [[ "${?}" = "0" ]]
then
    echo "Attached target group PicSiteTargetGroup to the PicSiteASG auto scaling group"
else
    echo "Error encountered while attaching target group to PicSiteASG. Recommend running teardown script"
    exit $?
fi

