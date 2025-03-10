import os
import uuid

import boto3
import pytest
from botocore.config import Config

environment = os.getenv("ENVIRONMENT")
region = os.getenv("AWS_DEFAULT_REGION")

boto_client_config = Config(region_name=region)
sfn = boto3.client("stepfunctions", config=boto_client_config)
sts = boto3.client("sts", config=boto_client_config)


def pytest_addoption(parser):
    parser.addoption("--experiment-template-id", action="store")


@pytest.fixture
def get_experiment_template_id(request):
    return request.config.option.experiment_template_id


@pytest.fixture
def get_uuid():
    return str(uuid.uuid4().hex)


@pytest.fixture()
def get_test_id(get_experiment_template_id, get_uuid):
    return f"{get_experiment_template_id}-{get_uuid}"


@pytest.fixture
def get_account_info():
    response = sts.get_caller_identity()
    account_number = response["Account"]
    partition = response["Arn"].split(":")[1]
    return account_number, partition


@pytest.fixture
def get_state_machine_arn(get_account_info):
    account_number, partition = get_account_info
    state_machine_arn = f"arn:{partition}:states:{region}:{account_number}:stateMachine:chaos-machine-{environment}"
    return state_machine_arn
