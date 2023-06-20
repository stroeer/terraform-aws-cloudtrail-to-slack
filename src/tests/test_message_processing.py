import pytest
from main import should_message_be_processed
import json
from rules import default_rules
# ruff: noqa: ANN201, ANN001, E501


# Tests can be run by : pytest src/tests/test_message_processing.py -v

with open("src/tests/test_events.json") as f:
    data = json.load(f)


@pytest.fixture(
    params = data["test_events"],
    ids = [event["test_event_name"] for event in data["test_events"]]
)
def message_should_be_processed_test_cases(request):
    return request.param


@pytest.fixture(
    params = [
        {
            "in": {
                "event":{
                    "userIdentity": "123",
                    "eventName": "empty_event",
                    "eventSource": "imagination"
                },
            },
            "out": {
                "result": False,
            },
        },
    ],
    ids = ["empty_event"],
)
def message_should_not_be_processed_test_cases(request):
    return request.param


@pytest.fixture(
    params = [
        {
            "in": {
                "incorrect_rule": "incorrect_rule",
                "event":{
                    "eventVersion": "1.05",
                    "userIdentity": {
                        "type": "IAMUser",
                        "principalId": "XXXXXXXXXXX",
                        "arn": "arn:aws:iam::XXXXXXXXXXX:user/xxxxxxxx",
                        "accountId": "XXXXXXXXXXX",
                        "userName": "xxxxxxxx"
                    },
                    "eventTime": "2019-07-03T16:14:51Z",
                    "eventSource": "signin.amazonaws.com",
                    "eventName": "ConsoleLogin",
                    "awsRegion": "us-east-1",
                    "sourceIPAddress": "83.41.208.104",
                    "userAgent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0",
                    "requestParameters": "null",
                    "responseElements": {
                        "ConsoleLogin": "Success"
                    },
                    "additionalEventData": {
                        "LoginTo": "https://console.aws.amazon.com/ec2/v2/home?XXXXXXXXXXX",
                        "MobileVersion": "No",
                        "MFAUsed": "No"
                    },
                    "eventID": "0e4d136e-25d4-4d92-b2b2-8a9fe1e3f1af",
                    "eventType": "AwsConsoleSignIn",
                    "recipientAccountId": "XXXXXXXXXXX"
                },
            },
            "out": {
                "result": True,
            },
        },
    ],
    ids= ["incorrect_rule"],
)
def message_should_not_be_processed_with_incorrect_rule_test_case(request):
    return request.param



def test_message_should_be_processed(message_should_be_processed_test_cases) -> None:
    assert should_message_be_processed(
        event = message_should_be_processed_test_cases["event"],
        rules = default_rules,
        ignore_rules = []
        ) == True # noqa: E712


def test_message_should_not_be_processed(message_should_not_be_processed_test_cases) -> None:
    assert should_message_be_processed(
        event = message_should_not_be_processed_test_cases["in"]["event"],
        rules = default_rules,
        ignore_rules = []
        ) is message_should_not_be_processed_test_cases["out"]["result"]


def test_message_should_not_be_processed_with_rules_as_ignor_rules(message_should_be_processed_test_cases) -> None:
    assert should_message_be_processed(
        event = message_should_be_processed_test_cases["event"],
        rules = default_rules,
        ignore_rules = default_rules
        ) is False


def test_should_message_be_processed_with_ParsingEventError_handling(message_should_not_be_processed_with_incorrect_rule_test_case) -> None:
    almost_default_rules = default_rules.copy()
    almost_default_rules.insert(0, message_should_not_be_processed_with_incorrect_rule_test_case["in"]["incorrect_rule"])
    assert should_message_be_processed(
            event = message_should_not_be_processed_with_incorrect_rule_test_case["in"]["event"],
            rules = almost_default_rules, # type: ignore # noqa:
            ignore_rules = [],
        ) is message_should_not_be_processed_with_incorrect_rule_test_case["out"]["result"]
