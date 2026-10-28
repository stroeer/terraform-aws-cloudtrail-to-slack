import http.client
import json
from datetime import datetime
from typing import Any

from config import SlackAppConfig, SlackWebhookConfig, get_logger
from slack_sdk import WebClient
from slack_sdk.web.slack_response import SlackResponse

logger = get_logger()

# Slack Block Kit limits: section text 3000 chars, section field 2000 chars.
MAX_SECTION_TEXT = 3000
MAX_FIELD_TEXT = 2000


def post_message(
        slack_config: SlackAppConfig | SlackWebhookConfig,
        message: dict,
        account_id: str | None = None,
        thread_ts: str | None = None,
) -> None | SlackResponse:
    if isinstance(slack_config, SlackAppConfig):
        if account_id and slack_config.configuration:
            channel_id = next(
                (cfg["slack_channel_id"] for cfg in slack_config.configuration if account_id in cfg["accounts"]), # noqa: E501
                slack_config.default_channel_id
            )
        else:
            channel_id = slack_config.default_channel_id
        return slack_app_post_message(
            message = message,
            channel_id = channel_id,
            slack_config = slack_config,
            thread_ts = thread_ts,
        )

    if isinstance(slack_config, SlackWebhookConfig):
        if account_id and slack_config.configuration:
            hook_url = next(
                (cfg["slack_hook_url"] for cfg in slack_config.configuration if account_id in cfg["accounts"]), # noqa: E501
                slack_config.default_hook_url
            )
        else:
            hook_url = slack_config.default_hook_url
        webhook_post_message(
            message = message,
            hook_url = hook_url,
        )
    return None


def slack_app_post_message(
        message: dict,
        channel_id: str,
        slack_config: SlackAppConfig,
        thread_ts: str | None = None
) -> SlackResponse:
    client = WebClient(token=slack_config.bot_token)
    return client.chat_postMessage(
        channel = channel_id,
        blocks = message["blocks"],
        thread_ts = thread_ts,
        text = message.get("text", "New message from CloudTrailToSlack"),
        unfurl_links = False,
    )


# Slack web hook example
# https://hooks.slack.com/services/XXXXXXX/XXXXXXX/XXXXXXXXXX
def webhook_post_message(message: dict, hook_url: str) -> int:
    if not hook_url:
        logger.error("No hook URL provided")
        return 200
    logger.info({"Sending message to slack": message})
    headers = {"Content-type": "application/json"}
    connection = http.client.HTTPSConnection("hooks.slack.com")
    connection.request("POST",
                       hook_url.replace("https://hooks.slack.com", ""),
                       json.dumps(message),
                       headers)
    response = connection.getresponse()
    logger.info({"Slack response": {"status": response.status, "message": response.read().decode()}})
    return response.status


def escape(text: Any) -> str:  # noqa: ANN401
    """Escape Slack mrkdwn control chars so event data can't inject links or @channel mentions."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def code_block(value: Any, limit: int) -> str:  # noqa: ANN401
    text = value if isinstance(value, str) else json.dumps(value, indent=2, default=str)
    # a literal ``` inside the payload would close the code block early
    text = escape(text).replace("```", "`\u200b``")
    if len(text) > limit - 6:
        suffix = "\n… (truncated)"
        text = text[: limit - 6 - len(suffix)] + suffix
    return f"```{text}```"


def mrkdwn(text: str) -> dict:
    return {"type": "mrkdwn", "text": text}


def section(text: str) -> dict:
    return {"type": "section", "text": mrkdwn(text)}


def labelled_code_section(label: str, value: Any) -> dict:  # noqa: ANN401
    heading = f"*{label}*\n"
    return section(heading + code_block(value, MAX_SECTION_TEXT - len(heading)))


def describe_actor(user_identity: dict | str) -> tuple[str, str]:
    """Return (short display name, full identifier) for a CloudTrail userIdentity."""
    if not isinstance(user_identity, dict):
        return str(user_identity), str(user_identity)
    arn = user_identity.get("arn")
    if not arn:
        name = user_identity.get("invokedBy") or user_identity.get("principalId") or user_identity.get("type", "unknown")
        return name, name
    if user_identity.get("type") == "Root":
        return "root", arn
    resource = arn.split(":", 5)[-1]
    if resource.startswith("assumed-role/"):
        _, role, *session = resource.split("/")
        return (f"{session[0]} ({role})" if session else role), arn
    return resource.rsplit("/", 1)[-1], arn


def slack_date(event_time: str) -> str:
    """Render the event time in each reader's own timezone, with the raw UTC value as fallback."""
    try:
        epoch = int(datetime.fromisoformat(event_time).timestamp())
    except (TypeError, ValueError):
        return escape(event_time)
    return f"<!date^{epoch}^{{date_short_pretty}} {{time_secs}}|{escape(event_time)}>"


def event_to_slack_message(event: dict, source_file: str, account_id_from_event: str) -> dict[str, Any]:
    event_name = event.get("eventName", "unknown")
    service = event.get("eventSource", "").removesuffix(".amazonaws.com")
    action = f"{service}:{event_name}" if service else event_name
    error_code = event.get("errorCode")
    region = event.get("awsRegion", "")
    event_id = event.get("eventID")
    user_identity = event.get("userIdentity", {})
    actor_name, actor_id = describe_actor(user_identity)
    no_mfa = event_name == "ConsoleLogin" and (event.get("additionalEventData") or {}).get("MFAUsed") != "Yes"
    is_root = isinstance(user_identity, dict) and user_identity.get("type") == "Root"

    if error_code:
        emoji, outcome = ":no_entry:", f" but failed with `{escape(error_code)}`"
    elif is_root or no_mfa:
        emoji, outcome = ":rotating_light:", ""
    else:
        emoji, outcome = ":large_blue_circle:", ""

    blocks = [section(f"{emoji} *{escape(actor_name)}* called *{escape(action)}*{outcome}")]
    if no_mfa:
        blocks.append(section(":warning: *Console login without MFA*"))
    if is_root:
        blocks.append(section(":warning: *Action performed by the root user*"))

    fields = [
        ("Account", f"`{escape(account_id_from_event or 'unknown')}`"),
        ("Region", escape(region or "global")),
        ("Principal", f"`{escape(actor_id)}`"),
        ("Time", slack_date(event.get("eventTime", ""))),
        ("Source IP", escape(event.get("sourceIPAddress", "n/a"))),
        ("User agent", escape(event.get("userAgent", "n/a"))),
    ]
    blocks.append({
        "type": "section",
        "fields": [mrkdwn(f"*{label}*\n{value}"[:MAX_FIELD_TEXT]) for label, value in fields],
    })

    if event.get("errorMessage"):
        blocks.append(labelled_code_section("Error message", event["errorMessage"]))
    # additionalEventData is left out on purpose: mostly TLS/signature noise, MFA is surfaced above.
    for key, label in (("requestParameters", "Request parameters"), ("responseElements", "Response elements")):
        if event.get(key) not in (None, "null", {}):
            blocks.append(labelled_code_section(label, event[key]))

    context = []
    if event_id:
        event_ref = f"`{escape(event_id)}`"
        if region:
            url = f"https://{region}.console.aws.amazon.com/cloudtrailv2/home?region={region}#/events/{event_id}"
            event_ref = f"<{escape(url)}|{escape(event_id)}>"
        context.append(mrkdwn(f"Event ID: {event_ref}"))
    context.append(mrkdwn(f"Source: `{escape(source_file)}`"))
    blocks.append({"type": "context", "elements": context})
    blocks.append({"type": "divider"})

    # Plain-text fallback for push notifications and the channel sidebar.
    text = f"{actor_name} called {action}" + (f" but failed with {error_code}" if error_code else "")
    return {"text": text, "blocks": blocks}


def message_for_slack_error_notification(error: Exception, record: dict) -> dict:
    event = record.get("event", {})
    return {
        "text": "CloudTrail to Slack failed to process an event",
        "blocks": [
            section(":x: *Failed to process CloudTrail event*"),
            labelled_code_section("Error", f"{type(error).__name__}: {error}"),
            {
                "type": "context",
                "elements": [
                    mrkdwn(f"Event: `{escape(event.get('eventName', 'n/a'))}`"),
                    mrkdwn(f"Event ID: `{escape(event.get('eventID', 'n/a'))}`"),
                    mrkdwn(f"Account: `{escape(event.get('recipientAccountId', record.get('accountId', 'n/a')))}`"),
                    mrkdwn(f"Source: `{escape(record.get('key', 'n/a'))}`"),
                ],
            },
        ],
    }


def message_for_rule_evaluation_error_notification(error: Exception, object_key: str, rule: str) -> dict[str, Any]:
    return {
        "text": "CloudTrail to Slack failed to evaluate a rule",
        "blocks": [
            section(":x: *Failed to evaluate rule*"),
            labelled_code_section("Rule", rule),
            labelled_code_section("Error", f"{type(error).__name__}: {error}"),
            {"type": "context", "elements": [mrkdwn(f"Source: `{escape(object_key)}`")]},
        ],
    }
