#!/usr/bin/python3
import csv
import os
from argparse import ArgumentParser

import boto3

LOGS_DIR = "aws_logs"


def get_logs(ec2, ec2_client, cw_client, args):
    """
    Between the start and end times,
    - gets a list of running instances in the autoscaling group
    - obtains logs for each
    - converts these per-instance logs into per-timepoint logs
    - outputs to csv

    """
    # get params from args
    results_dir = args.results_dir

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
                {'Name': 'tag:aws:autoscaling:groupName', 'Values': ['PicSiteASG']}
            ]
    )
    instance_id_list = [instance.id for instance in instances]

    logs_by_instance = []

    for instance_id in instance_id_list:
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

        # exclude instances with no activity during the timespan of interest
        if (not cpu0_response) or (len(cpu0_response['Datapoints']) < 1):
            continue

        if cpu0_response:
            # 'Idle Percent * 100' -> 'Util Percent'
            cpu0_utils = [(100 - idle_percent['Average']) / 100 for
                    idle_percent in cpu0_response['Datapoints']]
        else:
            cpu0_utils = None

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
            cpu1_utils = [(100 - util_val['Average']) / 100 for
                    util_val in cpu1_response['Datapoints']]
        else:
            cpu1_utils = None

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
            disk_utils = [response['Average'] / 1000 / sample_period for
                    response in disk_response['Datapoints']]
        else:
            disk_utils = None

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
            mem_utils = [response['Average'] for response in mem_response['Datapoints']]
        else:
            mem_utils = None

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
            network_out_values = [response['Average'] for response in network_response['Datapoints']]
        else:
            network_out_values = None

        logs_by_instance.append({
            'instance_id': instance_id,
            'cpu0_utils': cpu0_utils,
            'cpu1_utils': cpu1_utils,
            'disk_utils': disk_utils,
            'mem_utils': mem_utils,
            'network_out_values': network_out_values
        })

    def convert_logs_by_instance_to_per_timepoint(logs_by_instance):

        def left_pad(logs_by_instance):
            '''
            Since the tests only involve scaling up, we assume missing values are
            due to late scalings and left-fill with zeroes.

            This could be wrong if for example logs in the middle are missing for
            some reason...
            '''

            # find total timepoints from oldest instance
            num_timepoints = 0
            oldest_instance = -1
            for log in logs_by_instance:
                for key, val in log.items():
                    if key == 'instance_id': continue
                    if len(log[key]) > num_timepoints:
                        num_timepoints = len(log[key])

            # perform the padding
            for log in logs_by_instance:
                if len(log[key]) < num_timepoints:
                    for key, val in log.items():
                        if key == 'instance_id': continue
                        num_missing = num_timepoints - len(log[key])
                        left_pad = [0 for missing_point in range(0, num_missing)]
                        log[key] = left_pad + log[key]
            return logs_by_instance

        padded_logs = left_pad(logs_by_instance)

        num_instances = len(padded_logs)
        num_timepoints = len(padded_logs[0]['cpu0_utils'])

        logs_by_timepoint = []
        for i in range(0, num_instances):
            for j in range(0, num_timepoints):
                # print(padded_logs[i][)
                logs_by_timepoint.append({
                    'instance_id': padded_logs[i]['instance_id'],
                    'cpu0_util': padded_logs[i]['cpu0_utils'][j],
                    'cpu1_util': padded_logs[i]['cpu1_utils'][j],
                    'disk_util': padded_logs[i]['disk_utils'][j],
                    'mem_util': padded_logs[i]['mem_utils'][j],
                    'network_out': padded_logs[i]['network_out_values'][j],
                    'timepoint': j
                })
        return logs_by_timepoint



    logs_by_timepoint = convert_logs_by_instance_to_per_timepoint(logs_by_instance)

    with open(os.path.join(results_dir, 'aws_metrics_{}_{}.csv'.format(test_id, test_end_time)), 'w') as csv_file:
        fieldnames = ['test_id',
                      'timepoint',
                      'test_start_time',
                      'test_end_time',
                      'cpu0_util',
                      'cpu1_util',
                      'mem_util',
                      'disk_util',
                      'network_out',
                      'asg_policy_type',
                      'asg_cpu_max',
                      'asg_disk_max',
                      'asg_scaleup_duration',
                      'image_size',
                      'num_users_a',
                      'num_users_b',
                      'num_users_c',
                      'instance_id']

        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        writer.writeheader()
        for i in range(0, len(logs_by_timepoint)):
            data = {
                fieldnames[0]: test_id,
                fieldnames[1]: logs_by_timepoint[i]['timepoint'],
                fieldnames[2]: test_start_time,
                fieldnames[3]: test_end_time,
                fieldnames[4]: logs_by_timepoint[i]['cpu0_util'],
                fieldnames[5]: logs_by_timepoint[i]['cpu1_util'],
                fieldnames[6]: logs_by_timepoint[i]['mem_util'],
                fieldnames[7]: logs_by_timepoint[i]['disk_util'],
                fieldnames[8]: logs_by_timepoint[i]['network_out'],
                fieldnames[9]: asg_policy_type,
                fieldnames[10]: asg_cpu_max,
                fieldnames[11]: asg_disk_max,
                fieldnames[12]: asg_scaleup_duration,
                fieldnames[13]: image_size,
                fieldnames[14]: num_users_a,
                fieldnames[15]: num_users_b,
                fieldnames[16]: num_users_c,
                fieldnames[17]: logs_by_timepoint[i]['instance_id']
            }
            writer.writerow(data)


def main():
    # Parse arguments
    parser = ArgumentParser()
    parser.add_argument('results_dir')
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
