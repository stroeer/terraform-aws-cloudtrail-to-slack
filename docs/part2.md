## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 0.13.1 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | >= 4.8 |
| <a name="requirement_external"></a> [external](#requirement\_external) | >= 1.0 |
| <a name="requirement_local"></a> [local](#requirement\_local) | >= 1.0 |
| <a name="requirement_null"></a> [null](#requirement\_null) | >= 2.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | >= 4.8 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_cloudtrail_to_slack_dynamodb_table"></a> [cloudtrail\_to\_slack\_dynamodb\_table](#module\_cloudtrail\_to\_slack\_dynamodb\_table) | terraform-aws-modules/dynamodb-table/aws | 4.0.1 |
| <a name="module_lambda"></a> [lambda](#module\_lambda) | terraform-aws-modules/lambda/aws | 4.18.0 |

## Resources

| Name | Type |
|------|------|
| [aws_cloudwatch_log_subscription_filter.cloudwatch_logs_to_slack](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_subscription_filter) | resource |
| [aws_iam_policy.s3](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_policy.ssm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_role_policy_attachment.s3](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_role_policy_attachment.ssm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_lambda_permission.cloudwatch_logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_permission) | resource |
| [aws_sns_topic.events_to_sns](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic) | resource |
| [aws_sns_topic_subscription.events_to_sns](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic_subscription) | resource |
| [aws_ssm_parameter.bot_token](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.slack_config](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_parameter) | resource |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |
| [aws_cloudwatch_log_group.logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/cloudwatch_log_group) | data source |
| [aws_iam_policy_document.s3](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.ssm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_partition.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/partition) | data source |
| [aws_region.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/region) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_aws_sns_topic_subscriptions"></a> [aws\_sns\_topic\_subscriptions](#input\_aws\_sns\_topic\_subscriptions) | Map of endpoints to protocols for SNS topic subscriptions. If not set, sns notifications will not be sent. | `map(string)` | `{}` | no |
| <a name="input_cloudtrail_cw_log_group"></a> [cloudtrail\_cw\_log\_group](#input\_cloudtrail\_cw\_log\_group) | Name of the CloudWatch log group that contains CloudTrail events | `string` | n/a | yes |
| <a name="input_cloudtrail_logs_kms_key_id"></a> [cloudtrail\_logs\_kms\_key\_id](#input\_cloudtrail\_logs\_kms\_key\_id) | Alias, key id or key arn of the KMS Key that used for CloudTrail events | `string` | `""` | no |
| <a name="input_configuration"></a> [configuration](#input\_configuration) | Allows the configuration of the Slack webhook URL per account(s). This enables the separation of events from different accounts into different channels, which is useful in the context of an AWS organization. | <pre>list(object({<br/>    accounts         = list(string)<br/>    slack_channel_id = string<br/>  }))</pre> | `null` | no |
| <a name="input_dead_letter_target_arn"></a> [dead\_letter\_target\_arn](#input\_dead\_letter\_target\_arn) | The ARN of an SNS topic or SQS queue to notify when an invocation fails. | `string` | `null` | no |
| <a name="input_default_slack_channel_id"></a> [default\_slack\_channel\_id](#input\_default\_slack\_channel\_id) | The Slack channel ID to be used if the AWS account ID does not match any account ID in the configuration variable. | `string` | `null` | no |
| <a name="input_default_slack_hook_url"></a> [default\_slack\_hook\_url](#input\_default\_slack\_hook\_url) | The Slack incoming webhook URL to be used if the AWS account ID does not match any account ID in the configuration variable. | `string` | `null` | no |
| <a name="input_default_sns_topic_arn"></a> [default\_sns\_topic\_arn](#input\_default\_sns\_topic\_arn) | Default topic for all notifications. If not set, sns notifications will not be sent. | `string` | `null` | no |
| <a name="input_dynamodb_time_to_live"></a> [dynamodb\_time\_to\_live](#input\_dynamodb\_time\_to\_live) | How long to keep cloudtrail events in dynamodb table, for collecting similar events in thread of one message | `number` | `900` | no |
| <a name="input_events_to_track"></a> [events\_to\_track](#input\_events\_to\_track) | Comma-separated list events to track and report | `string` | `""` | no |
| <a name="input_function_name"></a> [function\_name](#input\_function\_name) | Lambda function name | `string` | `"fivexl-cloudtrail-to-slack"` | no |
| <a name="input_ignore_rules"></a> [ignore\_rules](#input\_ignore\_rules) | Comma-separated list of rules to ignore events if you need to suppress something. Will be applied before rules and default\_rules | `string` | `""` | no |
| <a name="input_lambda_logs_retention_in_days"></a> [lambda\_logs\_retention\_in\_days](#input\_lambda\_logs\_retention\_in\_days) | Controls for how long to keep lambda logs. | `number` | `30` | no |
| <a name="input_lambda_memory_size"></a> [lambda\_memory\_size](#input\_lambda\_memory\_size) | Amount of memory in MB your Lambda Function can use at runtime. Valid value between 128 MB to 10,240 MB (10 GB), in 64 MB increments. | `number` | `256` | no |
| <a name="input_lambda_recreate_missing_package"></a> [lambda\_recreate\_missing\_package](#input\_lambda\_recreate\_missing\_package) | Description: Whether to recreate missing Lambda package if it is missing locally or not | `bool` | `true` | no |
| <a name="input_lambda_timeout_seconds"></a> [lambda\_timeout\_seconds](#input\_lambda\_timeout\_seconds) | Controls lambda timeout setting. | `number` | `60` | no |
| <a name="input_log_level"></a> [log\_level](#input\_log\_level) | Log level for lambda function | `string` | `"INFO"` | no |
| <a name="input_rule_evaluation_errors_to_slack"></a> [rule\_evaluation\_errors\_to\_slack](#input\_rule\_evaluation\_errors\_to\_slack) | If rule evaluation error occurs, send notification to slack | `bool` | `true` | no |
| <a name="input_rules"></a> [rules](#input\_rules) | Comma-separated list of rules to track events if just event name is not enough | `string` | `""` | no |
| <a name="input_rules_separator"></a> [rules\_separator](#input\_rules\_separator) | Custom rules separator. Can be used if there are commas in the rules | `string` | `","` | no |
| <a name="input_sns_configuration"></a> [sns\_configuration](#input\_sns\_configuration) | Allows the configuration of the SNS topic per account(s). | <pre>list(object({<br/>    accounts      = list(string)<br/>    sns_topic_arn = string<br/>  }))</pre> | `null` | no |
| <a name="input_sns_topic_pattern"></a> [sns\_topic\_pattern](#input\_sns\_topic\_pattern) | SNS topic pattern with 'ACCOUNT\_ID' as a account id placeholder | `any` | `null` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags to attach to resources | `map(string)` | `{}` | no |
| <a name="input_use_default_rules"></a> [use\_default\_rules](#input\_use\_default\_rules) | Should default rules be used | `bool` | `true` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_lambda_function_arn"></a> [lambda\_function\_arn](#output\_lambda\_function\_arn) | The ARN of the Lambda Function |
| <a name="output_lambda_function_name"></a> [lambda\_function\_name](#output\_lambda\_function\_name) | The Name of the Lambda Function |
| <a name="output_lambda_function_role_arn"></a> [lambda\_function\_role\_arn](#output\_lambda\_function\_role\_arn) | The ARN of the Lambda Function Role |
