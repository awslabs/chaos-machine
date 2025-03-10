import json
import os
import time
from datetime import datetime, timedelta

import boto3
import pytest
from botocore.config import Config

environment = os.getenv("ENVIRONMENT")
region = os.getenv("AWS_DEFAULT_REGION")

boto_client_config = Config(region_name=region)
sfn = boto3.client("stepfunctions", config=boto_client_config)


@pytest.fixture
def get_test_input(get_test_id, get_experiment_template_id):
    test_input = {
        "testId": f"{get_test_id}",
        "testDescription": "Test the response time and fault rate of the PetSite application during an AZ disruption",
        "experimentTemplateId": get_experiment_template_id,
        "steadyState": {
            "metrics": [
                {
                    "Id": "m1",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/X-Ray",
                            "MetricName": "ResponseTime",
                            "Dimensions": [
                                {"Name": "GroupName", "Value": "Default"},
                                {"Name": "ServiceName", "Value": "PetSite"},
                                {
                                    "Name": "ServiceType",
                                    "Value": "AWS::EC2::Instance",
                                },
                            ],
                        },
                        "Period": 60,
                        "Stat": "p90",
                    },
                },
                {
                    "Id": "m2",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/X-Ray",
                            "MetricName": "FaultRate",
                            "Dimensions": [
                                {"Name": "GroupName", "Value": "Default"},
                                {"Name": "ServiceName", "Value": "PetSite"},
                                {
                                    "Name": "ServiceType",
                                    "Value": "AWS::EC2::Instance",
                                },
                            ],
                        },
                        "Period": 60,
                        "Stat": "Average",
                    },
                },
                {
                    "Id": "m3",
                    "metricFormat": "Prometheus",
                    "query": "sum(rate(petsite_petsearches_total[2m])) * 60",
                    "step": "1m",
                },
                {"Id": "e1", "Expression": "IF(m1 > 0.5, 0, 1)"},
                {"Id": "e2", "Expression": "IF(100 * m2 > 1, 0, 1)"},
                {
                    "Id": "e3",
                    "metricFormat": "Prometheus",
                    "query": "sum(rate(petsite_petsearches_total[2m])) * 60 > bool 100",
                    "step": "1m",
                },
            ],
            "alarms": ["PetSiteOkRate"],
        },
        "hypothesis": "steadyState",
        "lookback": 300,
        "prometheusUrl": "http://10.1.186.117:31793",
    }

    return test_input


def test_az_disruption(get_state_machine_arn, get_test_input):
    execution = sfn.start_execution(
        stateMachineArn=get_state_machine_arn,
        input=json.dumps(get_test_input),
    )
    execution_arn = execution["executionArn"]
    execution_arn_short = execution_arn.split(":")[-1]

    while True:
        try:
            response = sfn.describe_execution(executionArn=execution_arn)
            start_time = response["startDate"]
            duration = datetime.now(start_time.tzinfo) - start_time

            if response["status"] == "RUNNING":
                print(
                    f"Execution {execution_arn_short} for test {get_test_input['testId']} has been RUNNING for {str(timedelta(seconds=duration.total_seconds()))}.",  # NOQA E501
                )
                time.sleep(10)
                continue
            else:
                break

        except sfn.exceptions.ExecutionDoesNotExist:
            print("Execution has not been started. Waiting...")
            time.sleep(10)
            continue

    assert response["status"] == "SUCCEEDED"
