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
import gzip
import json
import base64
import os
import sys
import urllib
from typing import Any, Dict, List, NamedTuple

import boto3
from config import Config, SlackAppConfig, SlackWebhookConfig, get_logger, get_slack_config
from dynamodb import get_thread_ts_from_dynamodb, put_event_to_dynamodb
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

def slack_config_cached():
    global slack_config
    if not slack_config:
        slack_config = get_slack_config()
    return slack_config

def lambda_handler(event, context) -> int:
    # noqa: ANN001
    records = get_cloudtrail_log_records(event)
    try:
        for record in records:
            handle_event(
                event = record["event"],
                source_file_object_key = record['key'],
                rules = cfg.rules,
                ignore_rules = cfg.ignore_rules
            )

    except Exception as e:
        logger.exception({"Failed to process event": e})
        post_message(
            message = message_for_slack_error_notification(e, event),
            account_id = None,
            slack_config = slack_config_cached(),
        )
    return 200



def get_cloudtrail_log_records(event) -> Dict | None:
    records = []
    cw_data = event['awslogs']['data']
    compressed_payload = base64.b64decode(cw_data)
    uncompressed_payload = gzip.decompress(compressed_payload)
    payload = json.loads(uncompressed_payload)

    log_events = payload['logEvents']
    for log_event in log_events:
        records.append(
            {
                'key': payload['logGroup'],
                'accountId': payload['owner'],
                'event': json.loads(log_event['message']),
            }
        )
    return records

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
            if eval(ignore_rule, {}, {"event": flat_event}) is True: # noqa: PGH001
                logger.info({"Event matched ignore rule and will not be processed": {"ignore_rule": ignore_rule, "flat_event": flat_event}}) # noqa: E501
                return ProcessingResult(False, errors)
        except Exception as e:
            logger.exception({"Event parsing failed": {"error": e, "ignore_rule": ignore_rule, "flat_event": flat_event}}) # noqa: E501
            errors.append({"error": e, "rule": ignore_rule})

    for rule in rules:
        try:
            if eval(rule, {}, {"event": flat_event}) is True: # noqa: PGH001
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
    account_id = event["recipientAccountId"] if "recipientAccountId" in event else ""
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
        source_file = source_file_object_key,
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
            logger.info({"Posting message to channel"})
            slack_response = post_message(
                message = message,
                account_id = account_id,
                slack_config = slack_config_cached()
            )
            if slack_response is not None:
                logger.info({"Saving thread_ts to DynamoDB"})
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

# For local testing
if __name__ == "__main__":
    #Before running this script, set environment variables below
    #On top of this file add region to boto3 clients
    #and remove cfg = Config() slack_config = get_slack_config() from top of this file.
    import os
    os.environ["SLACK_BOT_TOKEN"] = ""
    os.environ["DEFAULT_SLACK_CHANNEL_ID"] = ""
    os.environ["SLACK_APP_CONFIGURATION"] = ""

    os.environ["DYNAMODB_TABLE_NAME"] = ""
    os.environ["DYNAMODB_TIME_TO_LIVE"] = ""

    os.environ["HOOK_URL"] = ""
    os.environ["CONFIGURATION"] = ""

    os.environ["RULE_EVALUATION_ERRORS_TO_SLACK"] = ""
    os.environ["RULES_SEPARATOR"] = ","
    os.environ["RULES"] = ""
    os.environ["IGNORE_RULES"] = ""
    os.environ["USE_DEFAULT_RULES"] = ""
    os.environ["EVENTS_TO_TRACK"] = ""
    os.environ["LOG_LEVEL"] = ""
    os.environ["DEFAULT_SNS_TOPIC_ARN"] = ""
    os.environ["SNS_CONFIGURATION"] = '[{""}]'


    cfg = Config()
    slack_config = get_slack_config()

    with open("./tests/test_events.json") as f:
        data = json.load(f)
    for event in data["test_events"]:
        handle_event(event["event"], "file_name", cfg.rules, cfg.ignore_rules)
