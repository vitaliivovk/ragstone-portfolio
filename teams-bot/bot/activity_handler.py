"""Parse and handle Teams Bot Framework activities."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TeamsActivity:
    """Parsed Teams activity with relevant fields for processing."""
    activity_id: str
    conversation_id: str
    service_url: str
    message_text: str
    user_id: str
    user_name: str
    channel_id: str
    is_group_chat: bool
    reply_to_id: Optional[str] = None
    
    # Original activity data for reference
    raw_activity: Optional[dict] = field(default=None)


def parse_teams_activity(body: dict) -> Optional[TeamsActivity]:
    """
    Parse a Bot Framework activity from Teams.
    
    Args:
        body: The raw activity JSON from the webhook
        
    Returns:
        TeamsActivity if it's a message activity, None otherwise
    """
    activity_type = body.get("type", "")
    
    # Only process message activities
    if activity_type != "message":
        return None
    
    # Get message text
    message_text = body.get("text", "")
    if not message_text:
        return None
    
    # Remove bot mentions from message (Teams includes @mention)
    entities = body.get("entities", [])
    recipient = body.get("recipient", {})
    bot_id = recipient.get("id", "")
    
    for entity in entities:
        if entity.get("type") == "mention":
            mentioned = entity.get("mentioned", {})
            if mentioned.get("id") == bot_id:
                mention_text = entity.get("text", "")
                message_text = message_text.replace(mention_text, "").strip()
    
    # Determine if this is a group chat
    conversation = body.get("conversation", {})
    conversation_type = conversation.get("conversationType", "personal")
    is_group_chat = conversation_type in ("groupChat", "channel")
    
    # Extract user info
    from_user = body.get("from", {})
    
    return TeamsActivity(
        activity_id=body.get("id", ""),
        conversation_id=conversation.get("id", ""),
        service_url=body.get("serviceUrl", ""),
        message_text=message_text,
        user_id=from_user.get("id", ""),
        user_name=from_user.get("name", "User"),
        channel_id=body.get("channelId", "msteams"),
        is_group_chat=is_group_chat,
        reply_to_id=body.get("replyToId"),
        raw_activity=body,
    )


def build_reply_activity(activity: TeamsActivity, text: str) -> dict:
    """
    Build a reply activity for a simple text response.
    
    Args:
        activity: The original activity to reply to
        text: The response text
        
    Returns:
        Activity dict ready to send
    """
    return {
        "type": "message",
        "text": text,
        "textFormat": "markdown",
        "from": activity.raw_activity.get("recipient"),
        "recipient": activity.raw_activity.get("from"),
        "conversation": activity.raw_activity.get("conversation"),
        "replyToId": activity.activity_id,
    }
