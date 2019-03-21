#!/bin/bash

alarm_monitor_script_pid=

# Capture "ctrl + c" interruptions and kill the alarm monitor script if it is running
exit_fn () {
    trap SIGINT             # Restore signal handling for SIGINT
    if ! [[ "alarm_monitor_script_pid" = "" ]]
    then
        kill ${alarm_monitor_script_pid}
    fi
    echo "Script interrupted while running tests ..."
    echo "Please run 'shutdown_load_balancing.sh' and 'shutdown_auto_scaling_group.sh' if you would like to stop testing."
    exit                    # Then exit script.
}

# **************************************************************** 'initialize'

period=30 # used by get_logs.py
num_tests=$(cat test_list.json | jq "length")

# spin up load balancing infrastructure if it does not already exist.
./init_load_balancing.sh

# grab new load balancer DNS name
load_balancer_dns_name=$(aws elbv2 describe-load-balancers --names PicSiteAppLB | jq ".LoadBalancers[0].DNSName")

if [[ "${load_balancer_dns_name}" = "" ]]
then
    echo "Load balancer DNS name not found, quitting."
    exit
fi

# ********************************************************************** 'main'
for i in $(seq 0 $(expr ${num_tests} - 1)) ; do

    # read in test params from list of tests
    asg_type=$(cat test_list.json | jq ".[$i].autoscaling_value")
    cpu_max=$(cat test_list.json | jq ".[$i].cpu_utilization_param")
    disk_max=$(cat test_list.json | jq ".[$i].disk_utilization_param")
    duration=$(cat test_list.json | jq ".[$i].test_duration")
    image_size=$(cat test_list.json | jq ".[$i].image_size")
    num_users_a=$(cat test_list.json | jq ".[$i].num_users_a")
    num_users_b=$(cat test_list.json | jq ".[$i].num_users_b")
    num_users_c=$(cat test_list.json | jq ".[$i].num_users_c")
	test_id=${i}

    # init auto-scaling group
    ./init_auto_scaling_group.sh

    # wait until the group is ready
    ready="nope"
    while [[ "$ready" = "nope" ]]
    do
        # Reset 'Target'
        aws cloudwatch put-metric-data --namespace "PicSiteASG" \
            --metric-name "Target" \
            --value "0.5" \
            --dimensions "AutoScalingGroupName=PicSiteASG"

        group=$(aws autoscaling describe-auto-scaling-groups \
                --auto-scaling-group-names PicSiteASG \
                --region us-west-1)
        group_len=$(echo "$group" | jq ".AutoScalingGroups[0].Instances | length")

        if [[ "${group_len}" = 1 ]]
        then
            instance_id=$(echo ${group} | jq -r .AutoScalingGroups[0].Instances[0].InstanceId)
            status=$(aws ec2 describe-instance-status \
                    --instance-id ${instance_id} \
                    --region us-west-1)
            actual_status=$(echo ${status} | jq -r .InstanceStatuses[0].InstanceStatus.Status)
            if [[ "${actual_status}" = "ok" ]]
            then
                ready="true"
            else
                echo "Waiting for instance status = ok. Currently instance status = ${actual_status}"
            fi
        else
            echo "Waiting for num_instances = 1. Currently num_Instances = ${group_len}"
        fi
    done

    # setup auto-scaling monitor script and track pid to kill it later
    trap 'exit_fn' SIGINT
    python3 asg_util_alarms.py "$cpu_max" "$disk_max" &
    alarm_monitor_script_pid=$!

    # run JMeter
    echo "Running JMeter test ..."
    start_time=$(date +%s) # ms since epoch utc
    /home/ubuntu/apache-jmeter-5.1/bin/jmeter -n \
        -t jmeter_tests/Project_Test_Plan.jmx \
        -JusersA="${num_users_a}" \
        -JusersB="${num_users_b}" \
        -JusersC="${num_users_c}" \
        -Jduration="${duration}" \
        -JLoadBalancerDNS=${load_balancer_dns_name} \
        -JImageSize=${image_size} \
		-JTestID=${test_id} \
        -l results/testresults.jtl
    end_time=$(date +%s) # ms since epoch utc
    echo "Finished running JMeter test."

    # stop auto-scaling monitoring script since it needs new params for next test
    trap SIGINT
    kill -s SIGINT ${alarm_monitor_script_pid} # seems to be global

    # get our logs
    python3 get_logs.py "$i" \
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

# shut down load balancing infrastructure
./shutdown_load_balancing.sh

# scale down & disable auto-scaling
./shutdown_auto_scaling_group.sh

# a reminder
echo "Please manually confirm that the auto-scaling group scaled down!"
