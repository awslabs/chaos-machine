variable "create_chaos_machine" {
  description = "Set to true to create the chaos machine. You might set this to false if your organization requires you to pre-provision IAM resources, which can be created by setting `create_iam_resources = true`."
  type        = bool
  default     = true
}

variable "create_iam_roles" {
  description = "Set to true to create IAM resources. If false, you must provide ARNs for the Lambda and state machine roles."
  type        = bool
  default     = true
}

variable "lambda_environment_variables" {
  description = "Additional environment variables for all Lambda functions. Can be used to set the HTTPS_PROXY and NO_PROXY envs for Lambda functions."
  type        = map(string)
  default     = {}
}

variable "lambda_continue_execution_role_arn" {
  description = "The ARN of the execution role for the continue-execution Lambda function. Required if `create_iam_roles = false`."
  type        = string
  default     = ""
}

variable "lambda_evaluate_hypothesis_role_arn" {
  description = "The ARN of the execution role for the evaluate-hypothesis Lambda function. Required if `create_iam_roles = false`."
  type        = string
  default     = ""
}

variable "lambda_cloudwatch_log_group_retention_in_days" {
  description = "Retention period for the CloudWatch log groups associated with each Lambda function."
  type        = number
  default     = 30
}

variable "lambda_log_level" {
  description = "Log level for the Lambda functions."
  type        = string
  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.lambda_log_level)
    error_message = "Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL."
  }
  default = "INFO"
}

variable "lambda_runtime" {
  description = "The runtime of the Lambda function."
  default     = "python3.11"
}

variable "lambda_security_group_ids" {
  description = "Optional list of security group IDs associated with the Lambda function. Required if attaching functions to a VPC."
  type        = list(string)
  default     = []
}

variable "lambda_start_experiment_role_arn" {
  description = "The ARN of the execution role for the start-experiment Lambda function. Required if `create_iam_roles = false`."
  type        = string
  default     = ""
}

variable "lambda_steady_state_role_arn" {
  description = "The ARN of the execution role for the steady-state Lambda function. Required if `create_iam_roles = false`."
  type        = string
  default     = ""
}

variable "lambda_subnet_ids" {
  description = "Optional list of subnet IDs associated with the Lambda function. Required if attaching functions to a VPC."
  type        = list(string)
  default     = []
}

variable "project_env" {
  description = "Name of the project environment, e.g. dev."
  type        = string
}

variable "state_machine_cloudwatch_log_group_retention_in_days" {
  description = "Retention period for the CloudWatch log group associated with the state machine."
  type        = number
  default     = 30
}

variable "state_machine_log_level" {
  description = "Log level for the state machine."
  type        = string
  validation {
    condition     = contains(["ALL", "ERROR", "FATAL", "OFF"], var.state_machine_log_level)
    error_message = "Valid values: ALL, ERROR, FATAL, OFF."
  }
  default = "ERROR"
}

variable "state_machine_role_arn" {
  description = "The ARN of the execution role for the state machine. Required if `create_iam_roles = false`."
  type        = string
  default     = ""
}
