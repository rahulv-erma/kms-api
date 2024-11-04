import datetime


def create_schedule(frequency: dict, first_class_dtm: datetime.datetime, classes_in_series: int, class_duration: int) -> list:
    """Function to create a schedule based off of frequency

    Args:
        frequency (dict): frequency of schedule
        first_class_dtm (datetime.datetime): first class datetime
        classes_in_series (int): total classes in series

    Returns:
        list: Returns a list with scheduled events
    """
    first_class_dtm = datetime.datetime.strptime(
        first_class_dtm.replace('Z', '+0000'), '%Y-%m-%dT%H:%M:%S.%f%z')
    date_list = [(first_class_dtm, first_class_dtm +
                  datetime.timedelta(minutes=class_duration))]
    enum = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6
    }

    if frequency["frequency_type"] == "days":
        class_frequency = frequency["classes_per_week"]
        for _ in range(classes_in_series-1):
            next_class_start = first_class_dtm + \
                datetime.timedelta(days=class_frequency)
            next_class_end = next_class_start + \
                datetime.timedelta(minutes=class_duration)
            date_list.append((next_class_start, next_class_end))
            first_class_dtm = next_class_start

        return date_list

    if frequency["frequency_type"] == "weeks":
        class_frequency = frequency["skip_weeks"]
        class_days = []
        for _ in range(classes_in_series-1):
            for x in frequency["days"]:
                class_days.append(enum[x.lower()])

        while len(date_list) < classes_in_series-1:
            next_class_start = first_class_dtm
            while not next_class_start.weekday() == class_days[0]:
                next_class_start += datetime.timedelta(days=1)
                next_class_end = next_class_start + \
                    datetime.timedelta(minutes=class_duration)

            date_list.append((next_class_start, next_class_end))
            class_days.remove(next_class_start.weekday())

            if len(date_list) % len(frequency["days"]) == 0:
                first_class_dtm += datetime.timedelta(weeks=class_frequency)

        return date_list

    if frequency["frequency_type"] == "months":
        class_frequency = frequency["skip_months"]
        for _ in range(classes_in_series-1):
            if first_class_dtm.month == 2 and first_class_dtm.day < 28:
                continue
            next_class_start = first_class_dtm + \
                datetime.timedelta(days=30*class_frequency)
            next_class_end = next_class_start + \
                datetime.timedelta(minutes=class_duration)
            date_list.append((next_class_start, next_class_end))
        return date_list

    if frequency["frequency_type"] == "years":
        class_frequency = frequency["skip_years"]
        frequency["dates"].append(first_class_dtm)
        date_list = []
        while len(date_list) < classes_in_series-1:
            for date in frequency["dates"]:
                next_class_start = date + \
                    datetime.timedelta(days=365*class_frequency)
                next_class_end = next_class_start + \
                    datetime.timedelta(minutes=class_duration)
                date_list.append((next_class_start, next_class_end))
        return date_list

    return None
