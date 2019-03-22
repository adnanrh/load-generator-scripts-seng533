#!/usr/bin/python3
import calendar
import logging
import signal
import sys
import time
from argparse import ArgumentParser
from datetime import datetime, timedelta

import boto3

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)
logger = logging.getLogger('asg_util_alarms')

LAUNCH_TIME_DELAY_SECONDS = 300
PERIOD_SEC = 30
WINDOW_MINUTES = 2


def get_mean_from_data_points(data_points):
    """
    Get the mean value for input data points. Expects the key 'Average' to exist for each data point.
    """
    if len(data_points) == 0:
        return 0

    data_points_sum = 0
    for data_point in data_points:
        data_points_sum = data_points_sum + data_point['Average']
    data_points_avg = data_points_sum / len(data_points)

    return data_points_avg


def get_metric_data_cpu_util(cw_client, instance_id, cpu, start_time, end_time, period_sec):
    cpu_response = cw_client.get_metric_statistics(
        Namespace='CWAgent',
        Dimensions=[
            {
                'Name': 'AutoScalingGroupName',
                'Value': 'PicSiteASG'
            },
            {
                'Name': 'ImageId',
                'Value': 'ami-0bdd1b937142e6961'
            },
            {
                'Name': 'InstanceId',
                'Value': '{}'.format(instance_id)
            },
            {
                'Name': 'InstanceType',
                'Value': 'm4.large'
            },
            {
                'Name': 'cpu',
                'Value': '{}'.format(cpu)
            }
        ],
        MetricName='cpu_usage_idle',
        StartTime=start_time,
        EndTime=end_time,
        Period=period_sec,
        Statistics=[
            'Average'
        ],
        Unit='Percent'
    )

    if cpu_response:
        # 'Idle Percent' -> 'Utilization'
        return (100 - get_mean_from_data_points(cpu_response['Datapoints'])) / 100

    return None


def get_metric_data_disk_util(cw_client, instance_id, start_time, end_time, period_sec):
    disk_response = cw_client.get_metric_statistics(
        Namespace='CWAgent',
        Dimensions=[
            {
                'Name': 'AutoScalingGroupName',
                'Value': 'PicSiteASG'
            },
            {
                'Name': 'ImageId',
                'Value': 'ami-0bdd1b937142e6961'
            },
            {
                'Name': 'InstanceId',
                'Value': '{}'.format(instance_id)
            },
            {
                'Name': 'InstanceType',
                'Value': 'm4.large'
            },
            {
                'Name': 'name',
                'Value': 'xvda1'
            }
        ],
        MetricName='diskio_io_time',
        StartTime=start_time,
        EndTime=end_time,
        Period=period_sec,
        Statistics=[
            'Average'
        ],
        Unit='Milliseconds'
    )

    if disk_response:
        # 'Milliseconds' -> 'Utilization'
        return get_mean_from_data_points(disk_response['Datapoints']) / 1000 / period_sec

    return None


def put_metric_data_target(cw_client, target_value):
    cw_client.put_metric_data(
        Namespace='PicSiteASG',
        MetricData=[
            {
                'MetricName': 'Target',
                'Dimensions': [
                    {
                        'Name': 'AutoScalingGroupName',
                        'Value': 'PicSiteASG'
                    },
                ],
                'Timestamp': datetime.utcnow(),
                'Value': target_value,
                'Unit': 'None',
            },
        ]
    )


def run_scaling_notifier(ec2, ec2_client, cw_client, cpu_upper, cpu_lower, disk_upper, disk_lower, period_sec,
                         window_minutes):
    """

    """
    start_time = datetime.utcnow() - timedelta(minutes=window_minutes)
    end_time = datetime.utcnow()

    # Fetch running instances from PicSiteASG autoscaling group
    instances = ec2.instances.filter(
        Filters=[
            {'Name': 'instance-state-name', 'Values': ['running']},
            {'Name': 'tag:aws:autoscaling:groupName', 'Values': ['PicSiteASG']}
        ]
    )

    # Get ids from retrieved instances but exclude if not 'ok' status
    current_epoch_seconds = calendar.timegm(time.gmtime())
    waiting_instances = 0
    instance_id_list = list()
    for instance in instances:

        # Check if instance is older than the launch time delay
        parsed_epoch_seconds = instance.launch_time.timestamp()
        if current_epoch_seconds - parsed_epoch_seconds < LAUNCH_TIME_DELAY_SECONDS:
            waiting_instances = waiting_instances + 1
            continue

        # Check if instance status is 'ok'
        response = ec2_client.describe_instance_status(InstanceIds=['{}'.format(instance.id)])
        instance_statuses = response['InstanceStatuses']
        if len(instance_statuses) == 0 or instance_statuses[0]['InstanceStatus']['Status'] != 'ok':
            waiting_instances = waiting_instances + 1
            continue

        instance_id_list.append(instance.id)

    # Check if no ready instances found
    if len(instance_id_list) == 0:
        logger.warning("No ready instances found! (%s instance(s) warming up)", str(waiting_instances))
        return

    logger.info('Ready instances: %s (%s instance(s) warming up)', str(instance_id_list), str(waiting_instances))

    # Get average utilization for desired metrics
    count_cpu_util = 0
    count_disk_util = 0
    sum_cpu_util = 0
    sum_disk_util = 0

    for instance_id in instance_id_list:
        # Take average utilization for a single cpu for each instance.
        for cpu in ['cpu0', 'cpu1']:
            cpu_util = get_metric_data_cpu_util(cw_client, instance_id, cpu, start_time, end_time, period_sec)
            if cpu_util:
                sum_cpu_util = sum_cpu_util + cpu_util
                count_cpu_util = count_cpu_util + 1

        # Take average utilization for the disk for each instance.
        disk_util = get_metric_data_disk_util(cw_client, instance_id, start_time, end_time, period_sec)
        if disk_util:
            sum_disk_util = sum_disk_util + disk_util
            count_disk_util = count_disk_util + 1

    avg_cpu_util = sum_cpu_util / count_cpu_util if count_cpu_util > 0 else None
    avg_disk_util = sum_disk_util / count_disk_util if count_disk_util > 0 else None

    logger.info("Avg CPU Utilization: %s", str(avg_cpu_util))
    logger.info("Avg Disk Utilization: %s", str(avg_disk_util))

    # Calculate target based on upper and lower bounds
    if avg_cpu_util and avg_cpu_util >= cpu_upper or avg_disk_util and avg_disk_util >= disk_upper:
        target = 1
        target_msg = "Scale up"
    elif (len(instance_id_list) <= 1 and waiting_instances == 0) or avg_cpu_util and avg_cpu_util > cpu_lower \
            or avg_disk_util and avg_disk_util > disk_lower:
        target = 0.5
        target_msg = "No action"
    else:
        target = 0
        target_msg = "Scale down"

    logger.info("Target: %s (%s)", str(target), str(target_msg))

    # Send target value
    put_metric_data_target(cw_client, target)


def signal_handler(cw_client):
    # Reset Target metric
    print("ASG Util Alarms script exiting, sending target value 0.5 to Cloudwatch ...")
    put_metric_data_target(cw_client, 0.5)
    print("ASG Util Alarms script says \"Good bye.\"")
    sys.exit(0)


def main():
    # Parse arguments
    parser = ArgumentParser()
    parser.add_argument('boundaries', metavar=('cpu_upper', 'disk_upper'), type=int, nargs=2,
                        help="Supply 'cpu_upper' and 'disk_upper' bounds (0-100)")
    args = parser.parse_args()

    cpu_upper = args.boundaries[0] / 100
    disk_upper = args.boundaries[1] / 100

    # Set lower bounds based on percentage of upper bounds
    cpu_lower = cpu_upper * 0.5
    disk_lower = disk_upper * 0.5

    # Default vars
    period_sec = PERIOD_SEC
    window_minutes = WINDOW_MINUTES

    # Setup AWS resources
    region = "us-west-1"
    ec2 = boto3.resource('ec2', region_name=region)
    cw_client = boto3.client('cloudwatch', region_name=region)
    ec2_client = boto3.client('ec2', region_name=region)

    # Catch SIGINT & SIGINT
    def signal_handler_wrapper(sig, frame):
        signal_handler(cw_client)

    signal.signal(signal.SIGINT, signal_handler_wrapper)
    signal.signal(signal.SIGTERM, signal_handler_wrapper)

    # Run infinite-loop
    logging.info("Starting ASG Util Alarms script ...")
    while True:
        run_scaling_notifier(ec2, ec2_client, cw_client, cpu_upper, cpu_lower, disk_upper, disk_lower, period_sec,
                             window_minutes)
        time.sleep(15)


if __name__ == "__main__":
    main()
