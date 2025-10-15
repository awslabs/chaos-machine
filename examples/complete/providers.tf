# Copyright 2025, Amazon Web Services, Inc. or its affiliates. All rights reserved. Amazon Confidential and Trademark. This work is licensed under a Creative Commons Attribution 4.0 International License.
terraform {
  required_version = "<=1.12.2"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "<=5.100.0"
    }
  }
}
