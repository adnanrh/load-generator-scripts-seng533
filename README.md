# load-generator-scripts-seng533

jmeter tests should be run with the following parameters:

./jmeter -n -t <.jmx file path> -JusersA=<number of class A users> -JusersB=<number of class B users> -JusersC=<number of class C users> -Jduration=<test duration in seconds> -l testresults.jtl
