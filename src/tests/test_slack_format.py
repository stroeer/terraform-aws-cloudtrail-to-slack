from slack_helpers import MAX_SECTION_TEXT, describe_actor, event_to_slack_message

# ruff: noqa: ANN201, E501

EVENT = {
    "eventName": "GetAccelerateConfiguration",
    "eventSource": "s3.amazonaws.com",
    "awsRegion": "eu-west-1",
    "eventTime": "2026-10-24T23:38:11Z",
    "eventID": "742fe730-c6e3-3567-b613-fe9f908f161b",
    "errorCode": "AccessDenied",
    "errorMessage": "Access Denied",
    "userAgent": "<!channel> evil",
    "userIdentity": {
        "type": "AssumedRole",
        "arn": "arn:aws:sts::806599846381:assumed-role/devops-agent-agent-space/monitorAssociationRoleSession",
    },
    "requestParameters": {"bucketName": "x" * 5000},
    "additionalEventData": {"CipherSuite": "TLS_AES_128_GCM_SHA256"},
}


def test_event_message():
    message = event_to_slack_message(EVENT, "aws-controltower/CloudTrailLogs", "806599846381")
    blocks = message["blocks"]
    rendered = str(blocks)

    assert message["text"] == "monitorAssociationRoleSession (devops-agent-agent-space) called s3:GetAccelerateConfiguration but failed with AccessDenied"
    assert blocks[0]["text"]["text"].startswith(":no_entry: *monitorAssociationRoleSession (devops-agent-agent-space)*")
    assert "<!channel>" not in rendered and "&lt;!channel&gt;" in rendered
    assert "CipherSuite" not in rendered
    assert "<!date^1792885091^" in rendered
    for block in blocks:
        if block["type"] == "section" and "text" in block:
            assert len(block["text"]["text"]) <= MAX_SECTION_TEXT
    assert "(truncated)" in rendered


def test_describe_actor():
    assert describe_actor({"type": "Root", "arn": "arn:aws:iam::1:root"}) == ("root", "arn:aws:iam::1:root")
    assert describe_actor({"type": "IAMUser", "arn": "arn:aws:iam::1:user/path/alice"})[0] == "alice"
    assert describe_actor({"type": "AWSService", "invokedBy": "config.amazonaws.com"})[0] == "config.amazonaws.com"
    assert describe_actor("123") == ("123", "123")
