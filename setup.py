# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(name='cashflow',
      version='1.1',
      description='Python library to generate future cashflows for budgeting.',
      url='https://gitlab.com/ddkto/cashflow',
      author='David de Koning',
      author_email='david.dekoning@gmail.com',
      license='MIT',
      packages=find_packages(),
      install_requires=['pandas','numpy'],
      zip_safe=False)