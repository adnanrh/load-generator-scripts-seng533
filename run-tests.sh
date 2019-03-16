#!/bin/bash



# **************************************************************** 'initialize'
period=30 # used by get-logs.py
num_tests=$(cat test_list.json | jq "length")



# ********************************************************************** 'main'
for i in $(seq 1 $num_tests) ; do

    # read in test params from list of tests
    # autoscaling_value=$(cat test_list.json | jq ".[$i].autoscaling_value")
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

    # wait until the group is ready TODO
    ready="nope"
    while [ "$ready" = "nope" ]
    do
        group=$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names PicSiteASG)

        if [ $(echo "$group" | jq ".AutoScalingGroups[0].Instances | length") = 1 ]
        then
            ready="true"
        fi
    done



    start_time=$(date +%s) # ms since epoch utc
    # run jmeter
    /home/ubuntu/apache-jmeter-5.1/bin/jmeter -n \
        -t jmeter_tests/Project_Test_Plan.jmx \
        -JusersA="${num_users_a}" \
        -JusersB=="${num_users_b}" \
        -JusersC=="${num_users_c}" \
        -Jduration= -l \
        testresults.jtl
    end_time=$(date +%s) # ms since epoch utc



    # stop autoscale monitoring script since it needs new params for next test
    kill ${alarm_monitor_script_pid} # seems to be global

    # get our logs
    ./get-logs.py "${start_time}" "${end_time}" "${period}"
done


# do something with output



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
