from setuptools import find_packages, setup

with open('README.rst') as file:
    long_description = file.read()

setup(
    name='django-getpaid',
    description='Multi-broker payment processor for django',
    long_description=long_description,
    version='1.3.0dev',
    packages=find_packages(),
    url='https://github.com/cypreess/django-getpaid',
    license='MIT',
    author='Krzysztof Dorosz',
    author_email='cypreess@gmail.com',
    install_requires=['django>=1.4'],
    extras_require = {
        'payu': [
            'django-celery>=3.0.11',
        ],
    },

    package_data={
        'getpaid': [
            'templates/getpaid/*.html',
        ],
        'getpaid.backends.dummy': [
            'templates/getpaid_dummy_backend/*.html',
        ],

        'getpaid.backends.dotpay': [
            'static/getpaid/backends/dotpay/*',
        ],

        'getpaid.backends.payanyway': [
            'static/getpaid/backends/payanyway/*',
        ],

        'getpaid.backends.payu': [
            'static/getpaid/backends/payu/*',
        ],

        'getpaid.backends.platron': [
            'static/getpaid/backends/platron/*',
        ],

        'getpaid.backends.transferuj': [
            'static/getpaid/backends/transferuj/*',
        ],

    },
)
