import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Dict, List, Union

import urllib3
from rules import default_rules


@dataclass
class SlackWebhookConfig:
    default_hook_url: str | None
    configuration: List[Dict]


@dataclass
class SlackAppConfig:
    bot_token: str
    default_channel_id: str
    configuration: List[Dict]

http_client = urllib3.PoolManager()

# Reads from the AWS Parameters and Secrets Lambda Extension cache.
def retrieve_extension_value(url: str) -> dict:
    port = os.environ["PARAMETERS_SECRETS_EXTENSION_HTTP_PORT"]
    url = ("http://localhost:" + port + url)
    headers = { "X-Aws-Parameters-Secrets-Token": os.environ.get("AWS_SESSION_TOKEN") }
    response = http_client.request("GET", url, headers=headers)
    response = json.loads(response.data)
    return response


def get_slack_config() -> Union[SlackWebhookConfig, SlackAppConfig]:
    config_parameter = os.environ.get("CONFIG_SSM_PARAMETER_NAME", "None")
    token_parameter = os.environ.get("SLACK_BOT_TOKEN_SSM_PARAMETER_NAME", "None")
    raw_configuration = retrieve_extension_value(f"/systemsmanager/parameters/get/?name={config_parameter}")["Parameter"]["Value"]
    bot_token = retrieve_extension_value(
        f"/systemsmanager/parameters/get/?withDecryption=true&name={token_parameter}"
    )["Parameter"]["Value"]

    if bot_token:

        default_channel_id: str | None = os.environ.get("DEFAULT_SLACK_CHANNEL_ID")
        configuration: List[Dict] = json.loads(raw_configuration) if raw_configuration else []

        return SlackAppConfig(
            bot_token = bot_token,
            default_channel_id = default_channel_id,
            configuration = configuration,
        )
    else:
        raise Exception("Slack bot token SSM parameter is empty.")


class Config:
    def __init__(self): # noqa: ANN101 ANN204

        self.default_sns_topic_arn: str | None = os.environ.get("DEFAULT_SNS_TOPIC_ARN")
        self.sns_topic_pattern: str | None = os.environ.get("SNS_TOPIC_PATTERN")

        self.rule_evaluation_errors_to_slack: bool = self.get_bool_from_env_var("RULE_EVALUATION_ERRORS_TO_SLACK")
        self.rules_separator: str = os.environ.get("RULES_SEPARATOR", ",")
        self.user_rules: List[str] = self.parse_rules_from_string(os.environ.get("RULES"), self.rules_separator) # noqa: E501
        self.ignore_rules: List[str] = self.parse_rules_from_string(os.environ.get("IGNORE_RULES"), self.rules_separator) # noqa: E501
        self.use_default_rules: bool = self.get_bool_from_env_var("USE_DEFAULT_RULES")
        self.events_to_track: str | None = os.environ.get("EVENTS_TO_TRACK")

        self.dynamodb_table_name: str | None = os.environ.get("DYNAMODB_TABLE_NAME")
        self.dynamodb_time_to_live: int = int(os.environ.get("DYNAMODB_TIME_TO_LIVE", "900"))

        self.rules = []
        if self.use_default_rules:
            self.rules += default_rules
        if self.user_rules:
            self.rules += self.user_rules
        if self.events_to_track:
            events_list = self.events_to_track.replace(" ", "").split(",")
            self.rules.append(f'"eventName" in event and event["eventName"] in {json.dumps(events_list)}')
        if not self.rules:
            raise Exception("Have no rules to apply! Check configuration - add some, or enable default.")

    @staticmethod
    def parse_rules_from_string(rules_as_string: str | None, rules_separator: str) -> List[str]:
        if not rules_as_string:
            return []
        rules_as_list = rules_as_string.split(rules_separator)
        # make sure there are no empty strings in the list
        return [x for x in rules_as_list if x]

    # Terraform renders bools as "true"/"false", and "false" is truthy as a plain string.
    @staticmethod
    def get_bool_from_env_var(env_var_name: str) -> bool:
        return os.environ.get(env_var_name, "").lower() in ["true", "1"]



class JsonFormatter(logging.Formatter):
    def format(self, record): # noqa: ANN001, ANN201, ANN101
        log_entry = {
            "level": record.levelname,
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

        if isinstance(record.msg, dict):
            log_entry.update(record.msg)
        else:
            log_entry["message"] = record.getMessage()
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # default=str keeps exceptions and other non-JSON values from breaking the log line
        return json.dumps(log_entry, default=str)

def get_logger(name: str ="main") -> logging.Logger:
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    log_level = logging.getLevelName(log_level)

    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.handlers = [] # Remove the default lambda logger
    root_logger.setLevel(log_level)

    logger = logging.getLogger(name)
    if not logger.handlers:  # Check if the logger already has handlers
        handler = logging.StreamHandler()
        formatter = JsonFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(log_level)

    return logger
