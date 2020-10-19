import pdfplumber
import os
import re
import pandas as pd
from collections import namedtuple
from tqdm import tqdm
import numpy as np

Line = namedtuple('Line', 'race_type race_location race_day race_time rank bib name country start_behind prone1 '
                          'prone2 stand1 stand2 err_total result_time cup_points pdf_path')

locations = {
    'AUT': ['Hochfilzen'],
    'SLO': ['Pokljuka'],
    'SVK': ['Brezno-Osrblie'],
    'GER': ['Oberhof', 'Ruhpolding', 'Chiemgau Arena',
            'Biathlon Stadion Am Grenzadler'],
    'ITA': ['Antholz-Anterselva', 'Antholz - Anterselva',
            'Cesana San Sicario', 'Torino', 'Antholz Obertal'],
    'USA': ['Soldier Hollow', 'Verizon Sports Complex',
            'Maine Winter Sports Center', 'Presque Isle',
            '10TH MOUNTAIN SKI CENTER'],
    'SWE': ['Oestersund', 'Östersund'],
    'FIN': ['Lahti', 'Kontiolahti', 'BIATHLON STADIUM KONTIOLAHTI',
            'KONTIOLAHTI'],
    'NOR': ['Holmenkollen', 'Beitostolen', 'Trondheim'],
    'RUS': ['Khanty-Mansiysk', 'Nordic Ski Centre', 'SOCHI',
            'Tyumen', 'Laura Cross-Country Ski', 'Khanty Mansiysk',
            'A.V. Filipenko Winter Sports Center', 'Nordic Sport Complex'],
    'KOR': ['PyeongChang', 'Alpensia Biathlon Center',
            'Alpensia Biathlon Centre'],
    'CAN': ['Whistler', 'Vancouver', 'Canmore', 'Whistler Olympic Park'],
    'CZE': ['Nove Mesto'],
    'FRA': ['Annecy-Le Grand Bornand', 'Annecy']
}

r_types = [
    'INDIVIDUAL', 'SPRINT', 'Pursuit', 'MASS START',
    'RELAY', 'MIXED RELAY', 'SINGLE MIXED'
]
loc_to_date = {
    'Oberhof': ['2002-01-20', '2005-01-09'],
    'Antholz-Anterselva': ['2002-01-27', '2006-01-20', '2006-01-21',
                           '2008-01-19', '2009-01-24', '2010-01-24'],
    'Lahti': ['2002-03-17', '2007-03-04'],
    'Holmenkollen': ['2002-03-23', '2006-03-25', '2010-03-20'],
    'Brezno-Osrblie': ['2002-12-22', '2003-12-21', '2005-12-18'],
    'Ruhpolding': ['2003-01-19', '2004-01-18', '2009-01-18', '2011-01-16'],
    'Khanty-Mansiysk': ['2003-03-16', '2007-03-17', '2011-03-06'],
    'Oestersund': ['2005-11-27', '2006-12-03', '2008-02-10'],
    'Pokljuka': ['2006-03-11', '2009-12-20'],
    'Kontiolahti': ['2006-03-18', '2010-03-14', '2015-03-08'],
    'Hochfilzen': ['2006-12-09', '2008-12-13', '2010-12-11', '2010-12-12'],
    'Trondheim': ['2009-03-21'],
    'Presque Isle': ['2011-02-06']
}

# Creating a regex string that refers to r_types list.
race_types_regex_str = ''
for i in r_types:
    race_types_regex_str += '.*{}|'.format(i)
race_type_re = re.compile(r'{}'.format(race_types_regex_str), re.IGNORECASE)

# Getting all locations in one list.
loc_list = []
for v in locations.values():
    for i in v:
        loc_list.append(i.lower())
        loc_list.append(i)
        loc_list.append(i.upper())

# Making regex to match locations.
locations_regex_str = ''
for i in loc_list:
    locations_regex_str += '{}|'.format(i)
location_re = re.compile(r'{}'.format(locations_regex_str[:-1]), re.IGNORECASE)

# Creating regex fo matching the date of the race.
race_day_re = re.compile(r'(?<=\w\w\w\s)\d{1,2}\s\w\w\w\s\d{4}|(?<=\w\w\w\s\s)\d{1,2}\s\w\w\w\s\d{4}')

# Creating the regex to match the start tome of the race.
race_time_re = re.compile(r'(?<=START TIME:|Start Time:|START TIME |start time |Start Time )(\s*)(\d\d:\d\d)|('
                          r'?<=DEBUT)(\s*)(\d\d:\d\d)')

# Creating regex to match player performance.
performance_re = re.compile((r"(?P<rank>(?<![a-zA-Z]\s)(?<=[=])?\d{1,2}(?=\s\d{1,2}))?\s?"
                             "(?(rank)(?P<bib1>(?<![a-zA-Z]\s)\d{1,2}y?r?)|(?P<bib2>(?<![a-zA-Z]\s)\A\d{1,"
                             "2}y?r?))\s?(?=\s?[a-z\u0080-\uFFFFA-Z.\')(-]{2}) "
                             "(?P<name>[a-z\u0080-\uFFFFA-Z\s.\')(-]*\s[\u0080-\uFFFFa-zA-Z\s.\')(-:]*(?=\s[A-Z]{3}))\s"
                             "(?P<country>[A-Z]{3}(?=\s))\s*"
                             "(?P<start_behind>\d{1,2}:\d{2})?\s?"
                             "(?P<prone1>[0,1,2,3,4,5]{1})?\s?"
                             "(?P<prone2>[0,1,2,3,4,5]{1})?\s?"
                             "(?P<stand1>[0,1,2,3,4,5]{1})?\s?"
                             "(?P<stand2>[0,1,2,3,4,5]{1})?\s?"
                             "(?P<err_total>\d{1,2})?\s*"
                             "(?P<result_time>[+]?\d{1,2}:{0,1}\d{0,2}.\d{1,2})?\s?"
                             "(?P<cup_points>(?<=[.]\d\s)\d{1,3})?"))


# Mapping venues/cities to countries.
def loc_to_country(x):
    for country, v_list in locations.items():
        for v in v_list:
            if x == v.lower():
                x = country
    return x


# Remove duplicate names.
with open('unique_names.txt') as f:
    unique_names_dict = eval(f.read())


def name_lookups(x):
    for or_name, dup_names in unique_names_dict.items():
        for dup_name in dup_names:
            if x == dup_name:
                x = or_name
    return x


# Removes bibs from names
def bib_remover(row):
    if row[:3] == 'yr ':
        return row[3:]
    if row[:2] == 'y ' or row[:2] == 'r ':
        return row[2:]
    else:
        return row


# Helper function to print pdf line-by-line.
def print_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages
        text_to_print = ''
        for page in pages:
            text_to_print += page.extract_text() + '\n'
    return text_to_print.split('\n')


def parse_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages
        pdf_text = ''
        for page in pages:
            pdf_text += page.extract_text() + '\n'
    ntuples_lines = []
    race_type_match = None
    race_location_match = None
    race_day_match = None
    race_time_match = None
    skipper = 0
    for l in pdf_text.split('\n'):
        # For skipping the rows that go after 'revised'.
        if skipper == 1:
            if not race_location_match:
                race_location = location_re.search(l)
                if race_location:
                    race_location_match = race_location.group(0)
            skipper = 0
            continue
        if l == 'REVISED':
            skipper += 1
        if l != '' and l[0] == '=':
            # To fix inconsistency where in some pdf
            # equal ranks are written as '=1'.
            l = l[1:]
        if l != '' and l[0:3] == 'FF ':
            # To fix inconsistency where in some pdf there is
            # photofinish marked as FF.
            l = l[3:]
        if 'WeronikaPOL' in l:
            # Wierd bug with country 'glued' to name,
            # failed to change my regex without ruining everything else,
            l = l.replace('WeronikaPOL', 'Weronika POL')
        if 'WeronikPaOL' in l:
            l = l.replace('WeronikPaOL', 'Weronika POL')
        if ' yr ' in l:
            l = l.replace(' yr ', ' ')
        if ' r ' in l:
            l = l.replace(' r ', ' ')
        if ' y ' in l:
            l = l.replace(' y ', ' ')
        if ' b ' in l:
            l = l.replace(' b ', ' ')
        if not race_type_match:
            race_type = race_type_re.search(l)
            if race_type.group(0) != '':
                race_type_match = race_type.group(0)
        if not race_location_match:
            race_location = location_re.search(l)
            if race_location:
                race_location_match = race_location.group(0)
        if not race_day_match:
            race_day = race_day_re.search(l)
            if race_day:
                race_day_match = race_day.group(0)
        if not race_time_match:
            race_time = race_time_re.search(l)
            if race_time:
                race_time_match = (
                    race_time.group(2) if race_time.group(2)
                    else race_time.group(4)
                )
        performance = performance_re.search(l)
        rank = bib = name = country = start_behind = prone1 = prone2 = \
            stand1 = stand2 = err_total = result_time = cup_points = None
        if performance:
            rank = performance.group('rank') if performance.group('rank') else 0
            bib = (
                performance.group('bib1') if performance.group('bib1')
                else performance.group('bib2')
            )
            name = performance.group('name')
            country = performance.group('country')
            start_behind = performance.group('start_behind')
            prone1 = (
                performance.group('prone1') if performance.group('prone1')
                else np.nan
            )
            prone2 = (
                performance.group('prone2') if performance.group('prone2')
                else np.nan
            )
            stand1 = (
                performance.group('stand1') if performance.group('stand1')
                else np.nan
            )
            stand2 = (
                performance.group('stand2') if performance.group('stand2')
                else np.nan
            )
            err_total = (
                performance.group('err_total') if performance.group('err_total')
                else np.nan
            )
            result_time = (
                performance.group('result_time') if performance.group('result_time')
                else np.nan
            )
            cup_points = (
                performance.group('cup_points') if performance.group('cup_points')
                else np.nan
            )
        if name is not None:
            ntuples_lines.append(Line(race_type_match, race_location_match,
                                      race_day_match, race_time_match, rank,
                                      bib, name, country, start_behind,
                                      prone1, prone2, stand1, stand2,
                                      err_total, result_time, cup_points,
                                      pdf_path))
        if 'time adjustment' in l.lower() or 'disqualified' in l.lower() or 'result cancellation' in l.lower():
            break
    return pd.DataFrame(ntuples_lines)


def parse_dir(directory):
    pdf_list = []
    for foldername, _, filenames in os.walk(directory):
        for filename in filenames:
            if str(filename).endswith('.pdf'):
                pdf_list.append(os.path.join(foldername, filename))
    counter = 0
    df = None
    for item in tqdm(pdf_list):
        df_temp = parse_pdf(item)
        df_temp['race_id'] = ('0000' + str(counter))[-4:]
        if counter > 0:
            df = pd.concat([df, df_temp], ignore_index=True)
        else:
            df = df_temp
        counter += 1
    return df


def load_data():
    df_purst = parse_dir('race_data/pursuit/')
    df_start = parse_dir('race_data/startlist_pursuit/')
    # Fixing incorrectly parsed rows with wierd countries/month names.
    wierd_countries = [
        'JAN', 'FEB', 'MAR', 'APR', 'MAY',
        'JUN', 'SKI', 'END', 'JUL', 'AUG', 'ADR',
        'SEP', 'OCT', 'NOV', 'DEC', 'IBU', 'ECR'
    ]
    df_purst = df_purst.drop(df_purst[df_purst['country'].isin(wierd_countries)].index)
    df_start = df_start.drop(df_start[df_start['country'].isin(wierd_countries)].index)
    df_purst.loc[df_purst['race_day'] == '14 MRZ 2010', 'race_day'] = '14 MAR 2010'
    # Coverting race_day to datetime.
    df_purst['race_day'] = pd.to_datetime(df_purst['race_day'])
    df_start['race_day'] = pd.to_datetime(df_start['race_day'])
    # Getting the race_days with missing race_locations into a list,
    # matching with loc_to_date dict, filling misssing values.
    days_with_missing_locations_purst = [
        str(x)[:10] for x in
        df_purst.loc[df_purst['race_location'].isnull()]['race_day'].value_counts().index
    ]
    for date in days_with_missing_locations_purst:
        for venue, v_date in loc_to_date.items():
            if date in v_date:
                df_purst.loc[df_purst['race_day'] == date, 'race_location'] = venue
    days_with_missing_locations_start = [
        str(x)[:10] for x in
        df_start.loc[df_start['race_location'].isnull()]['race_day'].value_counts().index
    ]
    for date in days_with_missing_locations_start:
        for venue, v_date in loc_to_date.items():
            if date in v_date:
                df_start.loc[df_start['race_day'] == date, 'race_location'] = venue
    # Making all locations lowercase for 'normalization'.
    df_purst['race_location'] = (
        df_purst['race_location'].apply(lambda x: x.lower())
    )
    # Creating gender column.
    df_purst['gender'] = (
        df_purst['race_type']
        .apply(lambda x: 'male' if '12.5' in x else 'female')
    )
    df_start['gender'] = (
        df_start['race_type']
        .apply(lambda x: 'male' if '12.5' in x else 'female')
    )
    # Mapping venue/city ('race_location') to corresponding
    # country ('race_country').
    df_purst['race_country'] = df_purst['race_location'].apply(loc_to_country)
    # Filling missing start_behind based on values from df_start dataframe.
    # Removing bib types from name column in startlist dataframe
    # and from bib column in pursuit dataframe.
    df_purst['bib'] = df_purst['bib'].apply(lambda x: x.rstrip('yr'))
    df_start['name'] = df_start['name'].apply(bib_remover)
    # Create unique key for each dataframe to update on.
    df_purst['date_bib_ind'] = (
            df_purst['race_day']
            .apply(lambda x: x.strftime('%Y-%m-%d')) + '-' + df_purst['bib'] + '-' + df_purst['gender']
    )
    df_start['date_bib_ind'] = (
            df_start['race_day']
            .apply(lambda x: x.strftime('%Y-%m-%d')) + '-' + df_start['bib'] + '-' + df_start['gender']
    )
    # Set index to created column.
    df_purst.set_index('date_bib_ind', inplace=True)
    df_start.set_index('date_bib_ind', inplace=True)
    df_purst.loc['2017-01-07-49-female', 'start_behind'] = '2:30'
    # Update only nans in df_purst start_behind.
    df_purst.update(df_start['start_behind'], overwrite=False)
    df_purst.reset_index(inplace=True)
    df_purst.drop('date_bib_ind', axis=1, inplace=True)
    # Removing duplicates from name column.
    df_purst['name'] = df_purst['name'].apply(name_lookups)
    return df_purst, df_start


if __name__ == '__main__':
    df_pursuit, df_startlist = load_data()
    df_pursuit.to_csv('pursuit_data_raw.csv', index=False)
