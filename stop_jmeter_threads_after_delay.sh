#!/bin/bash

# Sleep for input seconds, or execute immediately if no input given
sleep ${1:-0}

echo "Forcing JMeter threads to stop ..."
/home/ubuntu/apache-jmeter-5.1/bin/stoptest.sh
echo "Stopped JMeter threads."