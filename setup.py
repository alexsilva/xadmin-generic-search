from setuptools import setup

setup(
    name='xadmin-generic-search',
    version='1.2.0',
    packages=['xplugin_generic_search'],
    url='https://github.com/alexsilva/xadmin-generic-search',
    license='MIT',
    author='alex',
    author_email='alex@fabricadigital.com.br',
    include_package_data=True,
    description='Plugin that adds the ability to search for generic content (with content-type).',
    classifiers=[
        'Framework :: Django',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.7'
    ]
)
