#!/usr/bin/env python3

import sys, getopt
import pyBlitz
from collections import OrderedDict
import json
import csv
import pdb
import os.path
from pathlib import Path
from datetime import datetime
import re
import scrape_schedule
from shutil import copyfile

import settings

def main(argv):
    stat_file = settings.data_path + "stats.json"
    merge_file = settings.data_path + "merge.json"
    week = "current"
    verbose = False
    test = False
    try:
        opts, args = getopt.getopt(argv, "hs:m:w:vt", ["help", "stat_file=", "merge_file=", "week=", "verbose", "test"])
    except getopt.GetoptError as err:
        print(err)
        usage()
        sys.exit(2)
    output = None
    verbose = False
    for o, a in opts:
        if o in ("-v", "--verbose"):
            verbose = True
        elif o in ("-t", "--test"):
            test = True
        elif o in ("-h", "--help"):
            usage()
            sys.exit
        elif o in ("-s", "--stat_file"):
            stat_file = a
        elif o in ("-w", "--week"):
            week = a
        elif o in ("-m", "--merge_file"):
            merge_file = a
        else:
            assert False, "unhandled option"
    if (test):
        testResult = pyBlitz.Test(verbose)
        if (testResult):
            print ("Test result - pass")
        else:
            print ("Test result - fail")
    else:
        PredictTournament(week, stat_file, merge_file, verbose)

def usage():
    usage = """
    -h --help                 Prints this help
    -v --verbose              Increases the information level
    -s --stat_file            stats file (json file format)
    -m --merge_file           merge file (csv/spreadsheet file format)
    -t --test                 runs test routine to check calculations
    -w --week                 week to predict
                                [current, all, 1-16] default is current
    """
    print (usage) 

def EarliestUnpickedWeek(list_schedule):
    current_date = datetime.now().date()
    for i, e in reversed(list(enumerate(list_schedule))):
        for item in e.values():
            str_date = "{0}, {1}".format(item["Date"], item["Year"])
            dt_obj = datetime.strptime(str_date, '%A, %B %d, %Y')
            if (current_date >= dt_obj.date()):
                return i
    return 0

def GetWeekRange(week, list_schedule):
    max_range = len(list_schedule)
    if (week[0].lower() == "a"):
        return range(0, max_range)
    if (week[0].lower() == "c"):
        return range(EarliestUnpickedWeek(list_schedule), EarliestUnpickedWeek(list_schedule) + 1)
    idx = GetIndex(week)
    if ((idx < 1) or (idx > max_range)):
        return range(EarliestUnpickedWeek(list_schedule), EarliestUnpickedWeek(list_schedule) + 1)
    return range(int(week) - 1, int(week))

def GetIndex(item):
    filename = os.path.basename(str(item))
    idx = re.findall(r'\d+', str(filename))
    if (len(idx) == 0):
        idx.append("0")
    return int(idx[0])

def GetSchedFiles(path, templatename):
    A = []
    for p in Path(path).glob(templatename):
        A.append(str(p))
    file_list = []
    for item in range(0, 17):
        file_list.append("?")
    for item in A:
        idx = GetIndex(item)
        file_list[idx] = item
    file_list = [x for x in file_list if x != "?"]
    return file_list

def CurrentStatsFile(filename):
    if (not os.path.exists(filename)):
        return False
    stat = os.path.getmtime(filename)
    stat_date = datetime.fromtimestamp(stat)
    if stat_date.date() < datetime.now().date():
        return False
    return True

def RefreshStats():
    import scrape_bornpowerindex
    import scrape_teamrankings
    import combine_stats
    import measure_results

def FindTeams(teama, teamb, dict_merge):
    FoundA = ""
    FoundB = ""
    for item in dict_merge.values():
        if (teama.lower().strip()== item["scheduled"].lower().strip()):
            FoundA = item["BPI"]
        if (teamb.lower().strip() == item["scheduled"].lower().strip()):
            FoundB = item["BPI"]
        if (FoundA and FoundB):
            break
    return FoundA, FoundB

def FindAbbr(teama, teamb, dict_merge):
    FoundAbbrA = ""
    FoundAbbrB = ""
    for item in dict_merge.values():
        stats = item["BPI"].lower().strip()
        abbr = item["abbr"].strip()
        if (teama.lower().strip() == stats):
            FoundAbbrA = abbr
        if (teamb.lower().strip() == stats):
            FoundAbbrB = abbr
        if (FoundAbbrA and FoundAbbrB):
            break
    return FoundAbbrA, FoundAbbrB

def SaveOffFiles(path, file_list):
    Path(path).mkdir(parents=True, exist_ok=True) 
    for item in file_list:
        filename = os.path.basename(str(item))
        dest_file = "{0}{1}".format(path, filename)
        if (not os.path.exists(dest_file)):
            copyfile(item, dest_file)

def PredictTournament(week, stat_file, merge_file, verbose):
    now = datetime.now()
    year = int(now.year)
    week_path = "{0}{1}/".format(settings.predict_root, year)
    sched_path = "{0}{1}/{2}".format(settings.predict_root, year, settings.predict_sched)
    saved_path = "{0}{1}/{2}".format(settings.predict_root, year, settings.predict_saved)
    if (not "a" in week.lower().strip()):
        idx = GetIndex(week)
        if ((idx < 1) or (idx > len(schedule_files))):
            week = "current"
    print ("Weekly Prediction Tool")
    print ("**************************")
    print ("Statistics file:\t{0}".format(stat_file))
    print ("Team Merge file:\t{0}".format(merge_file))
    print ("\trunning for Week: {0}".format(week))
    print ("\tDirectory Location: {0}".format(week_path))
    print ("**************************")
    weekly_files = GetSchedFiles(week_path, "week*.csv")
    SaveOffFiles(saved_path, weekly_files)
    for p in Path(week_path).glob("week*.csv"):
        p.unlink()
    if (not CurrentStatsFile(stat_file)):
        RefreshStats()
    schedule_files = GetSchedFiles(sched_path, "sched*.json")
    if (not schedule_files):
        scrape_schedule.year = now.year
        scrape_schedule.main(sys.argv[1:])
        schedule_files = GetSchedFiles(sched_path, "sched*.json")
    if (not schedule_files):
        print ("schedule files are missing, run the scrape_schedule tool to create")
        exit()
    dict_merge = []
    if (not os.path.exists(merge_file)):
        print ("master merge file is missing, run the combine_merge tool to create")
        exit()
    with open(merge_file) as merge_file:
        dict_merge = json.load(merge_file, object_pairs_hook=OrderedDict)
    if (not os.path.exists(stat_file)):
        print ("statistics file is missing, run the combine_stats tool to create")
        exit()
    with open(stat_file) as stats_file:
        dict_stats = json.load(stats_file, object_pairs_hook=OrderedDict)
    list_schedule = []
    for file in schedule_files:
        with open(file) as schedule_file:
            item = json.load(schedule_file, object_pairs_hook=OrderedDict)
            list_schedule.append(item)
    weeks = GetWeekRange(week, list_schedule)
    for idx in range(len(schedule_files)):
        if (idx in weeks):
            list_predict = []
            list_predict.append(["Index", "Year", "Date", "TeamA", "AbbrA", "ChanceA", "ScoreA",
                "Spread", "TeamB", "AbbrB", "ChanceB", "ScoreB"])
            index = 0
            for item in list_schedule[idx].values():
                teama, teamb = FindTeams(item["TeamA"], item["TeamB"], dict_merge)
                abbra, abbrb = FindAbbr(teama, teamb, dict_merge)
                neutral = False
                if (item["Home"].lower().strip() == "neutral"):
                    neutral = True
                dict_score = pyBlitz.Calculate(teama, teamb, neutral, verbose)
                index += 1
                if (len(dict_score) > 0):
                    list_predict.append([str(index), item["Year"], item["Date"], item["TeamA"], abbra,
                        dict_score["chancea"], dict_score["scorea"], dict_score["spread"], item["TeamB"],
                        abbrb, dict_score["chanceb"], dict_score["scoreb"]])
                else:
                    if (teama == "?" and teamb != "?"):
                        list_predict.append([str(index), item["Year"], item["Date"], item["TeamA"], "?", "0%",
                            "?", "?", item["TeamB"], abbrb, "100%", "?"])
                    if (teamb == "?" and teama != "?"):
                        list_predict.append([str(index), item["Year"], item["Date"], item["TeamA"], abbra, "100%",
                            "?", "?", item["TeamB"], "?", "0%", "?"])
                    if (teamb == "?" and teama == "?"):
                        list_predict.append([str(index), item["Year"], item["Date"], item["TeamA"], "?", "?",
                            "?", "?", item["TeamB"], "?", "?", "?"])
                    if (teamb != "?" and teama != "?"):
                        list_predict.append([str(index), item["Year"], item["Date"], item["TeamA"], abbra, "?",
                            "?", "?", item["TeamB"], abbrb, "?", "?"])
            Path(week_path).mkdir(parents=True, exist_ok=True) 
            output_file = "{0}week{1}.csv".format(week_path, GetIndex(schedule_files[idx]))
            predict_sheet = open(output_file, 'w', newline='')
            csvwriter = csv.writer(predict_sheet)
            for row in list_predict:
                csvwriter.writerow(row)
            predict_sheet.close()
            print ("{0} has been created.".format(output_file))

    # How are we doing? Let's find Out!
    file = "{0}results.json".format(saved_path)
    if (os.path.exists(file)):
        dict_results = []
        last_week = GetIndex(week) - 1
        with open(file) as results_file:
            dict_results.append(json.load(results_file, object_pairs_hook=OrderedDict))
        if (len(dict_results) > 0):
            for idx in range(len(dict_results)):
                for item in dict_results[idx].values():
                    if (last_week > 0 and last_week == item["Week"]):
                        print ("=================================================")
                        print ("For week{0}, winning percent was: {1}%".
                            format(last_week, item["Percent Correct"]))
                        print ("=================================================")
                    if (item["Week"] == 99):
                        print ("=================================================")
                        print ("For this year so far, winning percent is: {0}%".
                            format(item["Percent Correct"]))
                        print ("=================================================")
    print ("done.")
if __name__ == "__main__":
  main(sys.argv[1:])
