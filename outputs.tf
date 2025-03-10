output "role_arns" {
  value = var.create_iam_roles ? { for k, v in local.roles_and_trusts : k => aws_iam_role.this[k].arn } : null
}
