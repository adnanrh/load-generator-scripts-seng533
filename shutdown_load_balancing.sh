#!/bin/bash

# delete load balancer PicSiteAppLB
load_balancer_arn_json=$(aws elbv2 describe-load-balancers --names PicSiteAppLB 2> /dev/null)
if ! [[ "${load_balancer_arn_json}" = "" ]]
then
    load_balancer_arn=$(echo ${load_balancer_arn_json} | jq -r ".LoadBalancers[0].LoadBalancerArn")

    aws elbv2 delete-load-balancer --load-balancer-arn ${load_balancer_arn}

    if [[ "${?}" = "0" ]]
    then
        echo "Deleted load balancer with ARN \"${load_balancer_arn}\""
    fi
else
    echo "No load balancer found!"
fi

# delete target group PicSiteTargetGroup
target_group_arn_json=$(aws elbv2 describe-target-groups --names PicSiteTargetGroup 2> /dev/null)
if ! [[ "${target_group_arn_json}" = "" ]]
then
    target_group_arn=$(echo ${target_group_arn_json} | jq -r ".TargetGroups[0].TargetGroupArn")

    aws elbv2 delete-target-group --target-group-arn ${target_group_arn}

    if [[ "${?}" = "0" ]]
    then
        echo "Deleted target group with ARN \"${target_group_arn}\""
    fi
else
    echo "No target group found!"
fi

# detach target groups from auto scaling group PicSiteASG
asg_target_group_arns_json=$(aws autoscaling describe-load-balancer-target-groups --auto-scaling-group-name PicSiteASG 2> /dev/null)
if ! [[ "${asg_target_group_arns_json}" = "" ]]
then
    asg_target_group_arns=$(echo ${asg_target_group_arns_json} | jq -rc ".LoadBalancerTargetGroups[].LoadBalancerTargetGroupARN")

    aws autoscaling detach-load-balancer-target-groups --auto-scaling-group-name PicSiteASG \
        --target-group-arns ${asg_target_group_arns}

    if [[ "${?}" = "0" ]]
    then
        echo "Detached target groups with ARNs \"${asg_target_group_arns}\""
    fi
else
    echo "No target group found!"
fi