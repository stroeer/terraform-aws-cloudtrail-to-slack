import json
from typing import Any

import config
from config import get_logger
import os
from dateutil.parser import parse as parse_date

logger = get_logger()


def send_message_to_sns(
    event: dict,
    source_file: str,
    account_id: str | None,
    cfg: config.Config,
    sns_client # noqa: ANN001
)-> None:
    if pattern := cfg.sns_topic_pattern:
        logger.info("Sending message to SNS.")
        attributes = {}
        for key, value in event.items():
            if isinstance(value, str):
                attributes[key] = {'DataType': 'String', 'StringValue': str(value)}
        message = json.dumps(event)

        logger.debug(f"SNS Message: {message}")
        topic_arn = pattern.replace("ACCOUNT_ID", account_id)
        logger.debug(f"Topic ARN: {topic_arn}")
        try:
            return sns_client.publish(
                TargetArn=topic_arn,
                Message=json.dumps(event),
                MessageAttributes=attributes
            )['ResponseMetadata']['HTTPStatusCode']
        except Exception as e:
            logger.info(f"Topic {topic_arn}: {e}")
            if "NotFound" in str(e) or "AuthorizationError" in str(e):
                return 200
            return 500
