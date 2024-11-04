import datetime


def check_overlap(schedule1, schedule2):
    """Function to compare if two schedule times overlap

    Args:
        schedule1 (str): Time 1 to be compared to Time 2
        schedule2 (str): Time 1 to be compared to Time 2

    Returns:
        _type_: _description_
    """

    startTime = datetime.datetime.strptime(
        schedule1["startTime"], '%m/%d/%Y  %I:%M %p')
    endTime = datetime.datetime.strptime(
        schedule1["endTime"], '%m/%d/%Y %I:%M %p')
    startTime2 = datetime.datetime.strptime(
        schedule2["startTime"], '%m/%d/%Y %I:%M %p')
    endTime2 = datetime.datetime.strptime(
        schedule2["endTime"], '%m/%d/%Y %I:%M %p')
    return startTime < endTime2 and endTime > startTime2
