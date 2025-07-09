import json
import logging
import os
import sys
import traceback
from datetime import datetime, timedelta

import boto3
import urllib3

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL"))

fis = boto3.client("fis")
cw = boto3.client("cloudwatch")
ddb = boto3.client("dynamodb")
ssm = boto3.client("ssm")

experiments_table = os.getenv("EXPERIMENTS_TABLE")


def time_ceil(time, delta):
    epoch = datetime(1970, 1, 1, tzinfo=time.tzinfo)
    mod = (time - epoch) % delta
    if mod:
        return time + (delta - mod)
    return time


def datetime_handler(x):
    if isinstance(x, datetime):
        return x.isoformat()
    raise TypeError("Unknown type")


def get_cw_metrics(metrics, start_time, end_time, type):
    logger.info(f"Retrieving metrics from {start_time} to {end_time}.")
    response = cw.get_metric_data(
        MetricDataQueries=metrics,
        StartTime=start_time,
        EndTime=end_time,
    )
    logger.info(
        f"{type} CloudWatch metrics: {json.dumps(response, default=datetime_handler, indent=4)}"
    )

    return response


def get_prom_metrics(metrics, start_time, end_time, prometheus_url, type):
    http = urllib3.PoolManager()
    prometheus_data_results = {"PrometheusDataResults": []}
    logger.info(f"Retrieving metrics from {start_time} to {end_time}.")
    for metric in metrics:
        response = http.request(
            "GET",
            f"{prometheus_url}/api/v1/query_range",
            fields={
                "query": str(metric.get("query")),
                "start": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "step": str(metric.get("step")),
            },
        )

        response_decoded = json.loads(response.data.decode("utf-8"))
        response_decoded["data"]["result"][0]["metric"] = str(metric.get("Id"))
        prometheus_data_results["PrometheusDataResults"].append(response_decoded)
    logger.info(
        f"{type} Prometheus metrics: {json.dumps(prometheus_data_results, default=datetime_handler, indent=4)}"
    )

    return prometheus_data_results


def evaluate_hypothesis_cw_metrics(metrics):
    found_expression = False
    expressions_false = []
    for result in metrics["MetricDataResults"]:
        id = result["Id"]
        if id.startswith("e"):
            found_expression = True
            logger.info(
                f"Evaluating expression: {json.dumps(result, default=datetime_handler, indent=4)}"
            )
            if any(value == 0 for value in result["Values"]):
                expressions_false.append(id)
                logger.info(
                    f"Expression {id} is false (0) and does not support the hypothesis."
                )

    if expressions_false:
        logger.info(
            f"Expressions that do not support the hypothesis: {expressions_false}"
        )
        return False

    if not found_expression:
        logger.info("No hypothesis expression found.")
        return False

    return True


def evaluate_hypothesis_prom_metrics(metrics):
    found_expression = False
    expressions_false = []
    for result in metrics["PrometheusDataResults"]:
        id = result["data"]["result"][0]["metric"]
        if id.startswith("e"):
            found_expression = True
            logger.info(
                f"Evaluating expression: {json.dumps(result, default=datetime_handler, indent=4)}"
            )
            if any(value[1] == "0" for value in result["data"]["result"][0]["values"]):
                expressions_false.append(id)
                logger.info(
                    f"Expression {id} is false (0) and does not support the hypothesis."
                )

    if expressions_false:
        logger.info(
            f"Expressions that do not support the hypothesis: {expressions_false}"
        )
        return False

    if not found_expression:
        logger.info("No steady state expression found.")
        return False

    return True


def get_alarm_state_history(alarm, start_time, end_time, type):
    logger.info(f"Retrieving alarm history from {start_time} to {end_time}.")
    response = cw.describe_alarm_history(
        AlarmName=alarm,
        AlarmTypes=["MetricAlarm", "CompositeAlarm"],
        HistoryItemType="StateUpdate",
        StartDate=start_time,
        EndDate=end_time,
    )
    logger.info(
        f"{type} alarm {alarm} history: {json.dumps(response, default=datetime_handler, indent=4)}"
    )
    return response


def evaluate_hypothesis_alarm_state_history(alarms, start_time, end_time, type):
    alarms_false = []
    for alarm in alarms:
        alarm_history = get_alarm_state_history(alarm, start_time, end_time, type)
        for alarm_history_item in alarm_history["AlarmHistoryItems"]:
            if alarm_history_item["HistorySummary"] in [
                "Alarm updated from OK to ALARM"
            ]:
                alarms_false.append(alarm)
                logger.info(
                    f"{type} alarm {alarm} was updated from OK to ALARM during the experiment and does not support the hypothesis."
                )

    if alarms_false:
        logger.info(f"Alarms that do not support the hypothesis: {alarms_false}")
        return False

    return True


def filter_metrics(metrics, metric_format):
    filtered_metrics = [
        metric
        for metric in metrics
        if metric.get("metricFormat", "CloudWatch") == metric_format
    ]
    for metric in filtered_metrics:
        metric.pop("metricFormat", None)
        if metric_format == "CloudWatch":
            metric["ReturnData"] = True
    logger.info(
        f"{metric_format} metrics specified in hypothesis: {json.dumps(filtered_metrics, default=datetime_handler, indent=4)}"
    )
    return filtered_metrics


def lambda_handler(event, context):
    logger.info(
        f"Event received: {json.dumps(event, default=datetime_handler, indent=4)}"
    )
    logger.info(f"boto3 version: {boto3.__version__}")

    try:
        if "experimentTemplateId" in event:
            response = fis.get_experiment(
                id=event["continueExecutionOutput"]["experimentId"]
            )
            start_time = response["experiment"]["startTime"]
            end_time = response["experiment"]["endTime"]

        elif "automationDocumentName" in event:
            response = ssm.describe_automation_executions(
                Filters=[
                    {
                        "Key": "ExecutionId",
                        "Values": [event["continueExecutionOutput"]["experimentId"]],
                    }
                ]
            )
            start_time = response["AutomationExecutionMetadataList"][0][
                "ExecutionStartTime"
            ]
            end_time = response["AutomationExecutionMetadataList"][0][
                "ExecutionEndTime"
            ]

        logger.info(
            f"Experiment: {json.dumps(response, default=datetime_handler, indent=4)}"
        )

        recovery_delay = event.get("recoveryDelay")
        recovery_duration = event.get("recoveryDuration")

        if recovery_delay is not None and recovery_duration is not None:
            metrics_start_time = end_time + timedelta(seconds=recovery_delay)
            metrics_end_time = metrics_start_time + timedelta(seconds=recovery_duration)
        else:
            metrics_start_time = start_time
            metrics_end_time = end_time

        metrics_end_time_ceil = time_ceil(metrics_end_time, timedelta(minutes=1))

        if event["hypothesis"] == "steadyState":
            hypothesis_metrics = event["steadyState"].get("metrics", [])
            hypothesis_alarms = event["steadyState"].get("alarms", [])
        else:
            hypothesis_metrics = event["hypothesis"].get("metrics", [])
            hypothesis_alarms = event["hypothesis"].get("alarms", [])

        # Metrics

        if hypothesis_metrics:
            hypothesis_cw_metrics = filter_metrics(hypothesis_metrics, "CloudWatch")
            hypothesis_prom_metrics = filter_metrics(hypothesis_metrics, "Prometheus")

            # CloudWatch

            if hypothesis_cw_metrics:
                hypothesis_cw_metrics_results = get_cw_metrics(
                    hypothesis_cw_metrics,
                    metrics_start_time,
                    metrics_end_time_ceil,
                    "hypothesis",
                )
                if not evaluate_hypothesis_cw_metrics(hypothesis_cw_metrics_results):
                    return {"nextState": "NotSupported"}

            # Prometheus

            if hypothesis_prom_metrics:
                prometheus_url = event.get("prometheusUrl")
                hypothesis_prom_metrics_results = get_prom_metrics(
                    hypothesis_prom_metrics,
                    metrics_start_time,
                    metrics_end_time_ceil,
                    prometheus_url,
                    "hypothesis",
                )
                if not evaluate_hypothesis_prom_metrics(
                    hypothesis_prom_metrics_results
                ):
                    return {"nextState": "NotSupported"}
        # Alarms

        if hypothesis_alarms:
            if not evaluate_hypothesis_alarm_state_history(
                hypothesis_alarms,
                metrics_start_time,
                metrics_end_time,
                "hypothesis",
            ):
                return {"nextState": "NotSupported"}

        return {"nextState": "Supported"}

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
        deleted_item = ddb.delete_item(
            TableName=experiments_table,
            Key={
                "testId": {"S": event["testId"]},
                "experimentId": {"S": event["continueExecutionOutput"]["experimentId"]},
            },
            ReturnValues="ALL_OLD",
        )
        logger.info(
            f"Deleted item from tests table: {json.dumps(deleted_item['Attributes'], default=datetime_handler, indent=4)}"
        )
        raise e
