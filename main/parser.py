from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
from selenium import webdriver

main_page = 'http://reestr.nostroy.ru'
reestr_page = main_page + '/reestr?'
df = pd.read_excel("../data/ТЗ.xlsx",
                   sheet_name=1,
                   converters={'ИНН': lambda value: str(value)})
inns = df['ИНН']
options = webdriver.ChromeOptions()
options.add_argument('--ignore-certificate-errors')
options.add_argument('--incognito')
options.add_argument('--headless')
driver = webdriver.Chrome('../webdriver/chromedriver', chrome_options=options)

df1 = pd.read_excel("../data/ТЗ.xlsx",
                    sheet_name=2,
                    header=[0, 1])
df1.reset_index()
df1 = df1.rename(columns=lambda x: x if 'Unnamed' not in str(x) else '')
df1.columns.names = (None, None)


def url_parameters(inn: str) -> dict:
    return {
        'm.fulldescription': '',
        'm.shortdescription': '',
        'm.inn': inn,
        'm.ogrnip': '',
        'bms.id': '',
        'bmt_id': '',
        'u.registrationnumber': ''
    }


def concat_params(inn: str) -> str:
    result = ''
    for (key, value) in url_parameters(inn).items():
        result += '{}={}&'.format(key, value)
    return result[0:-1]


def page_by_inn(inn: str) -> BeautifulSoup:
    url_string = reestr_page + concat_params(inn)
    driver.get(url_string)
    source = driver.page_source
    result = BeautifulSoup(source, 'html.parser')
    return result


# Retrieve information from SRO's main page
def get_mainpage_inform(tag) -> list:
    member_props = []
    for ch in tag.children:
        if ch.string:
            member_props.append(format_string(ch.string))
    span_parent = tag.find_next('span').find_parent()
    for c in span_parent.children:
        cstr = c.string
        if cstr:
            member_props.append(format_string(cstr))
    member_props = [e for e in member_props if e != '']
    selected = [e for e in range(len(member_props)) if e not in [0, 3]]
    return [member_props[i] for i in selected]


# Retrieve information from member's main chapter
def get_sro_member_inform(tag) -> list:
    result = []
    data_keys = ['Дата регистрации в реестре', 'Дата прекращения членства']
    for tr in tag:
        th = tr.find_next('th')
        for key in data_keys:
            if th.string.find(key) != -1:
                td = tr.find_next('td').string
                result.append(td if td else None)
    return result


# Get parser of chapter on page with special reference
def get_member_page_chapter(ref: str, chapter: str) -> BeautifulSoup:
    url_string = main_page + ref + chapter
    driver.get(url_string)
    source = driver.page_source
    return BeautifulSoup(source, 'html.parser')


# Retrieve information from 'RIGHTS' chapter if it's not empty
def get_member_rights_inform(ref: str) -> list:
    soup = get_member_page_chapter(ref, '/rights')
    trs = soup.find_all('tr')
    if len(trs) == 0:
        return []
    rights_props = []
    tds_center = [tr.find_all('td', attrs={'class': 'text-center'})[0] for tr in trs
                  if len(tr.find_all('td', attrs={'class': 'text-center'})) == 1]
    for td in tds_center:
        tdstr = td.string
        if tdstr:
            rights_props.append(format_string(tdstr))
        else:
            temp = [ch.string for ch in td.children if ch.string]
            rights_props.append(format_string(''.join(temp)))
    tds = [tr.find_all('td', attrs={'class': ''})[:2] for tr in trs
           if len(tr.find_all('td', attrs={'class': ''})) == 3]
    other = [format_string(value.string) for td in tds for value in td]
    rights_props.extend(other)
    return rights_props[2:]


# Retrieve information from 'ARCHIVE' chapter if it's not empty
def get_member_archive_inform(ref: str):
    soup = get_member_page_chapter(ref, '/certificates')
    trs = soup.find_all('tr', attrs={'rel': None})
    result, temp = [], []
    for tr in trs:
        tds = tr.find_all('td')
        for td in tds:
            tdstr = td.string
            if tdstr:
                temp.append(format_string(tdstr))
            else:
                next_a = td.find_all('a', attrs={'href': '#'})
                for a in next_a:
                    temp.append(format_string(a.string))
        result.extend(temp[1:3] + temp[4:])
        temp.clear()
    return result


# Format input string to delete useless symbols including whitespaces
def format_string(inp: str) -> str:
    return inp.replace('\n', '').strip()


def extract_information(inn: str):
    soup = page_by_inn(inn)
    trs = soup.find_all('tr', attrs={'class': 'sro-link'})
    refs = [tr['rel'] for tr in trs]
    for tr in trs:
        props = get_mainpage_inform(tr)
        for ref in refs:
            rights = get_member_rights_inform(ref)
            records_rights = len(rights[2:]) // 2
            archives = get_member_archive_inform(ref)
            records_archives = len(archives) // 4
            maximum = max(records_rights, records_archives, 1)
            soup = get_member_page_chapter(ref, '')
            trs = soup.find_all('tr')
            sro_inform = get_sro_member_inform(trs)
            length = len(df1)
            for i in range(length, length + maximum):
                write_main_information(f'{i}', props)
                write_sro_information(f'{i}', sro_inform)
            if rights:
                write_rights_information(f'{length}', rights)
            if archives:
                write_archive_information(f'{length}', archives)
    df1.to_excel("../data/Output.xlsx", sheet_name='parsed')


def write_main_information(index: str, data: list):
    columns = ['Сокращенное наименование члена СРО', 'ИНН', 'Тип', 'Рег. Номер СРО', 'Статус']
    df1.loc[index, columns] = data
    df1.loc[index, '№ п/п'] = float(index)


def write_sro_information(index: str, data: list):
    columns = ['Дата регистрации в реестре', 'Дата прекращения членства в СРО']
    df1.loc[index, columns] = data


def write_rights_information(index: str, data: list):
    columns_0 = ['Сведение о приостановлении/возобновлении права']
    columns_1 = ['Стоимость работ по одному договору подряда', 'Размер обязательств по договорам подряда']
    df1.loc[index, columns_1] = data[:2]
    records = len(data[2:]) // 2
    new_data = np.reshape(np.array(data[2:]), (records, 2))
    for record in new_data:
        df1.loc[index, columns_0] = record
        index = str(int(index) + 1)


def write_archive_information(index: str, data: list):
    records = len(data) // 4
    new_data = np.reshape(np.array(data), (records, 4))
    columns = ['Архив']
    for record in new_data:
        df1.loc[index, columns] = record
        index = str(int(index) + 1)


if __name__ == '__main__':
    for inn in inns:
        extract_information(inn)
