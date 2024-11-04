import datetime

base = datetime.datetime.today()
enum = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6
}
classes_in_series = 20
class_frequency = 2
class_days = []

for _ in range(classes_in_series):
    for x in ["monday", "thursday"]:
        class_days.append(enum[x])

date_list = []
print(class_days)
while len(date_list) < classes_in_series:
    next_class = base
    print(next_class)
    while not next_class.weekday() == class_days[0]:
        next_class += datetime.timedelta(days=1)
    date_list.append(next_class)
    class_days.remove(next_class.weekday())

    if len(date_list) % len(["monday", "thursday"]) == 0:
        base += datetime.timedelta(weeks=class_frequency)

print(date_list)


# {
#     "courses": [{

#     }],
# }

# {
#     "series": [{
#         "schedule": [
#             {
#                 "date": "",
#                 "startTime": '',
#                 "endTime": ''
#             },
#         ]
#     }]
# }
# {
#     "bundles": [{
#         "bundle": {

#         },
#         "courses": [{
#         }]
#     }]
# }