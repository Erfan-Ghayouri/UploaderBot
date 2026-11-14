from tortoise import fields, models


class User(models.Model):
    user_id = fields.BigIntField(pk=True)

    class Meta:
        table = "users"


class SponsorChannel(models.Model):
    channel_id = fields.BigIntField(pk=True)
    channel_name = fields.CharField(max_length=256, null=True)
    invite_link = fields.CharField(max_length=256)

    class Meta:
        table = "sponsor_channels"