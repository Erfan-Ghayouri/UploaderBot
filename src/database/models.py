from tortoise import fields, models


# ============================================================
# Users
# ============================================================

class User(models.Model):
    """
    Stores users who have started the bot.

    Only Telegram user_id is stored.
    """

    user_id = fields.BigIntField(pk=True)

    class Meta:
        table = "users"

    def __str__(self):
        return str(self.user_id)


# ============================================================
# Sponsor Channels
# ============================================================

class SponsorChannel(models.Model):
    """
    Channels that users must join before downloading files.
    Multiple sponsor channels are supported.
    """

    channel_id = fields.BigIntField(pk=True)

    name = fields.CharField(max_length=255)

    invite_link = fields.CharField(max_length=256)

    class Meta:
        table = "sponsor_channels"

    def __str__(self):
        return self.name


# ============================================================
# View / Reaction Channel
# ============================================================

class ViewReactionChannel(models.Model):
    """
    Separate channel for the view/reaction waiting feature.

    Only one record is used:
    id = 1

    Adding another channel replaces the previous channel.
    """

    id = fields.IntField(pk=True)

    channel_id = fields.BigIntField(unique=True)

    name = fields.CharField(max_length=255)

    invite_link = fields.CharField(max_length=256)

    enabled = fields.BooleanField(default=True)

    class Meta:
        table = "view_reaction_channel"

    def __str__(self):
        return self.name