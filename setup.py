"""
NBComet: Jupyter Notebook extension to track full notebook history
"""

from distutils.core import setup

setup(
    name='nbcomet',
    version='0.2',
    description='Extension for tracking Jupyter Notebook history',
    url = 'https://github.com/activityhistory/nbcomet',
    author='Adam Rule',
    author_email='acrule@ucsd.edu',
    license='BSD-3-Clause',
    packages=['nbcomet'],
    package_dir={'nbcomet': 'nbcomet'},
    package_data={'nbcomet': ['static/*.js']}
)
