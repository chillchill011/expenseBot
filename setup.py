from setuptools import setup, find_packages

setup(
    name="expense-bot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'python-telegram-bot',
        'google-api-python-client',
        'google-auth-httplib2',
        'google-auth-oauthlib',
        'python-dotenv',
        'nest-asyncio'
    ],
)