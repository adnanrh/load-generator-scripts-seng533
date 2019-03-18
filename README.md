# load-generator-scripts-seng533

jmeter tests should be run with the following parameters:

./jmeter -n -t <.jmx file path> -JusersA=<num A users> -JusersB=<num B users> -JusersC=<num C users> -Jduration=<test duration in seconds> -l testresults.jtl

test_list notes

- test duration refers to the time to scale from 0 users to max users

- autoscaling_value refers to type of policy. 0 is 'none', 1 is 'dynamic'
