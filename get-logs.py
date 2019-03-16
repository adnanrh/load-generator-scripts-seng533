#!/usr/bin/python3

from argparse import ArgumentParser
from datetime import datetime, timedelta

import boto3
import time

# Parse arguments
parser = ArgumentParser()
parser.add_argument('boundaries',
                    metavar=('start time', 'end time', 'sample_period'),
                    type=int, nargs=3,
                    help="Supply start time, end time, and sample period")
args = parser.parse_args() # hint - this crashes if you provide 0 args

# set global variables
start_time = args.boundaries[0] # ms since epoch
end_time = args.boundaries[1] # ms since epoch
sample_period = args.boundaries[2] # seconds
region = "us-west-1"

# Setup AWS resources
ec2 = boto3.resource('ec2', region_name=region)
cloudwatch = boto3.resource('cloudwatch', region_name=region)
cloudwatch_client = boto3.client('cloudwatch', region_name=region)
ec2_client = boto3.client('ec2', region_name=region)

def get_logs():
    """
    Gets logs for cpu, disk, and memory utilization, plus some info about
    network use

    """

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

            if response['InstanceStatuses'][0]['InstanceStatus']['Status'] == 'ok':
                instance_id_list.append(instance.id)

    print('instances founds: ' + str(instance_id_list))

    # Check if no running instances found
    if len(instance_id_list) == 0:
        print("No running & ready instances found!")
        return

    cpu_responses = []
    disk_responses = []
    mem_responses = [] # mem_used_percent
    network_responses = [] # NetworkOut

    for instance_id in instance_id_list:
        # Take maximum utilization for a single cpu for each instance.
        for cpu in ['cpu0', 'cpu1']:
            cpu_response = cloudwatch_client.get_metric_statistics(
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
                Period=sample_period,
                Statistics=[
                    'Average'
                ],
                Unit='Percent'
            )
            if cpu_response:
                # 'Idle Percent * 100' -> 'Util Percent'
                responses = [(100 - util_val['Average']) / 100 for
                        util_val in cpu_response['Datapoints']]
                cpu_responses.append(responses)

        # Take maximum utilization for the disk for each instance.
        disk_response = cloudwatch_client.get_metric_statistics(
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
            Period=sample_period,
            Statistics=[
                'Average'
            ],
            Unit='Milliseconds'
        )

        if disk_response:
            # 'Milliseconds' -> 'Util Percent'
            responses = [response['Average'] / 1000 / sample_period for
                    response in disk_response['Datapoints']]
            disk_responses.append(responses)

        mem_response = cloudwatch_client.get_metric_statistics(
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
                }
            ],
            MetricName='mem_used_percent',
            StartTime=start_time,
            EndTime=end_time,
            Period=sample_period,
            Statistics=[
                'Average'
            ],
            Unit='Percent'
        )

        if mem_response:
            responses = [response['Average'] for response in mem_response['Datapoints']]
            mem_responses.append(responses)


        # unlike above, this doesnt seem to work unless very few dimensions are
        # passed in
        network_response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/EC2',
            Dimensions=[
                {
                    'Name': 'InstanceId',
                    'Value': '{}'.format(instance_id)
                }
            ],
            MetricName='NetworkOut',
            StartTime=start_time,
            EndTime=end_time,
            Period=sample_period,
            Statistics=[
                'Average'
            ]
        )

        if network_response:
            responses = [response['Average'] for response in network_response['Datapoints']]
            network_responses.append(responses)

    print("CPU Utilization values: \n",cpu_responses)
    print("Disk responses: \n", disk_responses)
    print("Mem responses: \n", mem_responses)
    print("Network responses: \n", network_responses)

if __name__ == "__main__":
    get_logs()
