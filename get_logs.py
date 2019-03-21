#!/usr/bin/python3
import csv
import os
from argparse import ArgumentParser

import boto3

LOGS_DIR = "aws_logs"


def get_logs(ec2, ec2_client, cw_client, args):
    """
    Gets logs for cpu, disk, and memory utilization, plus some info about
    network use

    """
    # get params from args
    test_id = args.boundaries[0]
    test_start_time = args.boundaries[1]
    test_end_time = args.boundaries[2]
    sample_period = args.boundaries[3]
    asg_policy_type = args.boundaries[4]
    asg_cpu_max = args.boundaries[5]
    asg_disk_max = args.boundaries[6]
    asg_scaleup_duration = args.boundaries[7]
    image_size = args.boundaries[8]
    num_users_a = args.boundaries[9]
    num_users_b = args.boundaries[10]
    num_users_c = args.boundaries[11]

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

    cpu0_responses = []
    cpu1_responses = []
    disk_responses = []
    mem_responses = [] # mem_used_percent
    network_responses = [] # NetworkOut

    for instance_id in instance_id_list:
        # Take maximum utilization for a single cpu for each instance.
        cpu0_response = cw_client.get_metric_statistics(
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
                    'Value': 'cpu0'
                }
            ],
            MetricName='cpu_usage_idle',
            StartTime=test_start_time,
            EndTime=test_end_time,
            Period=sample_period,
            Statistics=[
                'Average'
            ],
            Unit='Percent'
        )
        if cpu0_response:
            # 'Idle Percent * 100' -> 'Util Percent'
            responses = [(100 - util_val['Average']) / 100 for
                    util_val in cpu0_response['Datapoints']]
            cpu0_responses.append(responses)
        else:
            cpu0_responses.append(-1)

        # Take maximum utilization for a single cpu for each instance.
        cpu1_response = cw_client.get_metric_statistics(
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
                    'Value': 'cpu1'
                }
            ],
            MetricName='cpu_usage_idle',
            StartTime=test_start_time,
            EndTime=test_end_time,
            Period=sample_period,
            Statistics=[
                'Average'
            ],
            Unit='Percent'
        )
        if cpu1_response:
            # 'Idle Percent * 100' -> 'Util Percent'
            responses = [(100 - util_val['Average']) / 100 for
                    util_val in cpu1_response['Datapoints']]
            cpu1_responses.append(responses)
        else:
            cpu1_responses.append(-1)

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
            StartTime=test_start_time,
            EndTime=test_end_time,
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
        else:
            disk_responses.append(-1)

        mem_response = cw_client.get_metric_statistics(
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
            StartTime=test_start_time,
            EndTime=test_end_time,
            Period=sample_period,
            Statistics=[
                'Average'
            ],
            Unit='Percent'
        )

        if mem_response:
            responses = [response['Average'] for response in mem_response['Datapoints']]
            mem_responses.append(responses)
        else:
            mem_responses.append(-1)

        # unlike above, this doesnt seem to work unless very few dimensions are
        # passed in
        network_response = cw_client.get_metric_statistics(
            Namespace='AWS/EC2',
            Dimensions=[
                {
                    'Name': 'InstanceId',
                    'Value': '{}'.format(instance_id)
                }
            ],
            MetricName='NetworkOut',
            StartTime=test_start_time,
            EndTime=test_end_time,
            Period=sample_period,
            Statistics=[
                'Average'
            ]
        )

        if network_response:
            responses = [response['Average'] for response in network_response['Datapoints']]
            network_responses.append(responses)
        else:
            network_responses.append(-1)

    try:
        os.mkdir(LOGS_DIR)
    except FileExistsError:
        pass

    with open(os.path.join(LOGS_DIR, '{}_{}.csv'.format(test_id, test_end_time)), 'w') as csv_file:
        fieldnames = ['test_id',
                      'timepoint',
                      'test_start_time',
                      'test_end_time',
                      'cpu0_util',
                      'cpu1_util',
                      'mem_util',
                      'disk_util',
                      'net_util',
                      'asg_policy_type',
                      'asg_cpu_max',
                      'asg_disk_max',
                      'asg_scaleup_duration',
                      'image_size',
                      'num_users_a',
                      'num_users_b',
                      'num_users_c']

        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        writer.writeheader()
        for i in range(0, len(cpu1_responses)):
            data = {
                fieldnames[0]: test_id,
                fieldnames[1]: i,
                fieldnames[2]: test_start_time,
                fieldnames[3]: test_end_time,
                fieldnames[4]: cpu0_responses[i],
                fieldnames[5]: cpu1_responses[i],
                fieldnames[6]: mem_responses[i],
                fieldnames[7]: disk_responses[i],
                fieldnames[8]: network_responses[i],
                fieldnames[9]: asg_policy_type,
                fieldnames[10]: asg_cpu_max,
                fieldnames[11]: asg_disk_max,
                fieldnames[12]: asg_scaleup_duration,
                fieldnames[13]: image_size,
                fieldnames[14]: num_users_a,
                fieldnames[15]: num_users_b,
                fieldnames[16]: num_users_c
            }
            writer.writerow(data)


def main():
    # Parse arguments
    parser = ArgumentParser()
    parser.add_argument('boundaries',
                        metavar=('test_id',
                                 'test_start_time',
                                 'test_end_time',
                                 'sample_period',
                                 'asg_policy_type',
                                 'asg_cpu_max',
                                 'asg_disk_max',
                                 'asg_scaleup_duration',
                                 'image_size',
                                 'num_users_a',
                                 'num_users_b',
                                 'num_users_c'),
                        type=int, nargs=12,
                        help="So many arguments, look at the source ")
    args = parser.parse_args()  # hint - this crashes if you provide 0 args

    # Setup AWS resources
    region = "us-west-1"
    ec2 = boto3.resource('ec2', region_name=region)
    cw_client = boto3.client('cloudwatch', region_name=region)
    ec2_client = boto3.client('ec2', region_name=region)

    # Get logs
    print("Getting logs...")
    get_logs(ec2, ec2_client, cw_client, args)
    print("Logs retrieved.")


if __name__ == "__main__":
    main()

