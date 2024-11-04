from src.api.api_models.courses.create import Series


def create_frequency(content: Series) -> dict:
    """Function to create frequency of schedule

    Args:
        content (Series): input from route

    Returns:
        dict: Returns a dict with frequency information
    """
    enum = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "steptember": 9,
        "october": 10,
        "november": 11,
        "december": 12
    }
    if content.classFrequency.days:
        return {
            "frequency_type": "days",
            "classes_per_week": content.classFrequency.days.frequency
        }
    if content.classFrequency.weeks:
        return {
            "frequency_type": "weeks",
            "days": content.classFrequency.weeks.days,
            "skip_weeks": content.classFrequency.weeks.frequency
        }
    if content.classFrequency.months:
        return {
            "frequency_type": "months",
            "skip_months": content.classFrequency.months.frequency,
            "months": [enum[month.lower()] for month in content.classFrequency.months.months],
            "days": content.classFrequency.months.days,
        }
    if content.classFrequency.years:
        return {
            "frequency_type": "years",
            "skip_years": content.classFrequency.years.frequency,
            "dates": content.classFrequency.years.dates,
        }
    return None
