#!/bin/bash

# Input vars
config_file=${1:-test_list.json}
asg_name=${2:-PicSiteASG}

# Capture "ctrl + c" interruptions and kill the alarm monitor script if it is running
alarm_monitor_script_pid=

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

# Wait until auto scaling group has desired number of instances. While waiting, will set target value to '0.5'.
wait_for_desired_instances() {
    desired_instances=$1

    ready="nope"
    while [[ "${ready}" = "nope" ]]
    do
        # Reset 'Target'
        aws cloudwatch put-metric-data --namespace "${asg_name}" \
            --metric-name "Target" \
            --value "0.5" \
            --dimensions "AutoScalingGroupName=${asg_name}"

        group=$(aws autoscaling describe-auto-scaling-groups \
                --auto-scaling-group-names ${asg_name} \
                --region us-west-1)
        group_len=$(echo "$group" | jq ".AutoScalingGroups[0].Instances | length")

        if [[ "${group_len}" = "${desired_instances}" ]]
        then
            ready="true"
            if [[ "${group_len}" != "0" ]]
            then
                instance_id_list=$(echo ${group} | jq -r .AutoScalingGroups[0].Instances[].InstanceId)
                for instance_id in ${instance_id_list}
                do
                    status=$(aws ec2 describe-instance-status \
                            --instance-id ${instance_id} \
                            --region us-west-1)
                    actual_status=$(echo ${status} | jq -r .InstanceStatuses[0].InstanceStatus.Status)
                    if [[ "${actual_status}" != "ok" ]]
                    then
                        ready="nope"
                        echo "Waiting for status = ok for \"${instance_id}\". Currently status = ${actual_status}"
                        sleep 15
                    fi
                done
            fi
        else
            echo "Waiting for num_instances = ${desired_instances}. Currently num_instances = ${group_len}"
            sleep 15
        fi
    done
}

# **************************************************************** 'initialize'

default_min_instances=1
default_max_instances=5
period=30 # used by get_logs.py
num_tests=$(cat ${config_file} | jq "length")

# spin up load balancing infrastructure if it does not already exist.
./init_load_balancing.sh ${asg_name}

# grab new load balancer DNS name
load_balancer_dns_name="$(aws elbv2 describe-load-balancers --names PicSiteAppLB | jq -r '.LoadBalancers[0].DNSName')"

if [[ "${load_balancer_dns_name}" = "" ]]
then
    echo "Load balancer DNS name not found, quitting."
    exit
fi

# setup results directory based on current run session
results_dir=results/$(date +%Y_%m_%d_%H%M%S)
mkdir -p ${results_dir}

# ********************************************************************** 'main'
for i in $(seq 0 $(expr ${num_tests} - 1)) ; do

    # read in test params from list of tests
    asg_type=$(cat ${config_file} | jq ".[$i].autoscaling_value")
    cpu_max=$(cat ${config_file} | jq ".[$i].cpu_utilization_param")
    disk_max=$(cat ${config_file} | jq ".[$i].disk_utilization_param")
    duration=$(cat ${config_file} | jq ".[$i].test_duration")
    image_size=$(cat ${config_file} | jq ".[$i].image_size")
    num_users_a=$(cat ${config_file} | jq ".[$i].num_users_a")
    num_users_b=$(cat ${config_file} | jq ".[$i].num_users_b")
    num_users_c=$(cat ${config_file} | jq ".[$i].num_users_c")
    test_id=${i}

    # init auto-scaling group
    if [[ "${asg_type}" = "0" ]]
    then
        # no auto-scaling, get num instances and set
        num_instances=$(cat ${config_file} | jq -r ".[$i].num_instances")
        if [[ "${num_instances}" = "null" ]]
        then
            echo "Must provide 'num_instances' field if 'asg_type' is set to 0. Skipping test ${i}"
            continue
        fi
        ./init_auto_scaling_group.sh ${num_instances} ${num_instances} ${num_instances}
    else
        # auto-scaling
        num_instances=1
        ./init_auto_scaling_group.sh ${default_min_instances} ${default_max_instances} ${num_instances}
    fi

    # wait until the group is ready
    echo "Waiting for desired starting instances (${num_instances}) for test ..."
    wait_for_desired_instances ${num_instances}

    # setup auto-scaling monitor script and track pid to kill it later
    trap 'exit_fn' SIGINT
    python3 asg_util_alarms.py "${asg_name}" "${cpu_max}" "${disk_max}" &
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
        -JLoadBalancerDNS="${load_balancer_dns_name}" \
        -JImageSize="${image_size}" \
        -JTestID="${test_id}" \
        -JResultsDir="${results_dir}" \
        -l ${results_dir}/testresults_${test_id}.jtl
    end_time=$(date +%s) # ms since epoch utc
    echo "Finished running JMeter test."

    # stop auto-scaling monitoring script since it needs new params for next test
    trap SIGINT
    kill -s SIGINT ${alarm_monitor_script_pid} # seems to be global

    # get our logs
    python3 get_logs.py "${results_dir}" "${asg_name}" \
        "${test_id}"  \
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

    # clean-up remaining instances
    echo "Cleaning up instances after test ..."
    ./shutdown_auto_scaling_group.sh ${asg_name}
    wait_for_desired_instances 0
done

# ******************************************************************** clean up

# scale down & disable auto-scaling
./shutdown_auto_scaling_group.sh ${asg_name}

# shut down load balancing infrastructure
./shutdown_load_balancing.sh ${asg_name}

# a reminder
echo "Please manually confirm that the auto-scaling group scaled down!"
