from setuptools import setup, find_packages

# 正确读取UTF-16 LE编码的文件
with open('requirements.txt', 'rb') as f:
    content = f.read()
    # 去除可能的BOM头（UTF-16 LE的BOM是 b'\xff\xfe'）
    if content.startswith(b'\xff\xfe'):
        content = content[2:]
    requirements = content.decode('utf-16-le').splitlines()

setup(
    name="neknd-crawler",
    version="1.0",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'neknd-crawler=src.crawler:main'
        ]
    }
)
