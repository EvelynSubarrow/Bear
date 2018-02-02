#!/usr/bin/env python3

import calendar, json, textwrap, smtplib, os, sys, re
from datetime import date, datetime, timedelta
from urllib import request

WEEK_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_SHORT = [a[:3] for a in WEEK_DAYS]
num_re = re.compile(r"^(-?\d+).*")

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

today = date(*config["date"]) if "date" in config else date.today()
year = today.year
month = today.month

next_year = year+1 if month == 12 else year
next_month = max((month + 1) % 13, 1)

def first_day(year, month, weekday):
    monthcal = c.monthdatescalendar(year,month)
    return [day for week in monthcal for day in week if
            day.strftime("%a").lower() == weekday.lower() and
            day.month == month][0]

def parse_frequency(frequency):
    base = date(year, month, 1)
    if not frequency or frequency[0]=="#":
        return date(1000,1,1)
    while frequency:
        first = frequency[0]
        frequency = frequency[1:]
        if first in ["^", "/"]:
            wday = frequency[:3]
            frequency = frequency[3:]
            base = [a for a in [first_day(year, month, wday), first_day(next_year, next_month, wday)] if a >= date.today() or first=="/"][0]
        elif first=="+":
            offset = num_re.match(frequency).group(1)
            frequency = frequency[len(offset):]
            base += timedelta(days=int(offset))
        else:
            raise Exception("'%s': Unknown token" % first)
    return base

def col80(text, indent):
    return " " * indent + ("\n" + " " * indent).join(textwrap.wrap(text, 80-indent))

def human_countdown(date_from, date_to):
    days = date_from.toordinal() - date_to.toordinal()
    if days==1: return "tomorrow"
    elif days==0: return "today"
    else: return "in %d days" % days

for meet in meets:
    if "date" in meet:
        meet["date"] = date(*meet["date"])
    else:
        meet["date"] = parse_frequency(meet["frequency"])

    if meet["date"].toordinal() - today.toordinal() not in meet.get("notify", notify):
        print("%10s %9s: Not time to send." % (meet["date"], meet["type"]))
        continue

    print("%10s %9s: Sending" % (meet["date"], meet["type"]))

    disruptions = ""
    try:
        with request.urlopen("https://api.tfl.gov.uk/Line/Mode/tube,dlr,overground,tram,tflrail/Status?startDate=%s&endDate=%s&detail=False&app_id=%s&app_key=%s" % (meet["date"].isoformat(), (meet["date"] + timedelta(days=1)).isoformat(), config["app_id"], config["api_key"])) as response:
            result = json.loads(response.read().decode("utf8"))
        for line in result:
            statuses = [status for status in line["lineStatuses"] if status["statusSeverity"] != 10]
            if len(statuses):
                disruptions += "    %s:" % line["name"] + "\n"
                disruptions += "\n".join([col80(status["reason"], 8) for status in statuses]) + "\n"
        if not disruptions:
            disruptions = "    There are no disruptions."
    except:
        disruptions = "An error occurred while retrieving TfL disruptions."
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
        with open(meet["include"][include], "r") as file:
            params[include] = file.read().rstrip()
    with smtplib.SMTP(config["host"]) as smtp:
        print(smtp.sendmail(config["from"], [config["to"]], message % params))
    print(message % params)
