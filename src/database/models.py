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
# Locked (sponsor) channels — users must join before receiving files
# ============================================================

class SponsorChannel(models.Model):
    channel_id = fields.BigIntField(pk=True)
    name = fields.CharField(max_length=256)
    invite_link = fields.CharField(max_length=256)

    class Meta:
        table = "sponsor_channels"

    def __str__(self):
        return self.name


# ============================================================
# Admins — added at runtime via the panel.
# Owners from .env (OWNER_IDS) are always admins and
# are stored only there, never in this table.
# ============================================================

class Admin(models.Model):
    user_id = fields.BigIntField(pk=True)
    name = fields.CharField(max_length=256, null=True)
    added_by = fields.BigIntField(null=True)
    added_at = fields.DatetimeField(auto_now_add=True)
    removed_at = fields.DatetimeField(null=True)
    removed_by = fields.BigIntField(null=True)

    class Meta:
        table = "admins"

    def __str__(self):
        return self.name or str(self.user_id)


# ============================================================
# Admin change log — who added / removed which admin and when
# ============================================================

class AdminLog(models.Model):
    id = fields.IntField(pk=True)
    action = fields.CharField(max_length=10)  # 'add' or 'remove'
    target_user_id = fields.BigIntField()
    target_name = fields.CharField(max_length=256, null=True)
    actor_user_id = fields.BigIntField()
    actor_name = fields.CharField(max_length=256, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "admin_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.target_user_id} by {self.actor_user_id}"


# ============================================================
# View/reaction gate channel — single record with fixed id=1
# ============================================================

class ViewReactionChannel(models.Model):
    id = fields.IntField(pk=True)
    channel_id = fields.BigIntField(null=True)
    name = fields.CharField(max_length=256, null=True)
    invite_link = fields.CharField(max_length=256, null=True)
    enabled = fields.BooleanField(default=False)

    class Meta:
        table = "view_reaction_channels"

    def __str__(self):
        return self.name or str(self.channel_id)
