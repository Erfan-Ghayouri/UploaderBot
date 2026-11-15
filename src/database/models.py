from tortoise import fields, models


class User(models.Model):
    user_id = fields.BigIntField(pk=True)

    class Meta:
        table = "users"


class Setting(models.Model):
    key = fields.CharField(max_length=64, pk=True)
    value = fields.CharField(max_length=512, null=True)

    class Meta:
        table = "settings"


class SponsorChannel(models.Model):
    id = fields.IntField(pk=True)
    channel_name = fields.CharField(max_length=256)
    channel_username = fields.CharField(max_length=64, null=True)
    invite_link = fields.CharField(max_length=256)

    class Meta:
        table = "sponsor_channels"
