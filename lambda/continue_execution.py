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
        item = ddb.query(
            TableName=experiments_table,
            IndexName=f"{experiments_table}-experimentId",
            KeyConditionExpression="experimentId = :experimentId",
            ExpressionAttributeValues={
                ":experimentId": {"S": event["detail"]["experiment-id"]}
            },
        )
        logger.info(f"item: {json.dumps(item, default=datetime_handler, indent=4)}")
        if event["detail"]["new-state"]["status"] in ("stopped", "failed"):
            deleted_item = ddb.delete_item(
                TableName=experiments_table,
                Key={
                    "testId": {"S": item["Items"][0]["testId"]["S"]},
                    "experimentId": {"S": item["Items"][0]["experimentId"]["S"]},
                },
                ReturnValues="ALL_OLD",
            )
            logger.info(
                f"Deleted item from tests table: {json.dumps(deleted_item['Attributes'], default=datetime_handler, indent=4)}"
            )
            sfn.send_task_failure(
                taskToken=item["Items"][0]["taskToken"]["S"],
                error="ExperimentStoppedOrFailed",
                cause=json.dumps(
                    {
                        "errorMessage": f"Experiment {event['detail']['experiment-id']} was {event['detail']['new-state']['status']}.",
                        "errorType": "ExperimentStoppedOrFailed",
                    }
                ),
            )
            logger.info(
                f"Sent task failure for {event['detail']['experiment-id']} to Step Functions"
            )
        if event["detail"]["new-state"]["status"] == "completed":
            sfn.send_task_success(
                taskToken=item["Items"][0]["taskToken"]["S"],
                output=json.dumps({"experimentId": event["detail"]["experiment-id"]}),
            )
            logger.info(
                f"Sent task success for {event['detail']['experiment-id']} to Step Functions"
            )

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
