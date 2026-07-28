# -*- coding: utf-8 -*-
import sys
from PIL import Image


def main():
  img = Image.open("./app-icon.png")
  img.save("./assets/app.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == '__main__':
  main()
  sys.exit(0)
