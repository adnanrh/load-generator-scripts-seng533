# load-generator-scripts-seng533

jmeter tests should be run with the following parameters:

./jmeter -n -t <.jmx file path> -JusersA=<num A users> -JusersB=<num B users> -JusersC=<num C users> -Jduration=<test duration in seconds> -l testresults.jtl
