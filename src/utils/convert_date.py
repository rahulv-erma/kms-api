import datetime


def convert_date(unix_time):
    timestamp_milliseconds = unix_time

    timestamp_seconds = timestamp_milliseconds / 1000
    date_object = datetime.datetime.fromtimestamp(timestamp_seconds)

    formatted_date = date_object.strftime('%Y-%m-%d')

    return formatted_date
