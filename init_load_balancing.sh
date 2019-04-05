#!/bin/bash

asg_suffix=${1}

asg_name="PicSiteASG${asg_suffix}"
lb_name="PicSiteAppLB${asg_suffix}"
tg_name="PicSiteTargetGroup${asg_suffix}"

# check if load balancer PicSiteAppLBx already exists before creating anything else
load_balancer_arn_json=$(aws elbv2 describe-load-balancers --names ${lb_name} 2> /dev/null)
if ! [[ "${load_balancer_arn_json}" = "" ]]
then
    echo "Load balancer already exists with ARN: $(echo ${load_balancer_arn_json} | jq -r '.LoadBalancers[0].LoadBalancerArn')"
    echo "Will not create a new load balancer until it is deleted."
    exit
fi

# create load balancer PicSiteAppLBx
load_balancer_arn=$(aws elbv2 create-load-balancer \
    --name "${lb_name}" \
    --type application \
    --security-groups "sg-070a315fadd1bc749" \
    --subnets "subnet-5ecdb207" "subnet-48f0ce2d" \
    | jq -r ".LoadBalancers[0].LoadBalancerArn")

if [[ "${?}" = "0" ]]
then
    echo "Created load balancer ${lb_name} with ARN \"${load_balancer_arn}\""
else
    echo "Error encountered while creating load balancer ${lb_name}"
    exit $?
fi

# create target group PicSiteTargetGroupX for PicSiteAppLBx
target_group_arn=$(aws elbv2 create-target-group \
    --name "${tg_name}" \
    --protocol HTTP \
    --port 80 \
    --vpc-id vpc-52612337 \
    --target-type instance \
    | jq -r ".TargetGroups[0].TargetGroupArn")

if [[ "${?}" = "0" ]]
then
    echo "Created target group ${tg_name} with ARN \"${target_group_arn}\""
else
    echo "Error encountered while creating target group ${tg_name}. Recommend running teardown script"
    exit $?
fi

# set PicSiteTargetGroupX's de-registration delay to 30 seconds (connection drain time)
aws elbv2 modify-target-group-attributes \
    --target-group-arn ${target_group_arn} \
    --attributes Key=deregistration_delay.timeout_seconds,Value=30 \
    > /dev/null

if [[ "${?}" = "0" ]]
then
    echo "Set target group ${tg_name} de-registration delay to 30 seconds"
else
    echo "Error encountered while setting ${tg_name}'s de-registration delay. Recommend running teardown script"
    exit $?
fi

# create listener for PicSiteAppLBx to forward traffic to PicSiteTargetGroupX
aws elbv2 create-listener \
    --load-balancer-arn ${load_balancer_arn} \
    --protocol HTTP --port 80 \
    --default-actions Type=forward,TargetGroupArn=${target_group_arn} \
    > /dev/null

if [[ "${?}" = "0" ]]
then
    echo "Created listener for load balancer ${lb_name} pointing to ${tg_name}"
else
    echo "Error encountered while creating listener for load balancer. Recommend running teardown script"
    exit $?
fi

# attach PicSiteTargetGroupX to the auto scaling group
aws autoscaling attach-load-balancer-target-groups \
    --auto-scaling-group-name ${asg_name} \
    --target-group-arns "${target_group_arn}"

if [[ "${?}" = "0" ]]
then
    echo "Attached target group ${tg_name} to the ${asg_name} auto scaling group"
else
    echo "Error encountered while attaching target group ${tg_name} to ${asg_name}. Recommend running teardown script"
    exit $?
fi

