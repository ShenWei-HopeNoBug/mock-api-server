# -*- coding: utf-8 -*-
import sys
from PIL import Image


def main():
  from_path = '../app-icon.png'
  save_path = '../assets/app.ico'
  img = Image.open(from_path)
  img.save(save_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == '__main__':
  main()
  sys.exit(0)
