module "cloudtrail_to_slack_dynamodb_table" {
  source  = "terraform-aws-modules/dynamodb-table/aws"
  version = "4.0.1"
  name    = "${var.function_name}-table"

  deletion_protection_enabled    = true
  server_side_encryption_enabled = true
  point_in_time_recovery_enabled = true

  hash_key           = "principal_structure_and_action_hash"
  ttl_attribute_name = "ttl"
  ttl_enabled        = true

  attributes = [
    {
      name = "principal_structure_and_action_hash"
      type = "S"
    },
  ]
  tags = var.tags
}
