import json
import hashlib
import math
import threading
import time
import urllib.parse
from threading import Thread

from loguru import logger
import requests


class Config:
    city: str
    category: int
    page_size: int

    def __init__(self, city, category, page_size):
        self.category = category
        self.city = city
        self.page_size = page_size


class Parser:
    headers = None
    config: Config = None

    def __init__(self, config: Config):
        cities = json.loads(open("city_list.json", encoding='utf-8').read())['data']
        city_codes = {}
        for i in cities:
            city_codes[i['title']] = i['id']
        cookie = f'selected_city_code={city_codes[config.city]}'
        self.headers = {
            'Authorization': 'Basic NGxhcHltb2JpbGU6eEo5dzFRMyhy',
            'cookie': cookie
        }
        self.config = config
        logger.info("Cookie " + cookie)

    def hash(self, text):
        if isinstance(text, int):
            text = str(text)
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def sign_params(self, params):
        params['token'] = 'de1c10bf4f0a2f7fc3f2cb047712a6a9'
        d = []
        for p in params.values():
            d.append(self.hash(p))
        d.sort()

        all = "ABCDEF00G"
        for s in d:
            all += s

        sign = self.hash(all)
        params['sign'] = sign
        return params

    def get_request_query(self, params):
        return "?" + urllib.parse.urlencode(params)

    def request(self, params):
        params = self.sign_params(params)
        url = 'https://4lapy.ru/api/v2/catalog/product/list/'
        extra_url = "https://4lapy.ru/api/v2/catalog/product/info-list/"
        logger.info(f"Downloading page {params['page']}")
        data = requests.get(url + self.get_request_query(params), headers=self.headers).json()['data']
        extra_params = {
            'sort': 'popular',
        }
        for i in range(len(data['goods'])):
            extra_params[f'offers[{i}]'] = data['goods'][i]['id']
        extra_params = self.sign_params(extra_params)
        logger.info(f"Downloading extra {params['page']}")
        extra_data = requests.post(extra_url, data=extra_params, headers=self.headers).json()['data']['products']
        return data, extra_data

    def parse(self, page):
        params = {
            'sort': 'popular',
            'category_id': self.config.category,
            'page': page,
            'count': self.config.page_size
        }
        data, extra = self.request(params)
        logger.info(f"Data downloaded")
        variants = {}
        items = []
        for d in extra:
            variants[d['active_offer_id']] = d['variants'][0]
        for d in data['goods']:
            if not d.get('isAvailable'):
                continue
            result = {
                i: d[i] for i in ['id', 'title', 'webpage', 'brand_name']
            }
            if variants.get(d['id']):
                result['price'] = variants[d['id']]['price']
            items.append(result)
        logger.info(f"Page {page} parsed")
        WorkCollector.count()
        return items

    def get_total_pages(self):
        return math.ceil(self.request({
            'sort': 'popular',
            'category_id': self.config.category,
            'page': 1,
            'count': 1
        })[0]['total_items'] / self.config.page_size)


class WorkCollector:
    result = []
    counter = 0
    lock = threading.Lock()

    def __init__(self, size):
        self.result = [None for i in range(size)]

    @classmethod
    def count(cls):
        with cls.lock:
            cls.counter += 1
            logger.warning(f"Done {cls.counter} tasks")


class WorkerManager:
    workers = []

    def __init__(self, func, tasks, processes=8):
        self.tasks = tasks
        self.func = func
        self.processes = processes
        self.work_amount = len(tasks) // processes
        if self.work_amount == 0:
            self.work_amount = 1

    def start(self):
        w = []
        for i in range(min(self.processes, len(self.tasks))):
            work_end = (i + 1) * self.work_amount
            if i == self.processes - 1:
                work_end = len(self.tasks)
            tasks = self.tasks[i * self.work_amount: min(work_end, len(self.tasks))]
            t = Thread(target=self.func, args=(i, tasks,))
            logger.info(f"Starting thread {i} with {len(tasks)} tasks")
            t.start()
            w.append(t)
            if work_end >= len(self.tasks):
                break
            time.sleep(1)

        for t in w:
            t.join()


if __name__ == '__main__':
    config = Config(city='Санкт-Петербург', category=1, page_size=100)
    parser = Parser(config)
    total_pages = parser.get_total_pages()
    collector = WorkCollector(total_pages)
    logger.info(f"Total pages {total_pages}")

    def parse(id, pages):
        r = []
        for p in pages:
            r += parser.parse(p)
        collector.result[id] = r


    workers = WorkerManager(parse, [i + 1 for i in range(total_pages)])
    logger.info("Starting parser")
    workers.start()

    result = []
    for r in collector.result:
        if r is not None:
            result += r

    logger.info("Saving result")
    with open(f"{str(time.time()).split('.')[0]}_out.json", 'w', encoding='utf-8') as f:
        json.dump({
            'config': config.__dict__,
            'total': len(result),
            'items': result,
        }, f, ensure_ascii=False)
