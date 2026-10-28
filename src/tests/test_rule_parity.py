"""The restricted evaluator must answer exactly like the old eval() (used here only as the oracle) for every rule in real use."""

import json

import pytest
from main import flatten_json
from rule_evaluator import evaluate_rule
from rules import default_rules

# ruff: noqa: ANN201, ANN001, E501, PGH001, S307

# Copied from stroeer/control-tower accounts/root-notifications/cloudtrail.tf
CONTROL_TOWER_IGNORE_RULES = [
    "'anonymous' in event.get('userIdentity.accountId', '') and event.get('eventName', '') in ['GetBucketAcl', 'PutBucketAcl']",
    "'AWSServiceRoleForConfig' in event.get('userIdentity.arn', '')",
    "':assumed-role/WizAccess-Role/aws-go-sdk-' in event.get('userIdentity.arn', '')",
    "'config.amazonaws.com' in event.get('userIdentity.invokedBy', '')",
    "'ConfigRecorderRole' in event.get('requestParameters.roleArn', '')",
    "'DatadogAWSIntegrationRole' in event.get('userIdentity.arn', '')",
    "'aft-invoke-customizations-execution-' in event.get('userIdentity.arn', '')",
    "'GetBucketLocation' in event.get('eventName', '')",
    "'.amazonaws.com' in event.get('eventSource', '') and ('List' in event.get('eventName', '') or 'Describe' in event.get('eventName', '') or 'GetApis' in event.get('eventName', '') or 'GetRestApis' in event.get('eventName', ''))",
    "'AccountColor' in event.get('eventName', '')",
]
CONTROL_TOWER_RULES = [
    f"'{s}' in str(event).lower() and not 'AWSServiceRoleForECS' in event.get('userIdentity.arn', '') and not 'Get' in event.get('eventName', '') and not 'List' in event.get('eventName', '') and not 'UpdateService' in event.get('eventName', '')"
    for s in ["acl-094659d63f17084ea", "subnet-0894a94895f170364"]
]
EVENTS_TO_TRACK_RULE = f'"eventName" in event and event["eventName"] in {json.dumps(["CreateUser", "DeleteUser", "CreateAccessKey"])}'

ALL_RULES = CONTROL_TOWER_IGNORE_RULES + CONTROL_TOWER_RULES + [EVENTS_TO_TRACK_RULE] + default_rules

with open("tests/test_events.json") as f:
    EVENTS = [e["event"] for e in json.load(f)["test_events"]]

EVENTS += [
    {"eventName": "GetBucketAcl", "eventSource": "s3.amazonaws.com", "userIdentity": {"accountId": "anonymous"}},
    {"eventName": "AssumeRole", "userIdentity": {"arn": "arn:aws:sts::1:assumed-role/WizAccess-Role/aws-go-sdk-123"}},
    {"eventName": "PutConfigRule", "userIdentity": {"invokedBy": "config.amazonaws.com"}},
    {"eventName": "ReplaceNetworkAclEntry", "requestParameters": {"networkAclId": "ACL-094659D63F17084EA"}, "userIdentity": {"arn": "arn:aws:iam::1:user/bob"}},
    {"eventName": "DescribeSubnets", "eventSource": "ec2.amazonaws.com", "requestParameters": {"subnetSet": {"items": [{"subnetId": "subnet-0894a94895f170364"}]}}},
    {"eventName": "CreateUser", "eventSource": "iam.amazonaws.com", "userIdentity": {"type": "Root"}},
    {"eventName": "GetAccountColor", "errorCode": "AccessDenied", "userIdentity": {"accountId": "1"}},
    {"eventName": "AttachUserPolicy", "requestParameters": {"policyArn": "arn:aws:iam::aws:policy/AdministratorAccess"}},
    {"eventName": "ConsoleLogin", "additionalEventData": {"MFAUsed": "No"}, "userIdentity": {"arn": "arn:aws:iam::1:user/x"}},
    {"userIdentity": "123", "eventName": "empty_event", "eventSource": "imagination"},
    {"eventName": "Weird", "responseElements": {"functionName": None, "count": 3, "flag": True}},
    {},
]


def outcome(fn):
    try:
        return fn()
    except Exception as e:
        return type(e).__name__


@pytest.mark.parametrize("rule", ALL_RULES)
def test_evaluator_matches_eval(rule):
    for event in EVENTS:
        flat = {k: v for k, v in flatten_json(event).items() if v is not None}
        expected = outcome(lambda: eval(rule, {}, {"event": flat}))  # noqa: B023
        actual = outcome(lambda: evaluate_rule(rule, flat))  # noqa: B023
        assert actual == expected, f"{rule!r} on {flat!r}"
