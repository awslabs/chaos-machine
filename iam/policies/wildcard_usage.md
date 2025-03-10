This table provides justification for actions in IAM policies that use wildcards for the `Resource` property. Related actions in the actual policies may be described in the table using wildcards for conciseness, rather than listing them all out.

| Policy | Action | Justification |
|------|------|------|
| [continue-execution](continue-execution.json) | `states:Send` <br> `logs:CreateLogStream` <br> `ec2:*NetworkInterface*` | Action does not support resource-level permissions <br> Physical IDs not being used for log streams <br> Actions do not support resource-level permissions |
| [evaluate-hypothesis](evaluate-hypothesis.json) | `fis:GetExperiment` <br> `cloudwatch:*` <br> `logs:CreateLogStream` <br> `ec2:*NetworkInterface*` | Experiment IDs will be unknown <br> Metrics and alarms will be unknown <br> Physical IDs not being used for log streams <br> Actions do not support resource-level permissions |
| [start-experiment](start-experiment.json) | `fis:St*Experiment` <br> `logs:CreateLogStream` <br> `ec2:*NetworkInterface*` | Experiment and template IDs will be unknown <br> Physical IDs not being used for log streams <br> Actions do not support resource-level permissions |
| [state-machine](state-machine.json) | `logs:*` | Actions do not support resource-level permissions |
| [steady-state](steady-state.json) | `fis:GetExperiment` <br> `cloudwatch:*` <br> `logs:CreateLogStream` <br> `ec2:*NetworkInterface*` | Experiment IDs will be unknown <br> Metrics and alarms will be unknown <br> Physical IDs not being used for log streams <br> Actions do not support resource-level permissions
