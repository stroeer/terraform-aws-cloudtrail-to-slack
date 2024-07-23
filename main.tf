locals {
  placeholder = "ACCOUNT_ID"
}
module "lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "4.18.0"

  function_name = var.function_name
  description   = "Send CloudTrail Events to Slack"
  handler       = "main.lambda_handler"
  runtime       = "python3.12"
  timeout       = var.lambda_timeout_seconds
  architectures = ["x86_64"]
  publish       = true

  source_path = [
    {
      path             = "${path.module}/src/"
      pip_requirements = "${path.module}/src/deploy_requirements.txt"
      artifacts_dir    = "${path.root}/builds/"
      patterns = [
        "!.venv/.*",
        "!.vscode/.*",
        "!__pycache__/.*",
        "!tests/.*",
        "!tools/.*",
        "!.pytest_cache/.*",
      ]
    }
  ]

  recreate_missing_package = var.lambda_recreate_missing_package

  environment_variables = merge(
    {
      FUNCTION_NAME = var.function_name

      HOOK_URL = var.default_slack_hook_url

      PARAMETERS_SECRETS_EXTENSION_HTTP_PORT = "2273"

      CONFIG_SSM_PARAMETER_NAME          = aws_ssm_parameter.slack_config.name
      SNS_TOPIC_PATTERN                  = var.sns_topic_pattern != "" ? var.sns_topic_pattern : "arn:aws:sns:${data.aws_region.current.name}:${local.placeholder}:cloudtrail-notifications"
      SLACK_BOT_TOKEN_SSM_PARAMETER_NAME = aws_ssm_parameter.bot_token.name

      CONFIG_HASH = sha1(jsonencode(var.configuration))

      DEFAULT_SLACK_CHANNEL_ID = try(var.default_slack_channel_id, "")
      DEFAULT_SNS_TOPIC_ARN    = try(aws_sns_topic.events_to_sns[0].arn, var.default_sns_topic_arn, "")

      RULES_SEPARATOR                 = var.rules_separator
      RULES                           = var.rules
      IGNORE_RULES                    = var.ignore_rules
      EVENTS_TO_TRACK                 = var.events_to_track
      LOG_LEVEL                       = var.log_level
      RULE_EVALUATION_ERRORS_TO_SLACK = var.rule_evaluation_errors_to_slack

      DYNAMODB_TIME_TO_LIVE = var.dynamodb_time_to_live
      DYNAMODB_TABLE_NAME   = module.cloudtrail_to_slack_dynamodb_table.dynamodb_table_id
    },
    var.use_default_rules ? { USE_DEFAULT_RULES = "True" } : {}
  )
  layers = [
    "arn:aws:lambda:eu-west-1:015030872274:layer:AWS-Parameters-and-Secrets-Lambda-Extension:11"
  ]

  memory_size = var.lambda_memory_size

  cloudwatch_logs_retention_in_days = var.lambda_logs_retention_in_days

  dead_letter_target_arn    = var.dead_letter_target_arn
  attach_dead_letter_policy = var.dead_letter_target_arn != null ? true : false

  tags = var.tags
}


resource "aws_lambda_permission" "cloudwatch_logs" {
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.lambda_function_arn
  principal     = "logs.amazonaws.com"
  source_arn    = "${data.aws_cloudwatch_log_group.logs.arn}:*"
}

resource "aws_cloudwatch_log_subscription_filter" "cloudwatch_logs_to_slack" {
  depends_on = [aws_lambda_permission.cloudwatch_logs]

  name            = "${var.function_name}-subscription-filter"
  log_group_name  = data.aws_cloudwatch_log_group.logs.name
  filter_pattern  = ""
  destination_arn = module.lambda.lambda_function_arn
}

data "aws_partition" "current" {}

resource "aws_iam_role_policy_attachment" "ssm" {
  policy_arn = aws_iam_policy.ssm.arn
  role       = module.lambda.lambda_role_name
}

resource "aws_iam_policy" "ssm" {
  name   = "${var.function_name}-ssm"
  policy = data.aws_iam_policy_document.ssm.json
}

data "aws_iam_policy_document" "ssm" {
  statement {
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.slack_config.arn, aws_ssm_parameter.bot_token.arn]
  }
}

resource "aws_iam_role_policy_attachment" "s3" {
  policy_arn = aws_iam_policy.s3.arn
  role       = module.lambda.lambda_role_name
}

resource "aws_iam_policy" "s3" {
  name   = "${var.function_name}-s3"
  policy = data.aws_iam_policy_document.s3.json
}

data "aws_iam_policy_document" "s3" {
  statement {
    sid = "AllowLambdaToInteractWithDynamoDB"

    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
    ]
    resources = [
      module.cloudtrail_to_slack_dynamodb_table.dynamodb_table_arn
    ]
  }
  dynamic "statement" {
    for_each = length(aws_sns_topic.events_to_sns) > 0 ? [1] : []
    content {
      sid = "AllowLambdaToPushToSNSTopic"

      actions = [
        "sns:Publish",
      ]

      resources = [
        aws_sns_topic.events_to_sns[0].arn,
      ]
    }
  }

  dynamic "statement" {
    for_each = var.default_sns_topic_arn != null ? [1] : []
    content {
      sid = "AllowLambdaToPushToDefaultSNSTopic"

      actions = [
        "sns:Publish",
      ]

      resources = [
        var.default_sns_topic_arn,
      ]
    }
  }
}
