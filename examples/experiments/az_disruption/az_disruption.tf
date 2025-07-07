data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  region                    = "us-east-1"
  iam_name_prefix           = "Cust"
  fis_reports_bucket        = "fis-reports-${local.region}-${data.aws_caller_identity.current.account_id}"
  experiment_name           = "Fis-Workshop-AZ-Disruption"
  cloudwatch_dashboard_name = "AvailabilityZonePowerImpairment"
}

provider "aws" {
  region = local.region
}

data "aws_subnet" "private_subnet_1" {
  filter {
    name   = "tag:Name"
    values = ["Services/Microservices/PrivateSubnet1"]
  }
}

resource "aws_fis_experiment_template" "az_disruption" {
  description = "Disrupt AZ"
  role_arn    = aws_iam_role.az_disruption.arn

  stop_condition {
    source = "none"
  }

  action {
    name      = "AZ-Disruption"
    action_id = "aws:network:disrupt-connectivity"

    target {
      key   = "Subnets"
      value = "Subnets-Target-1"
    }

    parameter {
      key   = "duration"
      value = "PT15M"
    }

    parameter {
      key   = "scope"
      value = "availability-zone"
    }
  }

  target {
    name           = "Subnets-Target-1"
    resource_type  = "aws:ec2:subnet"
    selection_mode = "ALL"
    resource_arns  = [data.aws_subnet.private_subnet_1.arn]
  }

  experiment_report_configuration {
    data_sources {
      cloudwatch_dashboard {
        dashboard_arn = "arn:${data.aws_partition.current.partition}:cloudwatch::${data.aws_caller_identity.current.account_id}:dashboard/${local.cloudwatch_dashboard_name}"
      }
    }

    outputs {
      s3_configuration {
        bucket_name = local.fis_reports_bucket
      }
    }

  }

  tags = {
    Name = local.experiment_name
  }

}

locals {
  policy_vars = {
    Partition        = data.aws_partition.current.partition
    Account          = data.aws_caller_identity.current.account_id
    Dashboard        = "arn:${data.aws_partition.current.partition}:cloudwatch::${data.aws_caller_identity.current.account_id}:dashboard/${local.cloudwatch_dashboard_name}"
    FisReportsBucket = local.fis_reports_bucket
  }
}

resource "aws_iam_policy" "network" {
  name        = "${local.iam_name_prefix}AWSFaultInjectionSimulatorNetworkAccess-${local.region}-${local.experiment_name}"
  description = "Copy of the AWSFaultInjectionSimulatorNetworkAccess managed policy."
  policy      = templatefile("../iam/AWSFaultInjectionSimulatorNetworkAccess.json", local.policy_vars)
}

resource "aws_iam_policy" "cloudwatch" {
  name        = "${local.iam_name_prefix}-fis-experiment-report-cloudwatch-${local.region}-${local.experiment_name}"
  description = "Copy of the customer managed policy that FIS creates for retrieving data from CloudWatch dashboards for experiment reports."
  policy      = templatefile("../iam/fis-experiment-report-cloudwatch.json", local.policy_vars)
}

resource "aws_iam_policy" "report" {
  name        = "${local.iam_name_prefix}-fis-experiment-report-policy-${local.region}-${local.experiment_name}"
  description = "Copy of the customer managed policy that FIS creates for saving experiment reports to S3."
  policy      = templatefile("../iam/fis-experiment-report.json", local.policy_vars)
}

resource "aws_iam_role" "az_disruption" {
  name               = "${local.iam_name_prefix}-${local.experiment_name}-${local.region}"
  description        = "Role for the FIS Workshop AZ Disruption experiment."
  assume_role_policy = templatefile("../iam/fis.json", local.policy_vars)
}

resource "aws_iam_role_policy_attachment" "network" {
  role       = aws_iam_role.az_disruption.name
  policy_arn = aws_iam_policy.network.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.az_disruption.name
  policy_arn = aws_iam_policy.cloudwatch.arn
}

resource "aws_iam_role_policy_attachment" "report" {
  role       = aws_iam_role.az_disruption.name
  policy_arn = aws_iam_policy.report.arn
}
