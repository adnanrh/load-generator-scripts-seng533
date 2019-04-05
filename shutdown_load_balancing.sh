#!/bin/bash

asg_suffix=${1}

asg_name="PicSiteASG${asg_suffix}"
lb_name="PicSiteAppLB${asg_suffix}"
tg_name="PicSiteTargetGroup${asg_suffix}"

# detach target groups from auto scaling group asg_name
asg_target_group_arns_json=$(aws autoscaling describe-load-balancer-target-groups --auto-scaling-group-name ${asg_name} | jq .LoadBalancerTargetGroups)
if ! [[ "${asg_target_group_arns_json}" = "[]" ]]
then
    asg_target_group_arns=$(echo ${asg_target_group_arns_json} | jq -rc ".[].LoadBalancerTargetGroupARN")

    aws autoscaling detach-load-balancer-target-groups --auto-scaling-group-name ${asg_name} \
        --target-group-arns ${asg_target_group_arns}

    if [[ "${?}" = "0" ]]
    then
        echo "Detached target groups from auto scaling group ${asg_name} with ARNs \"${asg_target_group_arns}\""
    fi
else
    echo "No target groups attached to auto scaling group ${asg_name}!"
fi

# delete load balancer PicSiteAppLBx
load_balancer_arn_json=$(aws elbv2 describe-load-balancers --names ${lb_name} 2> /dev/null)
if ! [[ "${load_balancer_arn_json}" = "" ]]
then
    load_balancer_arn=$(echo ${load_balancer_arn_json} | jq -r ".LoadBalancers[0].LoadBalancerArn")

    aws elbv2 delete-load-balancer --load-balancer-arn ${load_balancer_arn}

    if [[ "${?}" = "0" ]]
    then
        echo "Deleted load balancer ${lb_name} with ARN \"${load_balancer_arn}\""
    fi
else
    echo "No load balancer ${lb_name} found!"
fi

# delete target group PicSiteTargetGroupX
target_group_arn=$(aws elbv2 describe-target-groups --names  ${tg_name} \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text \
    2> /dev/null)
if ! [[ "${target_group_arn}" = "None" ]] && ! [[ "${target_group_arn}" = "" ]]
then
    # first, deregister targets (instances) from the target group
    target_ids=$(aws elbv2 describe-target-health \
        --target-group-arn ${target_group_arn} \
        --query 'TargetHealthDescriptions[*].Target.Id' \
        --output text)
    if ! [[ "${target_ids}" = "" ]]
    then
        target_ids_formatted=
        for id in ${target_ids}
        do
            target_ids_formatted="${target_ids_formatted}Id=${id} "
        done
        aws elbv2 deregister-targets --target-group-arn ${target_group_arn} --targets ${target_ids_formatted}
    fi

    # finally, delete the target group
    aws elbv2 delete-target-group --target-group-arn ${target_group_arn}

    if [[ "${?}" = "0" ]]
    then
        echo "Deleted target group ${tg_name} with ARN \"${target_group_arn}\""
    fi
else
    echo "No target group ${tg_name} found!"
fi
