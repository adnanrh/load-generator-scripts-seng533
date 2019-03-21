#!/usr/bin/python3
import logging
import signal
import sys
from argparse import ArgumentParser
from datetime import datetime, timedelta

import boto3
import time

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)
logger = logging.getLogger('asg_util_alarms')


def get_mean_from_datapoints(data_points):
    """
    Get the mean value for input data points. Expects the key 'Average' to exist for each data point.
    """
    if len(data_points) == 0:
        return 0

    sum = 0
    for data_point in data_points:
        sum = sum + data_point['Average']
    avg = sum / len(data_points)

    return avg


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
    instance_id_list = list()
    for instance in instances:
        response = ec2_client.describe_instance_status(
            InstanceIds=['{}'.format(instance.id)]
        )
        instance_statuses = response['InstanceStatuses']
        if len(instance_statuses) > 0 and instance_statuses[0]['InstanceStatus']['Status'] == 'ok':
            instance_id_list.append(instance.id)

    # Check if no running instances found
    if len(instance_id_list) == 0:
        logger.warning("No running instances found!")
        return

    logger.info('Instances founds: %s', str(instance_id_list))

    max_cpu_util = 0
    max_disk_util = 0

    for instance_id in instance_id_list:
        # Take maximum utilization for a single cpu for each instance.
        for cpu in ['cpu0', 'cpu1']:
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
                # 'Idle Percent * 100' -> 'Util Percent'
                avg = (100 - get_mean_from_datapoints(cpu_response['Datapoints'])) / 100
                max_cpu_util = max(max_cpu_util, avg)

        # Take maximum utilization for the disk for each instance.
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
            # 'Milliseconds' -> 'Util Percent'
            avg = get_mean_from_datapoints(disk_response['Datapoints']) / 1000 / period_sec
            max_disk_util = max(max_disk_util, avg)

    logger.info("Max CPU Utilization: %s", str(max_cpu_util))
    logger.info("Max Disk Utilization: %s", str(max_disk_util))

    # Calculate target based on upper and lower bounds
    if max_cpu_util >= cpu_upper or max_disk_util >= disk_upper:
        target = 1
    elif len(instance_id_list) <= 1 or max_cpu_util > cpu_lower or max_disk_util > disk_lower:
        target = 0.5
    else:
        target = 0

    logger.info("Target: %s", str(target))

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
    period_sec = 30
    window_minutes = 4

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
