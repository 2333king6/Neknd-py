'''
爬取获取电子工业出版社新闻1.0版本，
1.爬取标题，创建时间，封面图，链接
2.添加定时任务定时执行
3.完整的代码结构

更新时间:2025-3-12 12:00
更新内容：
4.添加反爬检测，防止超时，添加爬取间隔时间

'''
# 导入所需的库
import sys
from pathlib import Path
import requests  # 用于发送HTTP请求
from bs4 import BeautifulSoup  # 用于解析HTML内容
# 新增依赖
import pymysql
from datetime import datetime
from urllib.parse import urlparse
from apscheduler.schedulers.blocking import BlockingScheduler
# 建议在代码开头添加robots.txt检查逻辑
from urllib.robotparser import RobotFileParser
from urllib.request import urlopen
from urllib.error import HTTPError  # 新增导入
from time import sleep
# from config.settings import DB_CONFIG
import logging
from logging.handlers import RotatingFileHandler
import os

# 每次请求间隔2-5秒
REQUEST_INTERVAL = 2  # 单位：秒


# 初始化日志配置（添加在import之后，类定义之前）
def setup_logger():
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # 配置日志格式
    log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    formatter = logging.Formatter(log_format)

    # 文件日志（按大小轮转）
    file_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, 'crawler.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 获取logger实例
    logger = logging.getLogger('Crawler')
    logger.setLevel(logging.INFO)

    # 避免重复添加handler
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

# 初始化全局logger
logger = setup_logger()

class DatabaseHandler:
    def __init__(self):
        self.connection = pymysql.connect(**DB_CONFIG)

    def __enter__(self):
        return self.connection.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.connection.commit()
        self.connection.close()

def check_robots_permission(url):
    try:
        rp = RobotFileParser()
        robots_url = urlparse(url).scheme + '://' + urlparse(url).netloc + '/robots.txt'

        try:
            # 尝试获取robots.txt
            response = urlopen(robots_url, timeout=10)
            content = response.read().decode("utf-8")
            rp.parse(content.splitlines())
        except HTTPError as e:
            if e.code == 404:
                logger.warning(f"未找到robots.txt，允许爬取：{url}")
                return True  # 网站无robots.txt时允许访问
            raise  # 重新抛出其他HTTP错误
        except Exception as e:
            logger.error(f"robots.txt检测异常：{str(e)}", exc_info=True)
            return True  # 其他异常默认允许访问

        return rp.can_fetch('MyBot/1.0 (+http://example.com/bot)', url)
    except Exception as e:
        logger.exception(f"robots.txt解析异常: {str(e)}")
        return True  # 异常情况建议允许访问（根据实际需求调整）

# 获取网页源代码
def get_html_text(url):
    try:
        # 设置请求头，模拟浏览器访问
        headers = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"}
        # 发送GET请求，设置超时时间和请求头，并禁止重定向
        r = requests.get(url, timeout=30, headers=headers, allow_redirects=False)
        logger.debug(f"成功获取网页内容，URL：{url} 状态码：{r.status_code}")
        r.raise_for_status()  # 如果状态不是200，引发HTTPError异常
        r.encoding = r.apparent_encoding  # 设置编码方式
        return r.text  # 返回网页内容
    except Exception as e:
        logger.error(f"网页访问异常：{url}", exc_info=True)
        return None

def save_news_to_db(news_items):
    insert_sql = """
    INSERT INTO neknd_policy_news (
        news_title, source_title, create_time, update_by, news_type, news_content, 
        status, del_flag, remark
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    with DatabaseHandler() as cursor:
        # 初始化统计计数器 ▼▼▼
        total_count = len(news_items)
        duplicate_count = 0
        outdated_count = 0
        time_format_error = 0
        valid_count = 0
        # 初始化统计计数器 ▲▲▲

        # 新增步骤1：获取数据库最新创建时间 ▼▼▼
        cursor.execute("SELECT MAX(create_time) FROM neknd_policy_news")
        latest_create_time = cursor.fetchone()[0]
        if latest_create_time:
            print(f"当前数据库最新记录时间：{latest_create_time.strftime('%Y-%m-%d')}")
        # 新增步骤1 ▲▲▲

        for item in news_items:
            # 去重检查（新增部分）
            cursor.execute("""
                           SELECT remark FROM neknd_policy_news 
                           WHERE remark = %s
                       """, (item['news_url'],))
            if cursor.fetchone():
                duplicate_count += 1  # 统计重复
                print(f'⏩ 跳过已存在新闻 >> {item["news_title"]}：{item["news_url"]}')
                continue

            # 新增时间比对逻辑 ▼▼▼
            try:
                # 转换发布时间为日期对象
                publish_date = datetime.strptime(item['publish_time'], '%Y-%m-%d').date()

                # 当数据库存在历史记录时进行比对
                if latest_create_time:
                    # 转换数据库时间为日期对象（兼容datetime和date类型）
                    db_date = latest_create_time.date() if isinstance(latest_create_time,
                                                                      datetime) else latest_create_time

                    if publish_date < db_date:
                        outdated_count += 1  # 统计过期
                        print(f"⏳ 跳过早于数据库最新时间的新闻：{item['news_title']}（{item['publish_time']}）")
                        continue
            except ValueError as e:
                time_format_error += 1  # 统计格式错误
                print(f"⚠️ 时间格式错误：{item['publish_time']} - {str(e)}")
                continue
            # 新增时间比对逻辑 ▲▲▲

            cursor.execute(insert_sql, (
                item['news_title'],
                item['source'],  # 新增来源字段
                item['publish_time'],  # 新增发布时间字段
                '爬取-中国教育新闻网',
                '1',  # 默认新闻类型为通知，按需修改
                item['news_content'],  # 内容需要后续抓取补充
                '0',  # 状态正常
                '0',  # 未删除
                # datetime.now(),
                item['news_url']
            ))
            valid_count += 1  # 统计有效插入

        # 添加统计报告 ▼▼▼
        logger.info(f"""
            ======== 数据存储统计 ========
            接收条目总数：{total_count}
            ━━━━━━━━━━━━━━━━━━━━━━
            重复跳过：{duplicate_count}
            过期跳过：{outdated_count}
            时间格式错误：{time_format_error}
            成功存储：{valid_count}
            未计入差异：{total_count - (duplicate_count + outdated_count + time_format_error + valid_count)}
            当前数据库最新记录时间：{latest_create_time.strftime('%Y-%m-%d') if latest_create_time else '无历史记录'}
            =============================
            """)
        # 添加统计报告 ▲▲▲

def parse_news_content(news_url):
    if not news_url.startswith('http'):
        print(f'⚠️ 无效的新闻链接：{news_url}')
        return ''

    """解析新闻详情页内容"""
    sleep(REQUEST_INTERVAL)  # 遵守爬取间隔
    try:
        if not check_robots_permission(news_url):
            print(f'⛔ 禁止爬取详情页：{news_url}')
            return ''

        if html := get_html_text(news_url):
            soup = BeautifulSoup(html, 'html.parser')
            content_div = soup.find('div', class_='xl_text')

            # 保留原始HTML结构但不处理
            if content_div:
                # 获取div内部所有子元素的HTML字符串
                inner_html = ''.join(str(child) for child in content_div.contents)
                return inner_html.strip()
                # return str(content_div)  # 返回原始HTML内容
            return '内容解析失败'

    except Exception as e:
        print(f'详情页解析异常：{news_url} - {str(e)}')
    return ''


def parse_page(html):
    soup = BeautifulSoup(html, 'html.parser')

    # 在 parse_page 开头添加容错判断
    if not soup.find('div', id='jybpx'):
        print('⚠️ 页面结构异常，可能遇到反爬')
        return []

    news_items = []

    # 定位新闻列表容器
    for li in soup.select('ul.yxj_list li'):
        item = {
            'news_title': '',
            'news_url': '',
            'publish_time': '',
            'source': '',
            'news_content': ''
        }

        # 提取标题和链接
        if (a_tag := li.find('a', class_='title')):
            item['news_title'] = a_tag.get('title', '').strip()
            item['news_url'] = a_tag['href'].strip()

        # 提取来源和发布时间
        if (tags := li.find('p', class_='tags')):
            spans = tags.find_all('span')
            # 来源在第二个 span
            if len(spans) >= 2:
                # item['source'] = spans[1].get_text(strip=True).split('：')[-1]
                item['source'] = spans[1].get_text(strip=True).split('：')[-1] if len(spans) >= 2 else '未知来源'
            # 发布时间在第三个 span
            if len(spans) >= 3:
                # item['publish_time'] = spans[2].get_text(strip=True).split('：')[-1]
                item['publish_time'] = spans[2].get_text(strip=True).split('：')[-1] if len(spans) >= 3 else '未知时间'

        # 新增内容抓取（在获取基础信息后）
        if item['news_url']:
            item['news_content'] = parse_news_content(item['news_url'])

        news_items.append(item)



    for item in news_items:
        print(item)

    return news_items


# 生成多页的URL列表
# def get_urls(pages):
#     urls = ['http://www.jyb.cn/rmtlistzyjy/index.html']  # 添加首页URL
#     for i in range(1, pages):
#         page = i  # 计算页面编号
#         url = "http://www.jyb.cn/rmtlistzyjy/index_{}.html".format(page)  # 拼接分页URL
#         urls.append(url)  # 将新URL添加到列表中
#     return urls  # 返回URL列表
def get_urls(pages):
    base_url = 'http://www.jyb.cn/rmtlistzyjy/index{}.html'
    return [base_url.format(f'_{page}' if page > 0 else '') for page in range(pages)]



def main():
    base_domain = 'http://www.jyb.cn'
    if not check_robots_permission(base_domain):
        print(f'⛔ 根据 robots.txt 协议禁止爬取 {base_domain}')
        exit(1)

    urls = get_urls(pages=2)

    all_news = []
    for page_number, url in enumerate(urls, start=1):
        sleep(REQUEST_INTERVAL)
        # 添加反爬检测
        try:
            if not check_robots_permission(url):
                print(f'⚠️ 根据robots.txt协议，禁止爬取：{url}')
                continue  # 跳过被禁止的URL
        except Exception as e:
            print(f'⚠️ robots.txt检测失败：{str(e)}，继续执行爬取')

        # 原有爬取逻辑
        if html := get_html_text(url):
            page_news = parse_page(html)
            print(f'第{page_number}页抓取到{len(page_news)}条新闻')
            all_news.extend(page_news)

    try:
        save_news_to_db(all_news)
    except Exception as e:
        print(f'数据库存储失败: {str(e)}')


if __name__ == '__main__':
    try:
        logger.info("=" * 50)
        logger.info("爬虫服务启动初始化...")
        scheduler = BlockingScheduler()
        scheduler.add_job(main, 'cron', hour=1, minute=0)
        logger.info("定时任务已启动，每天01:00执行爬取")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("接收到终止信号，服务正常退出")
    except Exception as e:
        logger.critical("服务异常终止", exc_info=True)