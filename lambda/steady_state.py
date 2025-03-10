import json
import logging
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

import boto3
import urllib3
from jsonschema import validate

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL"))

fis = boto3.client("fis")
cw = boto3.client("cloudwatch")


def datetime_handler(x):
    if isinstance(x, datetime):
        return x.isoformat()
    raise TypeError("Unknown type")


class SteadyStateError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message}"


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
    for result in response["MetricDataResults"]:
        if not result["Values"]:
            raise SteadyStateError(
                f"The {type} metric {result['Id']} does not return any values."
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


def evaluate_steady_state_cw_metrics(metrics):
    found_expression = False
    expressions_not_steady_state = []
    for result in metrics["MetricDataResults"]:
        id = result["Id"]
        if id.startswith("e"):
            found_expression = True
            logger.info(
                f"Evaluating expression: {json.dumps(result, default=datetime_handler, indent=4)}"
            )
            if any(value == 0 for value in result["Values"]):
                expressions_not_steady_state.append(id)
                logger.info(f"Expression {id} is not in steady state.")

    if expressions_not_steady_state:
        raise SteadyStateError(
            f"Expressions not in steady state: {expressions_not_steady_state}"
        )

    if not found_expression:
        logger.info("No steady state expression found.")
        raise SteadyStateError("No steady state expression found.")

    return


def evaluate_steady_state_prom_metrics(metrics):
    found_expression = False
    expressions_not_steady_state = []
    for result in metrics["PrometheusDataResults"]:
        id = result["data"]["result"][0]["metric"]
        if id.startswith("e"):
            found_expression = True
            logger.info(
                f"Evaluating expression: {json.dumps(result, default=datetime_handler, indent=4)}"
            )
            if any(value[1] == "0" for value in result["data"]["result"][0]["values"]):
                expressions_not_steady_state.append(id)
                logger.info(f"Expression {id} is not in steady state.")

    if expressions_not_steady_state:
        raise SteadyStateError(
            f"Expressions not in steady state: {expressions_not_steady_state}"
        )

    if not found_expression:
        logger.info("No steady state expression found.")
        raise SteadyStateError("No steady state expression found.")

    return


def get_alarms(alarms):
    response = cw.describe_alarms(
        AlarmNames=alarms,
        AlarmTypes=["MetricAlarm", "CompositeAlarm"],
    )
    logger.info(
        f"Steady state alarms: {json.dumps(response, default=datetime_handler, indent=4)}"
    )
    return response


def evaluate_steady_state_alarms(alarms):
    alarms_not_steady_state = []
    for composite_alarm in alarms["CompositeAlarms"]:
        logger.info(
            f"Evaluating composite alarm: {json.dumps(composite_alarm, default=datetime_handler, indent=4)}"
        )
        if composite_alarm["StateValue"] in ["ALARM", "INSUFFICIENT_DATA"]:
            alarms_not_steady_state.append(composite_alarm["AlarmName"])
            logger.info(
                f"Composite alarm {composite_alarm['AlarmName']} is not in steady state."
            )

    for metric_alarm in alarms["MetricAlarms"]:
        logger.info(
            f"Evaluating metric alarm: {json.dumps(metric_alarm, default=datetime_handler, indent=4)}"
        )
        if metric_alarm["StateValue"] in ["ALARM", "INSUFFICIENT_DATA"]:
            alarms_not_steady_state.append(metric_alarm["AlarmName"])
            logger.info(
                f"Metric alarm {metric_alarm['AlarmName']} is not in steady state."
            )

    if alarms_not_steady_state:
        raise SteadyStateError(f"Alarms not in steady state: {alarms_not_steady_state}")

    return


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
        f"{metric_format} metrics specified in steadyState: {json.dumps(filtered_metrics, default=datetime_handler, indent=4)}"
    )
    return filtered_metrics


def lambda_handler(event, context):
    logger.info(
        f"Event received: {json.dumps(event, default=datetime_handler, indent=4)}"
    )
    logger.info(f"boto3 version: {boto3.__version__}")

    metrics_end_time = datetime.now(timezone.utc)
    delta = timedelta(seconds=event.get("lookback", 300))
    metrics_start_time = metrics_end_time - delta

    try:
        with open("/opt/schemas/chaos-machine-input.json", "r") as f:
            schema = json.load(f)
        validate(instance=event, schema=schema)

        experiment_template = fis.get_experiment_template(
            id=event["experimentTemplateId"]
        )
        logger.info(
            f"Experiment: {json.dumps(experiment_template, default=datetime_handler, indent=4)}"
        )

        # Metrics

        if "metrics" in event["steadyState"]:
            steady_state_cw_metrics = filter_metrics(
                event["steadyState"]["metrics"], "CloudWatch"
            )
            steady_state_prom_metrics = filter_metrics(
                event["steadyState"]["metrics"], "Prometheus"
            )

            # CloudWatch

            if steady_state_cw_metrics:
                steady_state_cw_metrics_results = get_cw_metrics(
                    steady_state_cw_metrics,
                    metrics_start_time,
                    metrics_end_time,
                    "steadyState",
                )

                evaluate_steady_state_cw_metrics(steady_state_cw_metrics_results)

            # Prometheus

            if steady_state_prom_metrics:
                prometheus_url = event.get("prometheusUrl")
                steady_state_prom_metrics_results = get_prom_metrics(
                    steady_state_prom_metrics,
                    metrics_start_time,
                    metrics_end_time,
                    prometheus_url,
                    "steadyState",
                )

                evaluate_steady_state_prom_metrics(steady_state_prom_metrics_results)

        # Alarms

        if "alarms" in event["steadyState"]:
            steady_state_alarms = get_alarms(event["steadyState"]["alarms"])

            evaluate_steady_state_alarms(steady_state_alarms)

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
