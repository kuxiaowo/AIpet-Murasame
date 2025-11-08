from datetime import datetime


WEEKDAY_CN = [
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
    "星期日",
]


def get_time_segment_cn(dt: datetime | None = None) -> str:
    """Return coarse time-of-day segment in Chinese.

    Segments:
    - 05:00–07:59 -> 早上
    - 08:00–11:59 -> 上午
    - 12:00–12:59 -> 中午
    - 13:00–16:59 -> 下午
    - 17:00–18:59 -> 傍晚
    - 19:00–22:59 -> 晚上
    - 23:00–04:59 -> 深夜
    """
    dt = dt or datetime.now()
    h = dt.hour
    m = dt.minute
    hm = h * 60 + m

    if 5 * 60 <= hm <= 7 * 60 + 59:
        return "早上"
    if 8 * 60 <= hm <= 11 * 60 + 59:
        return "上午"
    if 12 * 60 <= hm <= 12 * 60 + 59:
        return "中午"
    if 13 * 60 <= hm <= 16 * 60 + 59:
        return "下午"
    if 17 * 60 <= hm <= 18 * 60 + 59:
        return "傍晚"
    if 19 * 60 <= hm <= 22 * 60 + 59:
        return "晚上"
    return "深夜"


def get_weekday_cn(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    # Python weekday(): Monday=0, Sunday=6; map to CN list above
    idx = dt.weekday()
    # Convert Sunday (6) to 星期日
    return WEEKDAY_CN[idx]


def get_date_with_weekday_cn(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日（{get_weekday_cn(dt)}）"


def build_time_context() -> str:
    """Build a short context string about current date and time segment."""
    return f"当前日期：{get_date_with_weekday_cn()}；当前时间段：{get_time_segment_cn()}。"

