# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import base64
import gzip
import json
from typing import Any, Dict, List, NamedTuple

import boto3
from config import Config, SlackAppConfig, SlackWebhookConfig, get_logger, get_slack_config
from dynamodb import get_thread_ts_from_dynamodb, put_event_to_dynamodb
from rule_evaluator import evaluate_rule
from slack_helpers import (
    event_to_slack_message,
    message_for_rule_evaluation_error_notification,
    message_for_slack_error_notification,
    post_message,
)
from slack_sdk.web.slack_response import SlackResponse
from sns import send_message_to_sns

cfg = Config()
logger = get_logger()
slack_config = {}

s3_client = boto3.client("s3")
dynamodb_client = boto3.client("dynamodb")
sns_client = boto3.client("sns")


def slack_config_cached():  # noqa: ANN201
    global slack_config  # noqa: PLW0603
    if not slack_config:
        slack_config = get_slack_config()
    return slack_config


def lambda_handler(event, context) -> int:  # noqa: ANN001, ARG001
    records = get_cloudtrail_log_records(event)
    # One failing record must not swallow the alerts for the rest of the batch.
    for record in records:
        try:
            handle_event(
                event = record["event"],
                source_file_object_key = record["key"],
                rules = cfg.rules,
                ignore_rules = cfg.ignore_rules,
            )
        except Exception as e:
            logger.exception({"Failed to process event": str(e)})
            post_message(
                message = message_for_slack_error_notification(e, record),
                account_id = None,
                slack_config = slack_config_cached(),
            )
    return 200


def get_cloudtrail_log_records(event: dict) -> List[Dict[str, Any]]:
    payload = json.loads(gzip.decompress(base64.b64decode(event["awslogs"]["data"])))
    return [
        {
            "key": payload["logGroup"],
            "accountId": payload["owner"],
            "event": json.loads(log_event["message"]),
        }
        for log_event in payload["logEvents"]
    ]


class ProcessingResult(NamedTuple):
    should_be_processed: bool
    errors: List[Dict[str, Any]]


def should_message_be_processed(
    event: Dict[str, Any],
    rules: List[str],
    ignore_rules: List[str],
) -> ProcessingResult:
    flat_event = flatten_json(event)
    flat_event = {k: v for k, v in flat_event.items() if v is not None}
    logger.debug({"Rules:": rules, "ignore_rules": ignore_rules})
    logger.debug({"Flattened event": flat_event})

    errors = []
    for ignore_rule in ignore_rules:
        try:
            if evaluate_rule(ignore_rule, flat_event) is True:
                logger.info({"Event matched ignore rule and will not be processed": {"ignore_rule": ignore_rule, "flat_event": flat_event}}) # noqa: E501
                return ProcessingResult(False, errors)
        except Exception as e:
            logger.exception({"Event parsing failed": {"error": e, "ignore_rule": ignore_rule, "flat_event": flat_event}}) # noqa: E501
            errors.append({"error": e, "rule": ignore_rule})

    for rule in rules:
        try:
            if evaluate_rule(rule, flat_event) is True:
                logger.info({"Event matched rule and will be processed": {"rule": rule, "flat_event": flat_event}}) # noqa: E501
                return ProcessingResult(True, errors)
        except Exception as e:
            logger.exception({"Event parsing failed": {"error": e, "rule": rule, "flat_event": flat_event}})
            errors.append({"error": e, "rule": rule})

    logger.info({"Event did not match any rules and will not be processed": {"event": flat_event}}) # noqa: E501
    return ProcessingResult(False, errors)


def handle_event(
    event: Dict[str, Any],
    source_file_object_key: str,
    rules: List[str],
    ignore_rules: List[str],
) -> SlackResponse | None:

    result = should_message_be_processed(event, rules, ignore_rules)
    account_id = event.get("recipientAccountId", "")
    if cfg.rule_evaluation_errors_to_slack:
        for error in result.errors:
            post_message(
                message = message_for_rule_evaluation_error_notification(
                error = error["error"],
                object_key = source_file_object_key,
                rule = error["rule"],
                ),
                account_id = account_id,
                slack_config = slack_config_cached(),
            )

    if not result.should_be_processed:
        return

    # log full event if it is AccessDenied
    if ("errorCode" in event and "AccessDenied" in event["errorCode"]):
        event_as_string = json.dumps(event, indent=4)
        logger.info({"errorCode": "AccessDenied", "log full event": event_as_string})

    message = event_to_slack_message(event, source_file_object_key, account_id)

    send_message_to_sns(
        event = event,
        account_id = account_id,
        cfg = cfg,
        sns_client = sns_client,
    )

    if isinstance(slack_config_cached(), SlackWebhookConfig):
        return post_message(
            message = message,
            account_id = account_id,
            slack_config = slack_config_cached(),
        )

    if isinstance(slack_config_cached(), SlackAppConfig):
        thread_ts = get_thread_ts_from_dynamodb(
            cfg = cfg,
            event = event,
            dynamodb_client=dynamodb_client,
        )
        if thread_ts is not None:
            # If we have a thread_ts, we can post the message to the thread
            logger.info({"Posting message to thread": {"thread_ts": thread_ts}})
            return post_message(
                message = message,
                account_id = account_id,
                thread_ts = thread_ts,
                slack_config = slack_config_cached(),
            )
        else:
            # If we don't have a thread_ts, we need to post the message to the channel
            logger.info("Posting message to channel")
            slack_response = post_message(
                message = message,
                account_id = account_id,
                slack_config = slack_config_cached()
            )
            if slack_response is not None:
                logger.info("Saving thread_ts to DynamoDB")
                thread_ts = slack_response.get("ts")
                if thread_ts is not None:
                    put_event_to_dynamodb(
                        cfg = cfg,
                        event = event,
                        thread_ts = thread_ts,
                        dynamodb_client=dynamodb_client,
                    )



# Flatten json
def flatten_json(y: dict) -> dict:
    out = {}

    def flatten(x, name=""): # noqa: ANN001, ANN202
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + ".")
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + ".")
                i += 1
        else:
            out[name[:-1]] = x

    flatten(y)
    return out
