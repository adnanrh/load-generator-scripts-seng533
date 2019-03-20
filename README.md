# Load Generator Scripts SENG 533
_Now more automated!_

## Running all tests
Just one command:
```bash
./run-tests.sh 
```
NOTE: If interrupted pre-maturely, or if the shell crashes during a test run, you MUST run the teardown:
```bash
./shutdown_load_balancing.sh
./shutdown_auto_scaling_groups.sh
```

## Running tests individually
This is for testing the tests.
Remember that load balancers and instances cost money, so don't forget to teardown!

Setup:
```bash
./init_load_balancing.sh
./init_auto_scaling_groups.sh
```

Teardown:
```bash
./shutdown_load_balancing.sh
./shutdown_auto_scaling_groups.sh
```

## 'test_list' Notes

- `test_duration` refers to the time to scale from 0 users to max users
- `autoscaling_value` refers to type of policy. 0 is 'none', 1 is 'dynamic'
