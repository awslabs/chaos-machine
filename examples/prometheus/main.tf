provider "aws" {
  region = local.region
}

locals {
  region      = "us-east-1"
  project_env = "dev"
}

module "chaos-machine" {
  source = "/home/ec2-user/repos/pegasus/chaos-machine"

  create_iam_roles = true
  project_env      = local.project_env

  lambda_subnet_ids         = ["subnet-0e02e8e644a87860f", "subnet-03c52ce0deb15fc10"]
  lambda_security_group_ids = ["sg-0f12f45b95c62a064"]
}
