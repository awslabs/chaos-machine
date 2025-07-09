import json
import logging
import os
import sys
import traceback
from datetime import datetime

import boto3

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL"))

sfn = boto3.client("stepfunctions")
ddb = boto3.client("dynamodb")

experiments_table = os.getenv("EXPERIMENTS_TABLE")


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
        if event["source"] == "aws.fis":
            experiment_id = event["detail"]["experiment-id"]
            experiment_type = "FIS"
            status = event["detail"]["new-state"]["status"]
            failed_statuses = ["stopped", "failed"]
            completed_statuses = ["completed"]
        elif event["source"] == "aws.ssm":
            experiment_id = event["detail"]["ExecutionId"]
            experiment_type = "SSM"
            status = event["detail"]["Status"]
            failed_statuses = ["Cancelled", "Failed", "TimedOut"]
            completed_statuses = ["Success"]

        item = ddb.query(
            TableName=experiments_table,
            IndexName=f"{experiments_table}-experimentId",
            KeyConditionExpression="experimentId = :experimentId",
            ExpressionAttributeValues={":experimentId": {"S": experiment_id}},
        )
        logger.info(f"item: {json.dumps(item, default=datetime_handler, indent=4)}")

        test_id = item["Items"][0]["testId"]["S"]
        task_token = item["Items"][0]["taskToken"]["S"]

        if status in failed_statuses:
            deleted_item = ddb.delete_item(
                TableName=experiments_table,
                Key={
                    "testId": {"S": test_id},
                    "experimentId": {"S": experiment_id},
                },
                ReturnValues="ALL_OLD",
            )
            logger.info(
                f"Deleted item from tests table: {json.dumps(deleted_item['Attributes'], default=datetime_handler, indent=4)}"
            )
            sfn.send_task_failure(
                taskToken=task_token,
                error="ExperimentStoppedOrFailed",
                cause=json.dumps(
                    {
                        "errorMessage": f"{experiment_type} experiment {experiment_id} status is {status}.",
                        "errorType": "ExperimentStoppedOrFailed",
                    }
                ),
            )
            logger.info(f"Sent task failure for {experiment_id} to Step Functions")
        elif status in completed_statuses:
            sfn.send_task_success(
                taskToken=task_token,
                output=json.dumps({"experimentId": experiment_id}),
            )
            logger.info(f"Sent task success for {experiment_id} to Step Functions")

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
        raise e
