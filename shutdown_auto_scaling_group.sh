#!/bin/bash

asg_name=${1:-PicSiteASG}

./init_auto_scaling_group.sh 0 0 0 ${asg_name}

