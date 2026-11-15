MANIFEST_HEADER = "MANIFEST"


def build_manifest_text(view_on: bool, timer_on: bool, message_ids) -> str:
    """
    منیفست کانال دیتابیس:
    خط اول: هدر منیفست
    خط دوم: وضعیت ویو چنل
    خط سوم: وضعیت تایمر حذف خودکار
    خطوط بعدی: آیدی مسیج فایل‌ها (هر خط یک آیدی)
    """
    lines = [
        MANIFEST_HEADER,
        f"VIEW: {'on' if view_on else 'off'}",
        f"TIMER: {'on' if timer_on else 'off'}",
    ]

    lines.extend(str(message_id) for message_id in message_ids)

    return "\n".join(lines)


def parse_manifest(text: str):
    """
    منیفست رو پارس می‌کنه و (view_on, timer_on, message_ids) برمی‌گردونه.
    اگه فرمت درست نبود None برمی‌گردونه.
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]

    if not lines or not lines[0].upper().startswith(MANIFEST_HEADER):
        return None

    view_on = timer_on = False
    message_ids = []

    for line in lines[1:]:
        lowered = line.lower()

        if lowered.startswith("view:"):
            view_on = lowered.split(":", 1)[1].strip() == "on"

        elif lowered.startswith("timer:"):
            timer_on = lowered.split(":", 1)[1].strip() == "on"

        elif line.lstrip("-").isdigit():
            message_ids.append(int(line))

    return view_on, timer_on, message_ids
