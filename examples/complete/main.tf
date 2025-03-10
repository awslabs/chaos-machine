provider "aws" {
  region = local.region
}

locals {
  region      = "us-west-2"
  project_env = "dev"
}

module "chaos-machine" {
  source = "/home/ec2-user/repos/chaos-machine"

  create_iam_roles = true
  project_env      = local.project_env

}
