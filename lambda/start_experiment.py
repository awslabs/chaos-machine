import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime

import boto3

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL"))

fis = boto3.client("fis")
ddb = boto3.client("dynamodb")


def datetime_handler(x):
    if isinstance(x, datetime):
        return x.isoformat()
    raise TypeError("Unknown type")


def lambda_handler(event, context):
    logger.info(
        f"Event received: {json.dumps(event, default=datetime_handler, indent=4)}"
    )
    logger.info(f"boto3 version: {boto3.__version__}")

    try:
        client_token = str(uuid.uuid4())
        experiment = fis.start_experiment(
            clientToken=client_token,
            experimentTemplateId=event["Input"]["experimentTemplateId"],
        )
        logger.info(
            f"Experiment: {json.dumps(experiment, default=datetime_handler, indent=4)}"
        )
        item = {
            "testId": {"S": event["Input"]["testId"]},
            "experimentId": {"S": experiment["experiment"]["id"]},
            "taskToken": {"S": event["TaskToken"]},
            "executionName": {"S": event["ExecutionName"]},
        }
        if "testDescription" in event["Input"]:
            item["testDescription"] = {"S": event["Input"]["testDescription"]}
        ddb.put_item(TableName=event["TableName"], Item=item)

    except Exception as e:
        (
            exception_type,
            exception_value,
            exception_traceback,
        ) = sys.exc_info()
        traceback_string = traceback.format_exception(
            exception_type, exception_value, exception_traceback
        )
        err_msg = json.dumps(
            {
                "errorType": exception_type.__name__,
                "errorMessage": str(exception_value),
                "stackTrace": traceback_string,
            }
        )
        logger.error(err_msg)
        response = fis.stop_experiment(id=experiment["experiment"]["id"])
        logger.error(
            f"Stopping experiment: {json.dumps(response, default=datetime_handler, indent=4)}"
        )
        raise e
