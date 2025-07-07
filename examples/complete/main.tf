locals {
  region      = "us-east-1"
  project_env = "dev"
}

provider "aws" {
  region = local.region
}

module "chaos-machine" {
  source = "/home/ec2-user/repos/chaos-machine"

  create_iam_roles = true
  project_env      = local.project_env

}
