# -*- coding: utf-8 -*-
from flask import Flask, send_from_directory
import os
from pathlib import Path

WEB_ROOT = Path(os.path.abspath('B:\project\pycharm\mock-api-server\web'))
app = Flask(__name__, root_path=str(WEB_ROOT))


@app.route('/ping', methods=['GET'])
def ping():
  print('ping')
  return {'data': 'pong!'}


@app.route('/app_server/<path:path>')
def serve_static(path):
  """处理所有静态文件请求"""
  # 构建完整文件路径
  file_path = WEB_ROOT / path

  # 如果路径是目录，尝试查找index.html
  if file_path.is_dir():
    index_path = file_path / 'index.html'
    if index_path.exists():
      return send_from_directory(WEB_ROOT, f"{path}/index.html")
    return "Directory index not found", 404

  # 如果文件存在，返回文件内容
  if file_path.exists() and file_path.is_file():
    return send_from_directory(WEB_ROOT, path)

  # 如果都不存在，返回404
  return "File not found", 404


if __name__ == '__main__':
  # 确保web目录存在
  if not WEB_ROOT.exists():
    WEB_ROOT.mkdir(parents=True)
    print(f"已创建web目录: {WEB_ROOT}")
    (WEB_ROOT / 'index.html').write_text('''
          <!DOCTYPE html>
          <html>
          <head>
              <title>Welcome</title>
              <style>body{font-family: Arial, sans-serif; text-align: center; margin-top: 50px;}</style>
          </head>
          <body>
              <h1>Welcome to Static File Server</h1>
              <p>Place your static files in the 'web' directory.</p>
          </body>
          </html>
          ''', encoding='utf-8')

  print(f"静态文件根目录: {WEB_ROOT}")
  app.run(debug=True, port=5000)
