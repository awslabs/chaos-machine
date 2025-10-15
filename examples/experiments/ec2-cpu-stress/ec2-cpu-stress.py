# Copyright 2025, Amazon Web Services, Inc. or its affiliates. All rights reserved. Amazon Confidential and Trademark. This work is licensed under a Creative Commons Attribution 4.0 International License.
import hashlib
import time

import boto3
import psutil
import requests
from flask import Flask

app = Flask(__name__)


def get_instance_metadata():
    # Get token for IMDSv2
    token_url = "http://169.254.169.254/latest/api/token"
    token_headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
    token = requests.put(token_url, headers=token_headers, timeout=2).text

    # Headers for metadata requests
    headers = {"X-aws-ec2-metadata-token": token}

    # Get instance metadata
    instance_id = requests.get(
        "http://169.254.169.254/latest/meta-data/instance-id", headers=headers
    ).text
    availability_zone = requests.get(
        "http://169.254.169.254/latest/meta-data/placement/availability-zone",
        headers=headers,
    ).text

    return instance_id, availability_zone


# Get instance metadata once at startup with retries
instance_id = "unknown"
availability_zone = "unknown"

for attempt in range(3):
    try:
        instance_id, availability_zone = get_instance_metadata()
        print(f"Got metadata: Instance={instance_id}, AZ={availability_zone}")
        break
    except Exception as e:
        print(f"Attempt {attempt + 1} failed to get instance metadata: {e}")
        if attempt == 2:
            print("Using fallback values")
        else:
            time.sleep(1)

# Initialize CloudWatch client
cloudwatch = boto3.client("cloudwatch")


def emit_cloudwatch_metrics(response_time, cpu_percent):
    try:
        cloudwatch.put_metric_data(
            Namespace="ChaosExperiments",
            MetricData=[
                {
                    "MetricName": "ResponseTime",
                    "Dimensions": [
                        {"Name": "Service", "Value": "WebAPI"},
                        {"Name": "AvailabilityZone", "Value": availability_zone},
                        {"Name": "InstanceId", "Value": instance_id},
                    ],
                    "Value": response_time,
                    "Unit": "Milliseconds",
                },
                {
                    "MetricName": "CPUUtilization",
                    "Dimensions": [
                        {"Name": "Service", "Value": "WebAPI"},
                        {"Name": "AvailabilityZone", "Value": availability_zone},
                        {"Name": "InstanceId", "Value": instance_id},
                    ],
                    "Value": cpu_percent,
                    "Unit": "Percent",
                },
            ],
        )
        print(f"Sent metrics: ResponseTime={response_time}ms, CPU={cpu_percent}%")
    except Exception as e:
        print(f"Failed to send metrics: {e}")


@app.route("/")
def hello():
    start_time = time.time()

    # Predictable CPU work - hash computation
    data = b"stress test data" * 1000
    for _ in range(7500):  # Adjust this number to control CPU load
        hashlib.sha256(data).hexdigest()

    # Get current CPU utilization
    cpu_percent = psutil.cpu_percent()

    # Calculate response time
    response_time = (time.time() - start_time) * 1000  # in milliseconds

    # Send CloudWatch metrics
    emit_cloudwatch_metrics(response_time, cpu_percent)

    return f"CPU: {cpu_percent}%, Response Time: {response_time:.2f}ms"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
