data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

################################################################################
# Application resources
################################################################################

locals {

  tags = {
    Application = "ChaosMachine"
    ProjectEnv  = var.project_env
  }

  lambda = {
    functions = [
      {
        name                  = "steady-state"
        role_arn              = var.create_iam_roles ? null : var.lambda_steady_state_role_arn
        permission_principal  = "states.amazonaws.com"
        permission_source_arn = "arn:${data.aws_partition.current.partition}:states:${data.aws_region.current.name}:${data.aws_caller_identity.current.id}:stateMachine:chaos-machine-${var.project_env}"
        environment_variables = var.lambda_environment_variables
        layers                = [aws_lambda_layer_version.layer.arn]
      },
      {
        name                  = "start-experiment"
        role_arn              = var.create_iam_roles ? null : var.lambda_start_experiment_role_arn
        permission_principal  = "states.amazonaws.com"
        permission_source_arn = "arn:${data.aws_partition.current.partition}:states:${data.aws_region.current.name}:${data.aws_caller_identity.current.id}:stateMachine:chaos-machine-${var.project_env}"
        environment_variables = var.lambda_environment_variables
        layers                = []
      },
      {
        name                  = "continue-execution"
        role_arn              = var.create_iam_roles ? null : var.lambda_continue_execution_role_arn
        permission_principal  = "events.amazonaws.com"
        permission_source_arn = "arn:${data.aws_partition.current.partition}:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.id}:rule/chaos-machine-${var.project_env}-continue-execution-*"
        environment_variables = merge(var.lambda_environment_variables, {
          EXPERIMENTS_TABLE = aws_dynamodb_table.this[0].name
        })
        layers = []
      },
      {
        name                  = "evaluate-hypothesis"
        role_arn              = var.create_iam_roles ? null : var.lambda_evaluate_hypothesis_role_arn
        permission_principal  = "states.amazonaws.com"
        permission_source_arn = "arn:${data.aws_partition.current.partition}:states:${data.aws_region.current.name}:${data.aws_caller_identity.current.id}:stateMachine:chaos-machine-${var.project_env}"
        environment_variables = merge(var.lambda_environment_variables, {
          EXPERIMENTS_TABLE = aws_dynamodb_table.this[0].name
        })
        layers = []
      },
    ]
  }

}

data "archive_file" "this" {
  for_each    = var.create_chaos_machine ? { for function in local.lambda.functions : function.name => function } : {}
  type        = "zip"
  source_file = "${path.module}/lambda/${replace(each.key, "-", "_")}.py"
  output_path = "${path.module}/lambda/${replace(each.key, "-", "_")}.zip"
}

resource "aws_lambda_layer_version" "layer" {
  layer_name               = "chaos-machine"
  filename                 = "${path.module}/lambda/layer/chaos-machine.zip"
  compatible_architectures = ["x86_64"]
  compatible_runtimes      = [var.lambda_runtime]
  source_code_hash         = filebase64sha256("${path.module}/lambda/layer/chaos-machine.zip")
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = var.create_chaos_machine ? { for function in local.lambda.functions : function.name => function } : {}
  name              = "/aws/lambda/chaos-machine-${var.project_env}-${each.key}"
  retention_in_days = var.lambda_cloudwatch_log_group_retention_in_days
  tags              = local.tags
}

resource "aws_lambda_function" "this" {
  for_each         = var.create_chaos_machine ? { for function in local.lambda.functions : function.name => function } : {}
  function_name    = "chaos-machine-${var.project_env}-${each.key}"
  filename         = data.archive_file.this[each.key].output_path
  source_code_hash = data.archive_file.this[each.key].output_base64sha256
  role             = var.create_iam_roles ? aws_iam_role.this[each.key].arn : each.value.role_arn
  handler          = "${replace(each.key, "-", "_")}.lambda_handler"
  runtime          = var.lambda_runtime
  layers           = each.value.layers
  timeout          = 30
  vpc_config {
    security_group_ids = var.lambda_security_group_ids
    subnet_ids         = var.lambda_subnet_ids
  }

  logging_config {
    log_group  = aws_cloudwatch_log_group.lambda[each.key].name
    log_format = "Text"
  }

  tags = local.tags
  environment {
    variables = merge({
      LOG_LEVEL = var.lambda_log_level
      },
    each.value.environment_variables)
  }
}
resource "aws_lambda_permission" "this" {
  for_each      = var.create_chaos_machine ? { for function in local.lambda.functions : function.name => function } : {}
  statement_id  = "AllowExecution"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this[each.key].function_name
  principal     = each.value.permission_principal
  source_arn    = each.value.permission_source_arn
}

resource "aws_cloudwatch_event_rule" "continue_execution_fis" {
  count       = var.create_chaos_machine ? 1 : 0
  name        = "chaos-machine-${var.project_env}-continue-execution-fis"
  description = "Continue FIS experiment"
  event_pattern = jsonencode({
    source      = ["aws.fis"],
    detail-type = ["FIS Experiment State Change"],
    detail = {
      new-state = {
        status = ["completed", "stopped", "failed"]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "continue_execution_fis" {
  count     = var.create_chaos_machine ? 1 : 0
  target_id = "chaos-machine-${var.project_env}-continue-execution"
  rule      = aws_cloudwatch_event_rule.continue_execution_fis[0].name
  arn       = aws_lambda_function.this["continue-execution"].arn
}

resource "aws_cloudwatch_event_rule" "continue_execution_ssm" {
  count       = var.create_chaos_machine ? 1 : 0
  name        = "chaos-machine-${var.project_env}-continue-execution-ssm"
  description = "Continue SSM experiment"
  event_pattern = jsonencode({
    source      = ["aws.ssm"],
    detail-type = ["EC2 Automation Execution Status-change Notification"],
    detail = {
      Status = ["Success", "Cancelled", "Failed", "TimedOut"]

    }
  })
}

resource "aws_cloudwatch_event_target" "continue_execution_ssm" {
  count     = var.create_chaos_machine ? 1 : 0
  target_id = "chaos-machine-${var.project_env}-continue-execution"
  rule      = aws_cloudwatch_event_rule.continue_execution_ssm[0].name
  arn       = aws_lambda_function.this["continue-execution"].arn
}

resource "aws_dynamodb_table" "this" {
  count        = var.create_chaos_machine ? 1 : 0
  name         = "chaos-machine-${var.project_env}-tests"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "testId"
  range_key    = "experimentId"

  attribute {
    name = "testId"
    type = "S"
  }

  attribute {
    name = "experimentId"
    type = "S"
  }

  global_secondary_index {
    name               = "chaos-machine-${var.project_env}-tests-experimentId"
    hash_key           = "experimentId"
    projection_type    = "INCLUDE"
    non_key_attributes = ["taskToken", "experimentType"]
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "sfn" {
  count             = var.create_chaos_machine ? 1 : 0
  name              = "/aws/vendedlogs/states/chaos-machine-${var.project_env}"
  retention_in_days = var.state_machine_cloudwatch_log_group_retention_in_days
  tags              = local.tags
}

resource "aws_sfn_state_machine" "this" {
  count    = var.create_chaos_machine ? 1 : 0
  name     = "chaos-machine-${var.project_env}"
  role_arn = var.create_iam_roles ? aws_iam_role.this["state-machine"].arn : var.state_machine_role_arn

  logging_configuration {
    include_execution_data = true
    level                  = var.state_machine_log_level
    log_destination        = "${aws_cloudwatch_log_group.sfn[0].arn}:*"
  }

  definition = <<EOF
{
  "StartAt": "ErrorHandler",
  "States": {
    "ErrorHandler": {
      "Type": "Parallel",
      "Branches": [
        {
          "StartAt": "SteadyState",
          "States": {
            "SteadyState": {
              "Type": "Task",
              "Resource":"${aws_lambda_function.this["steady-state"].arn}",
              "ResultPath": null,
              "Next": "Experiment"
            },
            "Experiment": {
              "Type": "Task",
              "Resource":"arn:${data.aws_partition.current.partition}:states:::lambda:invoke.waitForTaskToken",
              "Parameters": {
                "FunctionName": "${aws_lambda_function.this["start-experiment"].function_name}",
                "Payload": {
                  "Input.$": "$",
                  "TaskToken.$": "$$.Task.Token",
                  "TableName": "${aws_dynamodb_table.this[0].name}",
                  "ExecutionName.$": "$$.Execution.Name"
                }
              },
              "ResultPath": "$.continueExecutionOutput",
              "Next": "EvaluateOrRecover"
            },
            "EvaluateOrRecover": {
              "Type": "Choice",
              "Choices": [
                {
                  "Variable": "$.recoveryDelay",
                  "IsPresent": true,
                  "Next": "RecoveryCalc"
                }
              ],
              "Default": "PauseForMetrics"
            },
            "RecoveryCalc": {
              "Type": "Pass",
              "Parameters": {
                "recoveryTotal.$": "States.MathAdd($.recoveryDelay,$.recoveryDuration)"
              },
              "ResultPath": "$.math",
              "Next": "Recovery"
            },
            "Recovery": {
              "Type": "Wait",
              "SecondsPath": "$.math.recoveryTotal",
              "Next": "PauseForMetrics"
            },
            "PauseForMetrics": {
              "Type": "Wait",
              "Seconds": 60,
              "Next": "EvaluateHypothesis"
            },
            "EvaluateHypothesis": {
              "Type": "Task",
              "Resource":"${aws_lambda_function.this["evaluate-hypothesis"].arn}",
              "ResultPath": "$.evaluateHypothesisResult",
              "End": true
            }
          }
        }
      ],
      "Catch": [
        {
          "ErrorEquals": [
            "States.ALL"
          ],
          "ResultPath": "$.error",
          "Next": "FormatError"
        }
      ],
      "ResultPath": "$",
      "Next": "Hypothesis"
    },
    "FormatError": {
      "Type": "Pass",
      "Parameters": {
        "formattedError.$": "States.StringToJson($.error.Cause)"
      },
      "ResultPath": "$",
      "Next": "TestFailed"
    },
    "TestFailed": {
      "Type": "Fail"
    },
    "Hypothesis": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$[0].evaluateHypothesisResult.nextState",
          "StringEquals": "Supported",
          "Next": "Supported"
        },
        {
          "Variable": "$[0].evaluateHypothesisResult.nextState",
          "StringEquals": "NotSupported",
          "Next": "NotSupported"
        }
      ]
    },
    "Supported": {
      "Type": "Succeed"
    },
    "NotSupported": {
      "Type": "Fail"
    }
  }
}
EOF

  tags = local.tags
}

################################################################################
# IAM resources
################################################################################

locals {
  roles_and_trusts = {
    state-machine       = "states"
    steady-state        = "lambda"
    start-experiment    = "lambda"
    continue-execution  = "lambda"
    evaluate-hypothesis = "lambda"
  }
  policy_vars = {
    Partition   = data.aws_partition.current.partition
    Account     = data.aws_caller_identity.current.account_id
    Region      = data.aws_region.current.name
    project_env = var.project_env
  }
}

# Wildcard usage

# Reason: Resource types not allowed for actions
# Applies to:
# steady-state - logs:* , cloudwatch:GetMetricData
# start-experiment - logs:*
# continue-execution - logs:*, states:Send*
# evaluate-hypothesis - logs:*, cloudwatch:GetMetricData

# Reason: FIS experiment template and experiment IDs are unknown at invocation
# Applies to: steady-state, start-experiment, evaluate-hypothesis


resource "aws_iam_role" "this" {
  for_each           = var.create_iam_roles ? local.roles_and_trusts : {}
  name               = "chaos-machine-${data.aws_region.current.name}-${local.policy_vars.project_env}-${each.key}"
  description        = "Customer managed role for use with the Chaos Machine feature."
  assume_role_policy = templatefile("${path.module}/iam/policies/${each.value}.json", local.policy_vars)

  tags = local.tags
}

resource "aws_iam_policy" "this" {
  for_each    = var.create_iam_roles ? local.roles_and_trusts : {}
  name        = "chaos-machine-${data.aws_region.current.name}-${local.policy_vars.project_env}-${each.key}"
  description = "Customer managed policy for use with the Chaos Machine feature."
  policy      = templatefile("${path.module}/iam/policies/${each.key}.json", local.policy_vars)
}

resource "aws_iam_role_policy_attachment" "this" {
  for_each   = var.create_iam_roles ? local.roles_and_trusts : {}
  role       = aws_iam_role.this[each.key].name
  policy_arn = aws_iam_policy.this[each.key].arn
}
