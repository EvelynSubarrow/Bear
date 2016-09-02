#!/usr/bin/env python3

import calendar, json, textwrap, smtplib, os, sys
from datetime import date, datetime, timedelta
from urllib import request

WEEK_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

#Because cron
os.chdir(sys.path[0])

with open("config.json") as config_file:
    config = json.loads(config_file.read())
with open("secret.json") as config_file:
    config.update(json.loads(config_file.read()))

with open("2600.txt") as mail:
    message = mail.read()

notify = config["notify"]
meets = config["meets"]

c = calendar.Calendar(firstweekday=calendar.SUNDAY)

today = date.today()
year = today.year
month = today.month

next_year = year+1 if month == 12 else year
next_month = max((month + 1) % 13, 1)

def first_friday(year, month):
    monthcal = c.monthdatescalendar(year,month)
    return [day for week in monthcal for day in week if
            day.weekday() == calendar.FRIDAY and
            day.month == month][0]

def col80(text, indent):
    return " " * indent + ("\n" + " " * indent).join(textwrap.wrap(text, 80-indent))

def human_countdown(date_from, date_to):
    days = date_from.toordinal() - date_to.toordinal()
    return "tomorrow" if days == 1 else "in %d days" % days

next_meet = next(filter(lambda x: x > date.today(), [first_friday(year, month),first_friday(next_year, next_month)]))

config["main"].update({"date": [next_meet.year, next_meet.month, next_meet.day]})
meets.append(config["main"])

for meet in meets:
    meet["date"] = date(meet["date"][0], meet["date"][1], meet["date"][2])
    if meet["date"].toordinal() - today.toordinal() not in notify:
        print("%10s %9s: Not time to send." % (meet["date"], meet["type"]))
        continue
    print("%10s %9s: Sending" % (meet["date"], meet["type"]))
    disruptions = ""
    with request.urlopen("https://api.tfl.gov.uk/Line/Mode/tube,dlr,overground,tram,tflrail/Status?startDate=%s&endDate=%s&detail=False&app_id=%s&app_key=%s" % (meet["date"].isoformat(), (meet["date"] + timedelta(days=1)).isoformat(), config["app_id"], config["api_key"])) as response:
        result = json.loads(response.read().decode("utf8"))
    for line in result:
        statuses = [status for status in line["lineStatuses"] if status["statusSeverity"] != 10]
        if len(statuses):
            disruptions += "    %s:" % line["name"] + "\n"
            disruptions += "\n".join([col80(status["reason"], 8) for status in statuses]) + "\n"
    if !disruptions:
        disruptions = "    There are no disruptions."
    params = meet
    params.update({
        "disruptions" : disruptions.rstrip(),
        "meet_date"    : meet["date"].isoformat(),
        "meet_weekday" : WEEK_DAYS[calendar.weekday(meet["date"].year, meet["date"].month, meet["date"].day)],
        "meet_countdown": human_countdown(meet["date"], today),
        "meet_time": "-".join(meet["times"]),
        "created_datetime": datetime.utcnow().isoformat() + "Z",
        "from" : config["from"],
        "to" : config["to"],
        })
    for include in meet["include"]:
        with open(meet["include"][include]) as file:
            params[include] = file.read().rstrip()
    smtp = smtplib.SMTP(config["host"])
    smtp.sendmail(config["from"], [config["to"]], message % params)

