#!/bin/bash



# **************************************************************** 'initialize'
period=30 # used by get-logs.py
num_tests=$(cat test_list.json | jq "length")
load_balancer_dns_name="$1"


# ********************************************************************** 'main'
for i in $(seq 0 $(expr $num_tests - 1)) ; do

    # read in test params from list of tests
    asg_type=$(cat test_list.json | jq ".[$i].autoscaling_value")
    cpu_max=$(cat test_list.json | jq ".[$i].cpu_utilization_param")
    disk_max=$(cat test_list.json | jq ".[$i].disk_utilization_param")
    duration=$(cat test_list.json | jq ".[1].test_duration")
    image_size=$(cat test_list.json | jq ".[$i].image_size")
    num_users_a=$(cat test_list.json | jq ".[$i].num_users_a")
    num_users_b=$(cat test_list.json | jq ".[$i].num_users_b")
    num_users_c=$(cat test_list.json | jq ".[$i].num_users_c")

    # setup autoscale monitor script and track pid to kill it later
    ./asg_util_alarms.py "$cpu_max" "$disk_max" &
    alarm_monitor_script_pid=$!

    # init autoscaling group
    aws autoscaling update-auto-scaling-group \
        --region us-west-1 \
        --auto-scaling-group-name PicSiteASG \
        --min-size 1 \
        --max-size 5 \
        --desired-capacity 1

    # wait until the group is ready
    ready="nope"
    while [ "$ready" = "nope" ]
    do
        group=$(aws autoscaling describe-auto-scaling-groups \
                --auto-scaling-group-names PicSiteASG \
                --region us-west-1)
        group_len=$(echo "$group" | jq ".AutoScalingGroups[0].Instances | length")

        if [ "${group_len}" = 1 ]
        then
            instance_id=$(echo $group | jq -r .AutoScalingGroups[0].Instances[0].InstanceId)
            status=$(aws ec2 describe-instance-status \
                    --instance-id ${instance_id} \
                    --region us-west-1)
            actual_status=$(echo $status | jq -r .InstanceStatuses[0].InstanceStatus.Status)
            if [ "${actual_status}" = "ok" ]
            then
                ready="true"
            fi
        fi
    done



    start_time=$(date +%s) # ms since epoch utc
    # run jmeter
    /home/ubuntu/apache-jmeter-5.1/bin/jmeter -n \
        -t jmeter_tests/Project_Test_Plan.jmx \
        -JusersA="${num_users_a}" \
        -JusersB=="${num_users_b}" \
        -JusersC=="${num_users_c}" \
        -Jduration="${duration}" \
        -JLoadBalancerDNS=${load_balancer_dns_name} \
        -JImageSize=${image_size} \
        -l \
        testresults.jtl
    end_time=$(date +%s) # ms since epoch utc



    # stop autoscale monitoring script since it needs new params for next test
    kill ${alarm_monitor_script_pid} # seems to be global

    # get our logs
    ./get-logs.py "$i" \
            "${start_time}" \
            "${end_time}" \
            "${period}" \
            "${asg_type}" \
            "${cpu_max}" \
            "${disk_max}" \
            "${duration}" \
            "${image_size}" \
            "${num_users_a}" \
            "${num_users_b}" \
            "${num_users_c}"
done



# ******************************************************************** clean up
# scale down & disable autoscaling
aws autoscaling update-auto-scaling-group \
    --region us-west-1 \
    --auto-scaling-group-name PicSiteASG \
    --min-size 0 \
    --max-size 0 \
    --desired-capacity 0

# a reminder
echo "please manually confirm that the autoscale group scaled down!"
