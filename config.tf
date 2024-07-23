resource "aws_ssm_parameter" "slack_config" {
  name  = "/internal/lambda/${var.function_name}/slack-config"
  type  = "String"
  value = jsonencode(var.configuration)
}

resource "aws_ssm_parameter" "bot_token" {
  name  = "/internal/lambda/${var.function_name}/slack-bot-token"
  type  = "SecureString"
  value = "<placeholder>"
  lifecycle {
    ignore_changes = [value]
  }
}
