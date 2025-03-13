# 中国教育新闻网新闻采集系统

![Python](https://img.shields.io/badge/python-3.8%2B-blue)

## 📌 功能特性
- 定时抓取中国教育新闻网职教板块新闻
- 自动存储标题、链接、发布时间、来源、正文等内容
- 支持防封禁策略（请求间隔、robots.txt检测）
- 数据库去重与时间过滤机制

## 🚀 快速开始

### 环境要求
- Python 3.8+
- MySQL 5.7+

### 安装依赖

- 参考requirements.txt文件
- 

### 查看执行情况
- ps aux | grep crawler.py

- pgrep -af 'python.*crawler.py'

示例如下：

```
root@FENGPVE000:/www/wwwroot/neknd-crawler# ps aux | grep crawler.py
root       87698  1.6  0.1  51396 39484 ?        S    16:12   0:00 python src/crawler.py
root       88003  0.0  0.0   6464  2368 pts/0    S+   16:13   0:00 grep crawler.py
root@FENGPVE000:/www/wwwroot/neknd-crawler# pgrep -af 'python.*crawler.py'
87698 python src/crawler.py
```

