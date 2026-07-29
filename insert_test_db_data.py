# -*- coding: utf-8 -*-

import sys
import os
from lib.db_lib import MockDBCache


def main():
  db_path = './server'
  db_abs_path = os.path.abspath(db_path)
  print(db_abs_path)
  mock_db = MockDBCache.get(work_dir=db_path)
  MockDBCache.close_all()


if __name__ == '__main__':
  main()
  sys.exit(0)
